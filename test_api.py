import os
import uuid
import concurrent.futures

import requests
import redis
from sqlalchemy import create_engine, text

from database import DATABASE_URL
import main


BASE_URL = "http://127.0.0.1:8000"
PRODUCT_ID = 1
ACCESS_TOKEN = os.getenv("TEST_ACCESS_TOKEN")


def get_auth_headers():
    return {
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }


def test_products_endpoint():
    response = requests.get(
        f"{BASE_URL}/products",
        headers=get_auth_headers()
    )

    print("Status:", response.status_code)
    print("Response:", response.json())

    assert response.status_code == 200


def test_products_requires_authentication():
    response = requests.get(
        f"{BASE_URL}/products"
    )

    print("Unauthenticated status:", response.status_code)
    print("Response:", response.json())

    assert response.status_code == 401


def test_purchase_product():
    headers = {
        **get_auth_headers(),
        "Idempotency-Key": "pytest-purchase-001"
    }

    response = requests.post(
        f"{BASE_URL}/products/{PRODUCT_ID}/purchase",
        headers=headers,
        json={"quantity": 1}
    )

    print("Purchase status:", response.status_code)
    print("Purchase response:", response.json())

    assert response.status_code == 200
    assert response.json()["status"] == "SUCCESS"


def test_purchase_idempotency():
    redis_client = redis.Redis(
        host="127.0.0.1",
        port=6379,
        decode_responses=True
    )

    # Clear rate limiter before the test
    redis_client.delete("rate_limit:127.0.0.1")

    headers = {
        **get_auth_headers(),
        "Idempotency-Key": "pytest-idempotency-001"
    }

    response1 = requests.post(
        f"{BASE_URL}/products/{PRODUCT_ID}/purchase",
        headers=headers,
        json={"quantity": 1}
    )

    response2 = requests.post(
        f"{BASE_URL}/products/{PRODUCT_ID}/purchase",
        headers=headers,
        json={"quantity": 1}
    )

    print("First purchase:", response1.json())
    print("Second purchase:", response2.json())

    assert response1.status_code == 200
    assert response2.status_code == 200

    assert response1.json()["order_id"] == response2.json()["order_id"]


def test_rate_limit():
    redis_client = redis.Redis(
        host="127.0.0.1",
        port=6379,
        decode_responses=True
    )

    # Clear rate limiter before the test
    redis_client.delete("rate_limit:127.0.0.1")

    # Temporarily allow enough requests to reach the rate-limit threshold
    main.RATE_LIMIT = 5

    headers = get_auth_headers()

    responses = []

    for _ in range(6):
        response = requests.get(
            f"{BASE_URL}/products",
            headers=headers
        )

        responses.append(response.status_code)

    print("Rate-limit responses:", responses)

    assert responses[:5] == [200, 200, 200, 200, 200]
    assert responses[5] == 429


def test_concurrent_purchases():
    # Create database connection
    engine = create_engine(DATABASE_URL)

    # Reset PostgreSQL inventory
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE products SET stock = 10 WHERE id = 1")
        )

    # Reset Redis inventory
    redis_client = redis.Redis(
        host="127.0.0.1",
        port=6379,
        decode_responses=True
    )

    redis_client.set("product_stock:1", 10)

    # Clear rate limiter
    redis_client.delete("rate_limit:127.0.0.1")

    def purchase():
        headers = {
            **get_auth_headers(),
            "Idempotency-Key": f"pytest-concurrent-{uuid.uuid4()}"
        }

        response = requests.post(
            f"{BASE_URL}/products/{PRODUCT_ID}/purchase",
            headers=headers,
            json={"quantity": 1}
        )

        return response.status_code

    # Five concurrent users
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=5
    ) as executor:

        results = list(
            executor.map(lambda _: purchase(), range(5))
        )

    successful = results.count(200)

    print("Concurrent results:", results)
    print("Successful purchases:", successful)

    assert successful == 5

    # Verify PostgreSQL and Redis inventory
    with engine.connect() as connection:
        db_stock = connection.execute(
            text("SELECT stock FROM products WHERE id = 1")
        ).scalar()

    redis_stock = int(
        redis_client.get("product_stock:1")
    )

    print("PostgreSQL stock:", db_stock)
    print("Redis stock:", redis_stock)

    assert db_stock == 5
    assert redis_stock == 5