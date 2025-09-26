import requests
import time

class BackendMonitor:
    def __init__(self, backends):
        self.backends = {b: {"alive": False, "ewma": 1000, "cpu": 0} for b in backends}
        self.alpha = 0.3  
    def check_backend(self, backend):
        try:
            r = requests.get(f"{backend}/health", timeout=1)
            if r.status_code == 200:
                self.backends[backend]["alive"] = True

                latency = r.elapsed.total_seconds() * 1000
                ewma = self.backends[backend]["ewma"]
                self.backends[backend]["ewma"] = (
                    self.alpha * latency + (1 - self.alpha) * ewma
                )

                try:
                    m = requests.get(f"{backend}/metrics", timeout=1).text
                    if "cpu_usage" in m:
                        val = [line for line in m.splitlines() if "cpu_usage" in line][0]
                        self.backends[backend]["cpu"] = float(val.split()[-1])
                except:
                    pass
            else:
                self.backends[backend]["alive"] = False
        except:
            self.backends[backend]["alive"] = False

    def monitor_loop(self, interval=5):
        for backend in self.backends:
            self.check_backend(backend)
        time.sleep(interval)
