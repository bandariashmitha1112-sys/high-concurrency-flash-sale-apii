import redis

import os
import redis
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL")

if not REDIS_URL:
    raise RuntimeError("REDIS_URL is not set")

redis_client = redis.from_url(
    REDIS_URL,
    decode_responses=True
)


def set_product_stock(product_id, stock):
    key = f"product_stock:{product_id}"
    redis_client.set(key, stock)

def decrease_product_stock(product_id, quantity):
    key = f"product_stock:{product_id}"

    script = """
    local stock = tonumber(redis.call('GET', KEYS[1]) or '0')
    local quantity = tonumber(ARGV[1])

    if stock < quantity then
        return -1
    end

    return redis.call('DECRBY', KEYS[1], quantity)
    """

    remaining_stock = redis_client.eval(
        script,
        1,
        key,
        quantity
    )

    return remaining_stock
def increase_product_stock(product_id, quantity):
    key = f"product_stock:{product_id}"

    return redis_client.incrby(
        key,
        quantity
    )