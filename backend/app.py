from fastapi import FastAPI, Request, Response
import psutil
import time
import asyncio
import socket
from prometheus_client import Gauge, Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = FastAPI()

CPU_USAGE = Gauge("backend_cpu", "CPU usage percentage of the backend container")
REQUEST_COUNT = Counter(
    "backend_requests_total",
    "Total number of requests received",
    ["endpoint", "method"]
)
REQ_LATENCY = Histogram(
    "backend_latency_ms",
    "Request latency in milliseconds",
    buckets=[10, 50, 100, 200, 500, 1000, 2000]
)

HOSTNAME = socket.gethostname() 

@app.middleware("http")
async def track_latency(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    latency = (time.time() - start) * 1000
    REQUEST_COUNT.labels(endpoint=request.url.path, method=request.method).inc()
    REQ_LATENCY.observe(latency)
    return response

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
async def root():
    start = time.time()
    while time.time() - start < 0.2:  
        _ = sum(i*i for i in range(1000))  # dummy work

    return {"message": f"Hello from backend!"}


@app.get("/metrics")
def metrics():
    cpu = psutil.cpu_percent(interval=0.1)
    CPU_USAGE.set(cpu)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
