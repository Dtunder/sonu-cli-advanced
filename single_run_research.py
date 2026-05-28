import subprocess
import time
import os

def run_single_research():
    script_path = r"C:\Users\user\sonu-cli-advanced\agents_swarm\batch_researcher.py"
    log_path = r"C:\Users\user\sonu-cli-advanced\logs\research_live.log"

    # Sicherstellen, dass Log-Verzeichnis existiert
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    with open(log_path, "w") as f:
        f.write(f"[{time.ctime()}] Starte Research-Agent...\n")
        process = subprocess.Popen(
            ["python", script_path],
            stdout=f,
            stderr=subprocess.STDOUT,
            text=True
        )

        # 30 Minuten warten
        time.sleep(1800)

        if process.poll() is None:
            process.terminate()
            f.write(f"[{time.ctime()}] Zeitlimit erreicht. Agent beendet.\n")
        else:
            f.write(f"[{time.ctime()}] Agent fertig.\n")

if __name__ == "__main__":
    run_single_research()
