import time
import os
import subprocess
import docker
from jinja2 import Environment, FileSystemLoader
from prometheus_api_client import PrometheusConnect
from prometheus_client import Gauge, Counter, start_http_server

PROM_URL = os.getenv("PROM_URL", "http://prometheus:9090")
NGINX_CONF = "/etc/nginx/conf.d/upstream.conf"
NGINX_TEMPLATE = "/controller/nginx_template.j2"
POLL_INTERVAL = 5
MIN_BACKENDS = 2
MAX_BACKENDS = 5
SCALE_UP_CPU = 50     
SCALE_DOWN_CPU = 20     
SCALE_UP_LAT = 300.0      
SCALE_DOWN_LAT = 150.0    

ALL_BACKENDS = [
    {"name": "backend1", "host": "backend1", "port": 8080},
    {"name": "backend2", "host": "backend2", "port": 8080},
    {"name": "backend3", "host": "backend3", "port": 8080},
    {"name": "backend4", "host": "backend4", "port": 8080},
    {"name": "backend5", "host": "backend5", "port": 8080},
]

active_backends = ALL_BACKENDS[:MIN_BACKENDS]
current_replicas = len(active_backends)

client = docker.from_env()

REPLICA_GAUGE = Gauge("controller_backends_replicas", "Active backend replicas")
AVG_CPU_GAUGE = Gauge("controller_avg_cpu", "Average backend CPU")
AVG_LAT_GAUGE = Gauge("controller_avg_latency", "Average backend latency (ms)")
SCALE_OUT_COUNTER = Counter("controller_scale_out_total", "Scale out events")
SCALE_IN_COUNTER = Counter("controller_scale_in_total", "Scale in events")

def fetch_metrics(prom):
    metrics = {}
    cpu_query = "backend_cpu"
    lat_query = "backend_latency_ms"

    try:
        cpu_results = prom.custom_query(cpu_query)
        lat_results = prom.custom_query(lat_query)

        for r in cpu_results:
            metrics[r["metric"]["instance"]] = {"cpu": float(r["value"][1])}

        for r in lat_results:
            inst = r["metric"]["instance"]
            if inst not in metrics:
                metrics[inst] = {}
            metrics[inst]["latency"] = float(r["value"][1])

    except Exception as e:
        print(f"[Controller] Error fetching metrics: {e}")

    return metrics

def compute_weights(metrics, backends):
    scored = []
    for backend in backends:
        inst = f"{backend['host']}:8080"
        cpu = metrics.get(inst, {}).get("cpu", 100.0)
        lat = metrics.get(inst, {}).get("latency", 1000.0)

        score = cpu * 0.5 + lat * 1.0
        weight = max(1, int(1000 / (score + 1)))
        backend["weight"] = weight
        scored.append(backend)
    return scored

def avg_cpu(metrics):
    cpu_vals = [m["cpu"] for m in metrics.values() if "cpu" in m]
    return sum(cpu_vals) / len(cpu_vals) if cpu_vals else 0.0

def avg_latency(metrics):
    lat_vals = [m["latency"] for m in metrics.values() if "latency" in m]
    return sum(lat_vals) / len(lat_vals) if lat_vals else 0.0

def scale_if_needed(metrics):
    global current_replicas, active_backends

    avg = avg_cpu(metrics)
    lat = avg_latency(metrics)

    AVG_CPU_GAUGE.set(avg)
    AVG_LAT_GAUGE.set(lat)
    REPLICA_GAUGE.set(current_replicas)

    print(f"[Controller] Avg CPU = {avg:.2f}% | Avg Lat = {lat:.2f} ms | Replicas = {current_replicas}")

    # Scale UP
    if (avg > SCALE_UP_CPU or lat > SCALE_UP_LAT) and current_replicas < MAX_BACKENDS:
        new_backend = ALL_BACKENDS[current_replicas]
        container_name = new_backend["name"]
        try:
            print(f"[Controller] Scaling UP: starting {container_name}")
            try:
                c = client.containers.get(container_name)
                if c.status != "running":
                    c.start()
                    print(f"[Controller] Re-started existing {container_name}")
                else:
                    print(f"[Controller] {container_name} already running")
            except docker.errors.NotFound:
                client.containers.run(
                    "capstone-backend",
                    name=container_name,
                    detach=True,
                    network="capstone_default",
                )
                print(f"[Controller] Created new {container_name}")

            if new_backend not in active_backends:
                active_backends.append(new_backend)
            current_replicas = len(active_backends)
            SCALE_OUT_COUNTER.inc()

        except Exception as e:
            print(f"[Controller] Error scaling up {container_name}: {e}")

    # Scale DOWN
    elif (avg < SCALE_DOWN_CPU and lat < SCALE_DOWN_LAT) and current_replicas > MIN_BACKENDS:
        old_backend = active_backends.pop()
        container_name = old_backend["name"]
        try:
            print(f"[Controller] Scaling DOWN: stopping {container_name}")
            c = client.containers.get(container_name)
            c.stop()
            print(f"[Controller] Stopped {container_name}")
        except Exception as e:
            print(f"[Controller] Error scaling down {container_name}: {e}")

        current_replicas = len(active_backends)
        SCALE_IN_COUNTER.inc()

def render_conf(backends):
    env = Environment(loader=FileSystemLoader("/controller"))
    template = env.get_template("nginx_template.j2")
    return template.render(backends=backends)

def write_conf(conf_text):
    with open(NGINX_CONF, "w") as f:
        f.write(conf_text)

def reload_nginx():
    try:
        for name in ["nginx1", "nginx2"]:
            c = client.containers.get(name)
            c.exec_run("nginx -s reload")
        print("[Controller] Reloaded nginx1 & nginx2")
    except Exception as e:
        print(f"[Controller] Failed to reload nginx: {e}")


def main():
    prom = PrometheusConnect(url=PROM_URL, disable_ssl=True)
    start_http_server(9105, addr="0.0.0.0")
    print("[Controller] Started, waiting for Prometheus metrics...")

    while True:
        try:
            metrics = fetch_metrics(prom)
            scale_if_needed(metrics)
            backends = compute_weights(metrics, active_backends)
            conf_text = render_conf(backends)
            write_conf(conf_text)
            reload_nginx()

            print(f"[Controller] Active backends: {[b['name'] for b in active_backends]}")
            print(f"[Controller] Updated weights: {[(b['name'], b['weight']) for b in backends]}")

        except Exception as e:
            print("[Controller] Error:", e)

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
