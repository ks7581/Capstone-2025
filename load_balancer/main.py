from fastapi import FastAPI
from monitor import BackendMonitor
from config_updater import update_nginx_config
import threading
import time
import subprocess

BACKENDS = [
    "http://backend1:8080",
    "http://backend2:8080",
    "http://backend3:8080"
]

app = FastAPI()
monitor = BackendMonitor(BACKENDS)

def background_monitor():
    while True:
        monitor.monitor_loop(interval=2)

        update_nginx_config(monitor.backends)

        subprocess.run(["docker", "exec", "nginx", "nginx", "-s", "reload"])

        time.sleep(5)

@app.on_event("startup")
def startup_event():
    t = threading.Thread(target=background_monitor, daemon=True)
    t.start()

@app.get("/status")
def status():
    return monitor.backends

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081, reload=False)
