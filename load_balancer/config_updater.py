def update_nginx_config(backend_status, upstream_file="nginx/upstream.conf"):
    alive_backends = {b: s for b, s in backend_status.items() if s["alive"]}

    config = "upstream backend {\n"

    for b, stats in alive_backends.items():
        # lower latency = higher weight
        latency_weight = max(1, int(100 / (stats["ewma"] + 1)))

        cpu_weight = max(1, int(100 / (stats["cpu"] + 1)))

        weight = max(1, int((latency_weight + cpu_weight) / 2))

        config += f"    server {b.replace('http://','')} weight={weight};\n"

    config += "}\n"

    with open(upstream_file, "w") as f:
        f.write(config)
