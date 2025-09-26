import requests
import concurrent.futures

URL = "http://localhost:8080/"
NUM_REQUESTS = 2000
CONCURRENCY = 50

def send_request(_):
    try:
        requests.get(URL, timeout=2)
    except Exception:
        pass

with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
    executor.map(send_request, range(NUM_REQUESTS))
