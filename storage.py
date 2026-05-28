import datetime
import logging
import os
import re
import sqlite3

_SECRET_RE = re.compile(
    r'(?:AIza|sk-|xai-|gsk_|hf_)[A-Za-z0-9_\-\.]{8,}',
    re.IGNORECASE,
)

def _redact(text: str) -> str:
    return _SECRET_RE.sub("<api-key-redacted>", text)

class StorageManager:
    def __init__(self, filename=None, db_filename=None):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Isolation fuer Multi-Instanz-Szenarien
        instance_id = os.getenv("SONU_INSTANCE_ID")
        if instance_id:
            default_log = f"sonu_{instance_id}_log.md"
            default_db = f"sonu_{instance_id}.db"
        else:
            default_log = "sonu_log.md"
            default_db = "sonu.db"
            
        self.filename = filename if filename else os.path.join(base_dir, default_log)
        self.db_filename = db_filename if db_filename else os.path.join(base_dir, default_db)
        self._interaction_count_cached = None
        self._init_db()

    def _init_db(self):
        """Initialisiert die SQLite-Datenbank und erstellt Tabellen, falls nötig."""
        try:
            conn = sqlite3.connect(self.db_filename, timeout=30.0)
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
            logging.error("StorageManager: Datenbank-Initialisierung fehlgeschlagen: %s", e)

    @property
    def interaction_count(self):
        """Bestimmt die Anzahl der bereits geloggten Interaktionen (lazy)."""
        if self._interaction_count_cached is not None:
            return self._interaction_count_cached
            
        if not os.path.exists(self.filename):
            return 0
            
        try:
            # Schnelles Zählen: Wir lesen nur die letzten 100KB oder nutzen eine Heuristik,
            # um nicht die ganze Datei (die MB groß sein kann) in den RAM zu laden.
            count = 0
            with open(self.filename, "rb") as f:
                # Wir zählen einfach das Vorkommen von b"## " im Binärmodus, das ist schneller.
                for line in f:
                    if line.startswith(b"## "):
                        count += 1
            self._interaction_count_cached = count
            return count
        except Exception:
            return 0

    def log_interaction(self, question, answer):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"## {timestamp}\n\n"
        log_entry += f"**Frage:**\n{_redact(question.strip())}\n\n"
        log_entry += f"**Antwort:**\n{_redact(answer.strip())}\n\n"
        log_entry += "---\n\n"
        
        try:
            with open(self.filename, "a", encoding="utf-8") as f:
                f.write(log_entry)
            if self._interaction_count_cached is not None:
                self._interaction_count_cached += 1
        except Exception as e:
            raise IOError(f"Fehler beim Schreiben des Logs in '{self.filename}': {str(e)}")

    def get_log_path(self):
        return os.path.abspath(self.filename)

    # Preise in USD per 1M Tokens (Input / Output)
    _PRICES = {
        "gemini-2.5-flash":       (0.075,  0.30),
        "gemini-2.5-flash-lite":  (0.03,   0.10),
        "gemini-2.0-flash":       (0.10,   0.40),
        "gemini-2.0-flash-lite":  (0.075,  0.30),
        "llama-3.3-70b-versatile":(0.59,   0.79),
        "grok-2":                 (2.00,   10.0),
        "gpt-4o-mini":            (0.15,   0.60),
    }

    def estimate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        in_price, out_price = self._PRICES.get(model, (1.0, 1.0))
        return (prompt_tokens * in_price + completion_tokens * out_price) / 1_000_000

    def get_session_stats(self, since_iso: str = None) -> dict:
        """Gibt Token-Statistiken seit `since_iso` zurück (oder alles wenn None)."""
        try:
            conn = sqlite3.connect(self.db_filename, timeout=10.0)
            cursor = conn.cursor()
            if since_iso:
                cursor.execute(
                    "SELECT provider, model, SUM(prompt_tokens), SUM(completion_tokens), SUM(estimated_cost_usd), AVG(latency_ms), COUNT(*) "
                    "FROM token_logs WHERE timestamp >= ? GROUP BY provider, model",
                    (since_iso,)
                )
            else:
                cursor.execute(
                    "SELECT provider, model, SUM(prompt_tokens), SUM(completion_tokens), SUM(estimated_cost_usd), AVG(latency_ms), COUNT(*) "
                    "FROM token_logs GROUP BY provider, model"
                )
            rows = cursor.fetchall()
            conn.close()
            return rows
        except Exception:
            return []

    def log_token_usage(self, provider, model, prompt_tokens, completion_tokens, latency_ms, estimated_cost_usd=None):
        timestamp = datetime.datetime.now().isoformat()
        if estimated_cost_usd is None:
            estimated_cost_usd = self.estimate_cost(model, prompt_tokens, completion_tokens)
        try:
            conn = sqlite3.connect(self.db_filename, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO token_logs (timestamp, provider, model, prompt_tokens, completion_tokens, latency_ms, estimated_cost_usd)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (timestamp, provider, model, prompt_tokens, completion_tokens, latency_ms, estimated_cost_usd))
            conn.commit()
            conn.close()
        except Exception as e:
            logging.warning("StorageManager: Token-Log fehlgeschlagen: %s", e)
