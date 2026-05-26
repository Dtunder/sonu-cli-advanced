import psutil
import json
import os

def monitor_resources():
    cpu_usage = psutil.cpu_percent(interval=1)
    # Available RAM in MB
    available_ram = psutil.virtual_memory().available / (1024 * 1024)

    data = {
        "cpu_usage_percent": cpu_usage,
        "available_ram_mb": round(available_ram, 2)
    }

    # Filepath relative to the script location
    filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'metrics.json')

    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)

    print(f"Metrics saved to {filepath}")

if __name__ == "__main__":
    monitor_resources()
