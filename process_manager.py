import os
import subprocess
import time

class ProcessManager:
    def __init__(self, logs_dir=None):
        if logs_dir is None:
            logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        self.logs_dir = logs_dir
        self.tasks = {}
        self.task_counter = 0
        os.makedirs(self.logs_dir, exist_ok=True)

    def start_task(self, command):
        """Startet einen PowerShell-Befehl asynchron im Hintergrund."""
        self.task_counter += 1
        task_id = self.task_counter
        log_path = os.path.join(self.logs_dir, f"task_{task_id}.log")
        
        # Logdatei oeffnen und Handle sichern
        log_file = open(log_path, "w", encoding="utf-8", errors="replace")
        
        # subprocess starten
        if os.name == 'nt':
            cmd_args = ["powershell", "-Command", command]
        else:
            if "ping" in command and "-n" in command:
                command = command.replace("-n", "-c")
            cmd_args = ["sh", "-c", command]

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

import ast
import sys
import importlib

class LiveHotReloader:
    """Neural AST Hot-Reloading & Live State Repair.
    Allows hot-swapping modified class definitions and functions in running Python
    background processes without losing in-memory variables/state.
    """

    @staticmethod
    def reload_module(module_name, new_source_code):
        """Compiles new AST node and injects it directly into the running module."""
        if module_name not in sys.modules:
            raise ImportError(f"Module {module_name} is not loaded.")

        module = sys.modules[module_name]

        # Parse and compile the new source code
        try:
            tree = ast.parse(new_source_code)
            compiled_code = compile(tree, filename=f"<hot-reload-{module_name}>", mode='exec')

            # Execute the compiled code in the module's namespace
            exec(compiled_code, module.__dict__)
            return True
        except Exception as e:
            print(f"[HotReload] Error reloading module {module_name}: {e}")
            return False

    @staticmethod
    def rehabilitate_state(module_name, state_dict):
        """Forces a state-rehabilitation loop by injecting the provided state into the module."""
        if module_name not in sys.modules:
            raise ImportError(f"Module {module_name} is not loaded.")

        module = sys.modules[module_name]

        try:
            for key, value in state_dict.items():
                setattr(module, key, value)
            return True
        except Exception as e:
            print(f"[HotReload] Error rehabilitating state for {module_name}: {e}")
            return False
