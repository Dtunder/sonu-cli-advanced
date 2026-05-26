import datetime
import os
import sqlite3
import time

class StorageManager:
    def __init__(self, filename=None, db_filename=None):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.filename = filename if filename else os.path.join(base_dir, "sonu_log.md")
        self.db_filename = db_filename if db_filename else os.path.join(base_dir, "sonu.db")
        self.interaction_count = 0
        self._count_existing_interactions()
        self._init_db()

    def _init_db(self):
        try:
            conn = sqlite3.connect(self.db_filename)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS token_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    provider TEXT,
                    model TEXT,
                    prompt_tokens INTEGER,
                    completion_tokens INTEGER,
                    latency_ms REAL,
                    estimated_cost_usd REAL
                )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Fehler bei der Initialisierung der Datenbank: {e}")

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

    def log_token_usage(self, provider, model, prompt_tokens, completion_tokens, latency_ms, estimated_cost_usd=0.0):
        timestamp = datetime.datetime.now().isoformat()
        try:
            conn = sqlite3.connect(self.db_filename)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO token_logs (timestamp, provider, model, prompt_tokens, completion_tokens, latency_ms, estimated_cost_usd)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (timestamp, provider, model, prompt_tokens, completion_tokens, latency_ms, estimated_cost_usd))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Fehler beim Loggen des Token-Verbrauchs: {e}")

    def get_token_usage_stats(self):
        """Returns aggregated token usage statistics by provider."""
        stats = {}
        try:
            conn = sqlite3.connect(self.db_filename)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT provider, SUM(prompt_tokens), SUM(completion_tokens), SUM(estimated_cost_usd)
                FROM token_logs
                GROUP BY provider
            ''')
            rows = cursor.fetchall()
            for row in rows:
                stats[row[0]] = {
                    "prompt_tokens": row[1],
                    "completion_tokens": row[2],
                    "cost": row[3]
                }
            conn.close()
        except Exception as e:
            print(f"Fehler beim Abrufen der Quota-Statistiken: {e}")
        return stats
