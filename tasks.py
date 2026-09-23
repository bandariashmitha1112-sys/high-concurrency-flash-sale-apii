from database import SessionLocal

from database import SessionLocal


def process_purchase_notification(order_id):
    from main import OrderTable

    db = SessionLocal()

    try:
        order = db.query(OrderTable).filter(
            OrderTable.id == order_id
        ).first()

        if order is None:
            print(f"Order {order_id} not found")
            return

        order.notification_status = "SENT"
        db.commit()

        print(f"Notification processed for order {order_id}")

    except Exception as e:
        db.rollback()
        print(f"Notification failed for order {order_id}: {e}")
        raise

    finally:
        db.close()
