import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
import subprocess
import time

class ProcessManager:
    def __init__(self, logs_dir=None):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        if logs_dir is None:
            logs_dir = os.path.join(self.base_dir, "logs")
        self.logs_dir = logs_dir
        self.tasks = {}
        self.task_counter = 0
        self.executor = ThreadPoolExecutor(max_workers=5)
        os.makedirs(self.logs_dir, exist_ok=True)

    def start_task(self, command: str) -> int:
        """Startet einen Shell-Befehl im Hintergrund. Erkennt das Betriebssystem automatisch."""
        self.task_counter += 1
        task_id = self.task_counter
        instance_id = os.getenv("SONU_INSTANCE_ID", "default")
        log_path = os.path.join(self.logs_dir, f"task_{instance_id}_{task_id}.log")
        log_fh = open(log_path, "w", encoding="utf-8")
        
        # Betriebssystem-spezifische Shell-Wahl
        if os.name == 'nt':
            shell_cmd = ["powershell", "-NoProfile", "-Command", command]
        else:
            # Versuche bash, falls nicht vorhanden sh
            import shutil
            shell_path = shutil.which("bash") or shutil.which("sh") or "/bin/sh"
            shell_cmd = [shell_path, "-c", command]

        proc = subprocess.Popen(
            shell_cmd,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            cwd=self.base_dir,
        )
        self.tasks[task_id] = {
            "process": proc,
            "log_fh": log_fh,
            "command": command,
            "log_path": log_path,
            "start_time": time.time(),
        }
        return task_id

    async def start_task_async(self, command: str) -> int:
        """Async-Variante: delegiert an start_task über den ThreadPoolExecutor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.executor, self.start_task, command)


    def list_tasks(self):
        """Gibt eine Liste aller registrierten Tasks und deren Status zurueck."""
        active = []
        for tid, tinfo in list(self.tasks.items()):
            proc = tinfo["process"]
            status = "Running"
            exit_code = proc.poll()
            if exit_code is not None:
                status = f"Completed (Exit {exit_code})"
                try:
                    tinfo["log_fh"].close()
                except Exception:
                    pass
            
            elapsed = time.time() - tinfo["start_time"]
            active.append({
                "id": tid,
                "command": tinfo["command"],
                "status": status,
                "elapsed": f"{elapsed:.1f}s"
            })
        return active

    def read_task_output(self, task_id, tail_lines=25):
        """Liest die aktuellsten Zeilen der Task-Ausgabe aus der Logdatei."""
        if task_id not in self.tasks:
            raise ValueError(f"Task-ID {task_id} existiert nicht.")
        
        log_path = self.tasks[task_id]["log_path"]
        if not os.path.exists(log_path):
            return "(Keine Logs verfuegbar)"
            
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            tail = lines[-tail_lines:] if len(lines) > tail_lines else lines
            return "".join(tail)
        except Exception as e:
            return f"Fehler beim Lesen der Ausgabedatei: {str(e)}"

    def watch_task_output(self, task_id):
        """Generator: liefert neue Log-Zeilen in Echtzeit. Stoppt wenn Prozess beendet."""
        if task_id not in self.tasks:
            raise ValueError(f"Task-ID {task_id} existiert nicht.")

        log_path = self.tasks[task_id]["log_path"]
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            # Bewege Pointer ans Ende
            f.seek(0, os.SEEK_END)
            while True:
                line = f.readline()
                if not line:
                    if self.tasks[task_id]["process"].poll() is not None:
                        break
                    time.sleep(0.1)
                    continue
                yield line

    def kill_task(self, task_id: int):
        """Beendet einen laufenden Task gewaltsam."""
        if task_id not in self.tasks:
            raise ValueError(f"Task-ID {task_id} existiert nicht.")
        tinfo = self.tasks[task_id]
        proc = tinfo["process"]
        if proc.poll() is None:
            try:
                proc.kill()
                proc.wait(timeout=5)
            except Exception:
                pass
        try:
            tinfo["log_fh"].close()
        except Exception:
            pass
