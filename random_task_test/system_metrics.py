import psutil
import json
import time
import os

def log_system_metrics():
    # Get system metrics
    cpu_usage = psutil.cpu_percent(interval=1)
    ram_usage = psutil.virtual_memory().percent

    metrics = {
        "timestamp": time.time(),
        "cpu_usage_percent": cpu_usage,
        "ram_usage_percent": ram_usage
    }

    # Write to JSON file
    file_path = os.path.join(os.path.dirname(__file__), "metrics.json")
    with open(file_path, "w") as f:
        json.dump(metrics, f, indent=4)

    print(f"Metrics logged to {file_path}")

if __name__ == "__main__":
    log_system_metrics()
