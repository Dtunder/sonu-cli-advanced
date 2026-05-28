import json
import os
import time
import logging
import sqlite3
import threading
from datetime import datetime

try:
    import psutil as _psutil
    _PSUTIL_OK = True
except ImportError:
    _PSUTIL_OK = False

# Set up logging
logger = logging.getLogger(__name__)

class TemporalMemory:
    def __init__(self, storage_path="skills/ltm_archive.json", db_path="sessions.db"):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.storage_path = os.path.join(base_dir, storage_path)
        self.db_path = os.path.join(base_dir, db_path)
        self.lock = threading.Lock()

        # Ensure directory exists
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)

        if not os.path.exists(self.storage_path):
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump({"last_updated": str(datetime.now()), "memories": []}, f)

        self._init_db()

    def _init_db(self):
        """Initialisiert die SQLite-Datenbank für Session-Historie."""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT,
                        topic TEXT,
                        turns TEXT
                    )
                """)
                conn.commit()
                conn.close()
        except Exception as e:
            logger.error(f"Error initializing sessions database: {e}")

    # --- Session Management (Requested by main.py) ---

    def save_session(self, turns, topic=None):
        """Speichert eine komplette Interaktions-Session."""
        if not turns:
            return
        if not topic:
            topic = turns[0].get("user", "Untitled Session")[:80]

        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO sessions (timestamp, topic, turns) VALUES (?, ?, ?)",
                    (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), topic, json.dumps(turns))
                )
                conn.commit()
                conn.close()
            logger.info(f"Session '{topic}' saved successfully.")
        except Exception as e:
            logger.error(f"Error saving session: {e}")

    def list_sessions(self, count=8):
        """Listet die letzten n Sessions auf."""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT id, timestamp, topic, turns FROM sessions ORDER BY timestamp DESC LIMIT ?", (count,))
                rows = cursor.fetchall()
                conn.close()

                results = []
                for r in rows:
                    try:
                        turn_list = json.loads(r[3])
                        turn_count = len(turn_list)
                    except Exception:
                        turn_count = 0

                    results.append({
                        "id": r[0],
                        "timestamp": r[1],
                        "topic": r[2],
                        "turns": turn_count
                    })
                return results
        except Exception as e:
            logger.error(f"Error listing sessions: {e}")
            return []

    def load_session(self, session_id):
        """Lädt eine spezifische Session anhand ihrer ID."""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT turns, topic FROM sessions WHERE id = ?", (session_id,))
                row = cursor.fetchone()
                conn.close()
                if row:
                    return {"turns": json.loads(row[0]), "topic": row[1]}
                raise ValueError(f"Session {session_id} wurde nicht gefunden.")
        except Exception as e:
            logger.error(f"Error loading session {session_id}: {e}")
            raise

    def search_sessions(self, query):
        """Durchsucht Sessions nach einem Stichwort im Topic oder Inhalt."""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                q = f"%{query}%"
                cursor.execute(
                    "SELECT id, timestamp, topic FROM sessions WHERE topic LIKE ? OR turns LIKE ? ORDER BY timestamp DESC",
                    (q, q)
                )
                rows = cursor.fetchall()
                conn.close()
                return [{"id": r[0], "timestamp": r[1], "topic": r[2]} for r in rows]
        except Exception as e:
            logger.error(f"Error searching sessions: {e}")
            return []

    # --- Long Term Memory (Summaries) ---

    def save_memory(self, summary):
        """Speichert ein verdichtetes Summary im LTM-JSON-Archiv."""
        try:
            with self.lock:
                with open(self.storage_path, "r+", encoding="utf-8") as f:
                    data = json.load(f)
                    data["memories"].append({
                        "timestamp": str(datetime.now()),
                        "content": summary
                    })
                    # Behalte nur die letzten 50 wichtigsten Summaries
                    if len(data["memories"]) > 50:
                        data["memories"] = data["memories"][-50:]
                    data["last_updated"] = str(datetime.now())
                    f.seek(0)
                    json.dump(data, f, indent=4)
                    f.truncate()
            logger.info("LTM memory saved successfully.")
        except Exception as e:
            logger.error(f"Error saving LTM memory: {str(e)}")

    def get_all_memories(self):
        """Gibt alle LTM-Summaries als formatierten String zurück."""
        try:
            if not os.path.exists(self.storage_path):
                return ""
            with self.lock:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return "\n".join([f"- {m['content']}" for m in data.get('memories', [])])
        except Exception as e:
            logger.error(f"Error getting LTM memories: {str(e)}")
            return ""

    # --- System Health (Internal Monitoring) ---

    def get_system_health(self):
        if not _PSUTIL_OK:
            return {}
        try:
            proc = _psutil.Process()
            return {
                "cpu_usage": proc.cpu_percent(interval=None),
                "memory_usage": proc.memory_info().rss / (1024 * 1024),
                "disk_usage": _psutil.disk_usage(os.path.splitdrive(self.db_path)[0] or "/").free / (1024 * 1024),
            }
        except Exception as e:
            logger.error("Error getting system health: %s", e)
            return {}

    def monitor_system_health(self):
        while True:
            try:
                health = self.get_system_health()
                if health:
                    logger.info("System health: CPU=%.1f%% Memory=%.1fMB Disk=%.1fMB",
                                health["cpu_usage"], health["memory_usage"], health["disk_usage"])
            except Exception as e:
                logger.error("Error monitoring system health: %s", e)
            time.sleep(60)

    def start_monitoring(self):
        t = threading.Thread(target=self.monitor_system_health, daemon=True)
        t.start()
