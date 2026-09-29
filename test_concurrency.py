import requests
import concurrent.futures
import time
import threading


PRODUCT_ID = 1

URL = f"http://127.0.0.1:8000/products/{PRODUCT_ID}/purchase"

NUMBER_OF_USERS = 50

ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzg5OTY3OTE0fQ.Ld7EA2PGNybnHnE76vbQxc8LJKkuebt9tmyfVYLAHqY"


def purchase():
    start = time.perf_counter()

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Idempotency-Key": f"flash-test-{threading.get_ident()}-{time.time_ns()}"
    }

    response = requests.post(
        URL,
        headers=headers,
        json={"quantity": 1}
    )

    end = time.perf_counter()

    return {
        "status": response.status_code,
        "data": response.json(),
        "time": end - start
    }


start_time = time.perf_counter()


with concurrent.futures.ThreadPoolExecutor(
    max_workers=NUMBER_OF_USERS
) as executor:

    results = list(
        executor.map(
            lambda _: purchase(),
            range(NUMBER_OF_USERS)
        )
    )


end_time = time.perf_counter()


successful = 0
failed = 0

response_times = []


for result in results:

    response_times.append(result["time"])

    if result["data"].get("status") == "SUCCESS":
        successful += 1
    else:
        failed += 1


total_time = end_time - start_time

requests_per_second = NUMBER_OF_USERS / total_time

average_response_time = sum(response_times) / len(response_times)


print()
print("======================================")
print("       FLASH SALE LOAD TEST")
print("======================================")

print("Total requests       :", NUMBER_OF_USERS)
print("Successful purchases :", successful)
print("Failed purchases     :", failed)

print("Total time           :", round(total_time, 4), "seconds")

print(
    "Average response     :",
    round(average_response_time, 4),
    "seconds"
)

print(
    "Requests per second  :",
    round(requests_per_second, 2)
)

print("======================================")