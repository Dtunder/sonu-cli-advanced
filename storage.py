import datetime
import os

class StorageManager:
    def __init__(self, filename="sonu_log.md"):
        self.filename = filename
        self.interaction_count = 0
        self._count_existing_interactions()

    def _count_existing_interactions(self):
        """Versucht, die Anzahl der bereits geloggten Interaktionen zu bestimmen."""
        if not os.path.exists(self.filename):
            return
        try:
            with open(self.filename, "r", encoding="utf-8") as f:
                content = f.read()
                # Zähle die Vorkommen von Datums-Headern
                self.interaction_count = content.count("## ")
        except Exception:
            pass

    def log_interaction(self, question, answer):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"## {timestamp}\n\n"
        log_entry += f"**Frage:**\n{question.strip()}\n\n"
        log_entry += f"**Antwort:**\n{answer.strip()}\n\n"
        log_entry += "---\n\n"
        
        try:
            with open(self.filename, "a", encoding="utf-8") as f:
                f.write(log_entry)
            self.interaction_count += 1
        except Exception as e:
            raise IOError(f"Fehler beim Schreiben des Logs in '{self.filename}': {str(e)}")

    def get_log_path(self):
        return os.path.abspath(self.filename)
