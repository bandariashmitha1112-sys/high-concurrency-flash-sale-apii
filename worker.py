from redis import Redis
from rq import Queue
from tasks import process_purchase_notification

redis_connection = Redis(
    host="127.0.0.1",
    port=6379,
    decode_responses=True
)

queue = Queue(
    "flash_sale",
    connection=redis_connection
)

job = queue.enqueue(
    process_purchase_notification,
    123
)

print("Job added to queue!")
print("Job ID:", job.id)