import os
import subprocess
import time
import sys
import ast

class LiveHotReloader:
    def __init__(self):
        self.reloaded_modules = {}

    def hot_reload(self, file_path: str, module_name: str) -> bool:
        """AST-basiertes Hot-Reloading zur Laufzeit, ohne Variablenverlust."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()

            # Syntaxprüfung via AST
            ast.parse(source_code)

            # Modul in sys.modules patchen
            if module_name in sys.modules:
                mod = sys.modules[module_name]
                exec(source_code, mod.__dict__)
                self.reloaded_modules[module_name] = time.time()
                return True
            else:
                return False
        except Exception as e:
            print(f"[LiveHotReloader] Fehler beim Neuladen von {module_name}: {e}")
            return False

class ProcessManager:
    def __init__(self, logs_dir=None):
        if logs_dir is None:
            logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        self.logs_dir = logs_dir
        self.tasks = {}
        self.task_counter = 0
        os.makedirs(self.logs_dir, exist_ok=True)

    def start_task(self, command):
        """Startet einen Befehl asynchron im Hintergrund (plattformübergreifend)."""
        self.task_counter += 1
        task_id = self.task_counter
        log_path = os.path.join(self.logs_dir, f"task_{task_id}.log")
        
        # Logdatei oeffnen und Handle sichern
        log_file = open(log_path, "w", encoding="utf-8", errors="replace")
        
        # subprocess starten (plattformübergreifend)
        cmd_args = ["powershell", "-Command", command] if os.name == 'nt' else ["sh", "-c", command]
        proc = subprocess.Popen(
            cmd_args,
            stdout=log_file,
            stderr=log_file,
            stdin=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0,
            text=True
        )
        
        self.tasks[task_id] = {
            "process": proc,
            "command": command,
            "log_path": log_path,
            "log_file": log_file,
            "start_time": time.time()
        }
        return task_id

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
                    tinfo["log_file"].close()
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

    def kill_task(self, task_id):
        """Beendet den Hintergrundprozess sicher."""
        if task_id not in self.tasks:
            raise ValueError(f"Task-ID {task_id} existiert nicht.")
            
        tinfo = self.tasks[task_id]
        proc = tinfo["process"]
        
        if proc.poll() is None:
            import signal
            if os.name == 'nt':
                # Sende CTRL_BREAK an die Prozessgruppe unter Windows
                proc.send_signal(signal.CTRL_BREAK_EVENT)
                proc.kill()
            else:
                proc.terminate()
            # Echten Poll erzwingen
            proc.poll()
            
        try:
            tinfo["log_file"].close()
        except Exception:
            pass
            
        return True
