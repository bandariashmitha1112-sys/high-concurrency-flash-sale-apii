from dotenv import load_dotenv
import os
from redis import Redis
from rq import Queue
from redis_client import (
    redis_client,
    decrease_product_stock,
    increase_product_stock,
    set_product_stock
)

queue = Queue(
    "flash_sale",
    connection=redis_client
)
from tasks import process_purchase_notification
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Depends, HTTPException, Form, Header, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from database import Base, engine, SessionLocal
from redis_client import (
    redis_client,
    decrease_product_stock,
    increase_product_stock
)
from pwdlib import PasswordHash
import jwt
from datetime import datetime, timedelta, timezone
from time import time


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# SECURITY SETTINGS
# =========================

password_hash = PasswordHash.recommended()

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


# =========================
# RATE LIMITING
# =========================

RATE_LIMIT = 5
RATE_WINDOW = 60

def check_rate_limit(request: Request):
    client_ip = request.client.host

    key = f"rate_limit:{client_ip}"

    current_count = redis_client.incr(key)

    if current_count == 1:
        redis_client.expire(key, RATE_WINDOW)

    if current_count > RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later."
        )

# =========================
# DATABASE MODELS
# =========================

class ProductTable(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    price = Column(Float)
    stock = Column(Integer)

class UserTable(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)


class OrderTable(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer)
    quantity = Column(Integer)
    status = Column(String)
    idempotency_key = Column(String, unique=True, index=True)
    notification_status = Column(String, default="PENDING")
# =========================
# CREATE DATABASE TABLES
# =========================

Base.metadata.create_all(bind=engine)
def initialize_redis_stock():
    db = SessionLocal()

    try:
        products = db.query(ProductTable).all()

        for product in products:
            key = f"product_stock:{product.id}"

            if not redis_client.exists(key):
                set_product_stock(product.id, product.stock)

    finally:
        db.close()
initialize_redis_stock()

# =========================
# PYDANTIC SCHEMAS
# =========================

class Product(BaseModel):
    name: str
    price: float
    stock: int


class UserCreate(BaseModel):
    username: str
    email: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class PurchaseRequest(BaseModel):
    quantity: int = Field(..., ge=1, le=10)


# =========================
# DATABASE SESSION
# =========================

def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# =========================
# CURRENT USER
# =========================

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        user_id = payload.get("sub")

        if user_id is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid token"
            )

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )

    user = db.query(UserTable).filter(
        UserTable.id == int(user_id)
    ).first()

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )

    return user


# =========================
# HOME
# =========================

@app.get("/")
def home():
    return {
        "message": "Flash Sale API is running!"
    }


# =========================
# CREATE PRODUCT
# =========================

@app.post("/products")
def create_product(
    product: Product,
    db: Session = Depends(get_db),
    current_user: UserTable = Depends(get_current_user)
):
    new_product = ProductTable(
        name=product.name,
        price=product.price,
        stock=product.stock
    )

    db.add(new_product)
    db.commit()
    db.refresh(new_product)

    return {
        "id": new_product.id,
        "name": new_product.name,
        "price": new_product.price,
        "stock": new_product.stock
    }


# =========================
# GET PRODUCTS
# =========================

@app.get("/products")
def get_products(
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserTable = Depends(get_current_user)
):
    check_rate_limit(request)
    products = db.query(ProductTable).order_by(ProductTable.id).all()

    return [
        {
            "id": product.id,
            "name": product.name,
            "price": product.price,
            "stock": product.stock
        }
        for product in products
    ]


# =========================
# PURCHASE PRODUCT
# =========================

@app.post("/products/{product_id}/purchase")
def purchase_product(
    product_id: int,
    purchase: PurchaseRequest,
    request: Request,
    idempotency_key: str = Header(...),
    db: Session = Depends(get_db),
    current_user: UserTable = Depends(get_current_user)
):
    # Rate limiting
    check_rate_limit(request)

    # Check whether this request was already processed
    existing_order = db.query(OrderTable).filter(
        OrderTable.idempotency_key == idempotency_key
    ).first()

    if existing_order:
        return {
            "order_id": existing_order.id,
            "user_id": existing_order.user_id,
            "product_id": existing_order.product_id,
            "quantity": existing_order.quantity,
            "status": existing_order.status,
            "message": "Existing order returned"
        }

    # Lock the product row
    product = db.query(ProductTable).filter(
        ProductTable.id == product_id
    ).with_for_update().first()

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    # Check stock
    remaining_stock = decrease_product_stock(
    product_id,
    purchase.quantity
)
    if remaining_stock == -1:
        raise HTTPException(
        status_code=400,
        detail="Not enough stock"
    )
    product.stock = product.stock - purchase.quantity
    # Create order
    new_order = OrderTable(
        user_id=current_user.id,
        product_id=product.id,
        quantity=purchase.quantity,
        status="SUCCESS",
        idempotency_key=idempotency_key,
        notification_status="PENDING"
    )

    db.add(new_order)
    # Commit safely
    try:
        db.commit()

    except SQLAlchemyError:
        db.rollback()

        increase_product_stock(
            product_id,
            purchase.quantity
        )

        existing_order = db.query(OrderTable).filter(
            OrderTable.idempotency_key == idempotency_key
        ).first()

        if existing_order:
            return {
                "order_id": existing_order.id,
                "user_id": existing_order.user_id,
                "product_id": existing_order.product_id,
                "quantity": existing_order.quantity,
                "status": existing_order.status,
                "message": "Existing order returned"
            }

        raise HTTPException(
            status_code=500,
            detail="Database error while processing purchase"
        )

    db.refresh(new_order)

    # Add background notification job
    try:
        queue.enqueue(
            process_purchase_notification,
            new_order.id
        )
    except Exception as e:
        print(f"Queue enqueue failed for order {new_order.id}: {e}")

    return {
        "order_id": new_order.id,
        "user_id": current_user.id,
        "product_id": product.id,
        "quantity": new_order.quantity,
        "status": new_order.status,
        "remaining_stock": product.stock
    }


# =========================
# USER REGISTRATION
# =========================

@app.post("/register")
def register_user(
    user: UserCreate,
    db: Session = Depends(get_db)
):
    hashed_password = password_hash.hash(user.password)

    new_user = UserTable(
        username=user.username,
        email=user.email,
        password_hash=hashed_password
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "id": new_user.id,
        "username": new_user.username,
        "email": new_user.email
    }


# =========================
# USER LOGIN
# =========================

@app.post("/login")
def login_user(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    existing_user = (
        db.query(UserTable)
        .filter(UserTable.username == username)
        .first()
    )

    if not existing_user:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    if not password_hash.verify(
        password,
        existing_user.password_hash
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    token_data = {
        "sub": str(existing_user.id),
        "exp": expire
    }

    access_token = jwt.encode(
        token_data,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }
@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }