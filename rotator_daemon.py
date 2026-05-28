import os
import json
import time
import logging
from google import genai
from google.genai import types

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(BASE_DIR, "logs")
ENV_PATH = os.path.join(BASE_DIR, ".env")

# Setup Logging
os.makedirs(LOGS_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] RotatorDaemon: %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, "rotator_daemon.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("RotatorDaemon")

# Konfiguration
COOLDOWN_FILE = os.path.join(LOGS_DIR, "keys_cooldown.json")
CHECK_INTERVAL = 30
# WICHTIG: Nutze ein Modell, das sicher existiert!
PROBE_MODEL = "gemini-2.0-flash-lite"

class APIRotatorDaemon:
    def __init__(self):
        self.cooldown_file = COOLDOWN_FILE
        self.keys = self._load_keys()
        self.running = True
        logger.info(f"Rotator Daemon initialisiert mit {len(self.keys)} Keys.")

    def _load_keys(self):
        from dotenv import load_dotenv
        load_dotenv(ENV_PATH, override=True)
        keys = []
        key_file = os.getenv("GEMINI_KEY_FILE", "").strip()
        if key_file:
            if not os.path.isabs(key_file):
                key_file = os.path.join(BASE_DIR, key_file)
            if os.path.exists(key_file):
                try:
                    with open(key_file, "r", encoding="utf-8-sig") as f:
                        keys.extend(k.strip() for k in f if k.strip() and not k.strip().startswith("#"))
                except Exception as e:
                    logger.error(f"Fehler beim Laden von GEMINI_KEY_FILE: {e}")
        pool = os.getenv("GEMINI_KEY_POOL", "")
        if pool:
            keys.extend(k.strip() for k in pool.split(",") if k.strip())
        standalone = os.getenv("GEMINI_API_KEY")
        if standalone and standalone not in keys:
            keys.insert(0, standalone)
        return list(dict.fromkeys(keys))

    def _load_cooldowns(self):
        if not os.path.exists(self.cooldown_file):
            return {}
        try:
            with open(self.cooldown_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_cooldowns(self, cooldowns):
        try:
            now = time.time()
            active = {k: v for k, v in cooldowns.items() if v > now}
            with open(self.cooldown_file, "w", encoding="utf-8") as f:
                json.dump(active, f)
        except Exception as e:
            logger.error(f"Fehler beim Speichern: {e}")

    def check_health(self):
        cooldowns = self._load_cooldowns()
        now = time.time()
        needs_check = [k for k, expiry in cooldowns.items() if expiry <= now or (expiry - now) > 3600] # Auch "permanente" 403er mal prüfen falls sie manuell gefixt wurden

        if not needs_check:
            return

        logger.info(f"Prüfe {len(needs_check)} Keys auf Reaktivierung...")
        changed = False
        for key in needs_check:
            res = self._verify_key(key)
            if res is True:
                logger.info(f"✅ Key {key[:8]}... ist wieder gesund.")
                del cooldowns[key]
                changed = True
            elif res == "FATAL":
                logger.error(f"🚫 Key {key[:8]}... ist UNGÜLTIG (403). Markiere permanent.")
                cooldowns[key] = now + 86400 * 30 # 30 Tage
                changed = True
            else:
                logger.warning(f"❌ Key {key[:8]}... immer noch im Limit.")

        if changed:
            self._save_cooldowns(cooldowns)

    def _verify_key(self, api_key):
        try:
            client = genai.Client(api_key=api_key)
            client.models.generate_content(
                model=PROBE_MODEL,
                contents="hi",
                config=types.GenerateContentConfig(max_output_tokens=1)
            )
            return True
        except Exception as e:
            err = str(e).lower()
            if "quota" in err or "429" in err or "limit" in err:
                return False
            if "403" in err or "forbidden" in err:
                return "FATAL"
            return False

    def run_loop(self):
        logger.info("Daemon-Loop gestartet.")
        while self.running:
            try:
                self.check_health()
                time.sleep(CHECK_INTERVAL)
            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                logger.error(f"Loop-Fehler: {e}")
                time.sleep(10)

if __name__ == "__main__":
    daemon = APIRotatorDaemon()
    daemon.run_loop()
