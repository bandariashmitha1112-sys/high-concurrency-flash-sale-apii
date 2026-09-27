import os
from redis import Redis
from rq import Queue
from dotenv import load_dotenv

from tasks import process_purchase_notification

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL")

if not REDIS_URL:
    raise RuntimeError("REDIS_URL is not set")

redis_connection = Redis.from_url(
    REDIS_URL,
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