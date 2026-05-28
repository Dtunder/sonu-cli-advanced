"""
Sonu CLI — Core Agent Client
Aufgebaut wie Gemini CLI (turn.ts + geminiChat.ts + retry.ts),
einziger Unterschied: Key-Rotation über Pool statt single key.
"""

import os
import time
import json

from dotenv import load_dotenv


class QuotaExhaustedException(Exception):
    def __init__(self, model_name, key_count):
        self.model_name = model_name
        self.key_count = key_count
        super().__init__(
            f"Alle {key_count} API-Keys haben die Tagesquota fuer '{model_name}' erschoepft."
        )


# ---------------------------------------------------------------------------
# Lazy SDK proxies — gleich wie vorher, vermeidet 2s Import beim Start
# ---------------------------------------------------------------------------

class _LazyGenai:
    def __getattr__(self, name):
        from google import genai
        return getattr(genai, name)

class _LazyTypes:
    def __getattr__(self, name):
        from google.genai import types
        return getattr(types, name)

genai = _LazyGenai()
types = _LazyTypes()

# ---------------------------------------------------------------------------
# Retry-Logik — portiert von Gemini CLI retry.ts
# Retryable: 429, 499, 5xx, Netzwerkfehler
# Terminal:  403 (auth), 400 (bad request), Tages-Quota
# ---------------------------------------------------------------------------

_RETRYABLE_STATUS = {429, 499, 500, 502, 503, 504}
_DAILY_QUOTA_PHRASES = ("daily", "per day", "day quota", "exceeded your", "resource_exhausted")
_AUTH_PHRASES = ("403", "forbidden", "unauthorized", "invalid api key", "api_key_invalid")
_RATE_PHRASES = ("429", "quota", "rate limit", "resource exhausted", "rateerror")


def _is_daily_quota(err: str) -> bool:
    e = err.lower()
    return any(p in e for p in _DAILY_QUOTA_PHRASES)


def _is_auth_error(err: str) -> bool:
    e = err.lower()
    return any(p in e for p in _AUTH_PHRASES)


def _is_rate_error(err: str) -> bool:
    e = err.lower()
    return any(p in e for p in _RATE_PHRASES)


def _is_server_error(err: str) -> bool:
    e = err.lower()
    return any(c in e for c in ("500", "502", "503", "504", "internal server"))


# ---------------------------------------------------------------------------
# Key-Pool — das einzige was Sonu von Gemini CLI unterscheidet
# Gemini CLI: 1 key, retry mit backoff
# Sonu:       N keys, bei 429/daily-quota → naechsten Key
# ---------------------------------------------------------------------------

class KeyPool:
    """Verwaltet N Gemini API-Keys mit Cooldown pro Key."""

    # Cooldown-Dauern
    DAILY_COOLDOWN = 3600.0      # 1h wenn Tages-Quota
    RATE_COOLDOWN = 65.0         # 65s bei RPM-Limit
    AUTH_COOLDOWN = 86400.0 * 30 # 30 Tage bei falschem Key (manuell resetten)

    def __init__(self, keys: list[str], state_file: str):
        self.keys = keys
        self._state_file = state_file
        # {key_index: {"until": float, "kind": str}}
        self._cooldown: dict[int, dict] = {}
        self._active = 0
        self._load()

    # -- Public API --

    def active_key(self) -> str | None:
        if not self.keys:
            return None
        return self.keys[self._active]

    def active_index(self) -> int:
        return self._active

    def count(self) -> int:
        return len(self.keys)

    def mark_rate_limited(self, idx: int):
        self._set_cooldown(idx, "rate", self.RATE_COOLDOWN)

    def mark_daily_exhausted(self, idx: int):
        self._set_cooldown(idx, "daily", self.DAILY_COOLDOWN)

    def mark_auth_failed(self, idx: int):
        self._set_cooldown(idx, "auth", self.AUTH_COOLDOWN)

    def is_available(self, idx: int) -> bool:
        entry = self._cooldown.get(idx)
        if not entry:
            return True
        if entry["kind"] == "auth":
            return False
        return time.time() > entry["until"]

    def rotate(self) -> bool:
        """Wechselt zum naechsten verfuegbaren Key. Gibt False zurueck wenn alle erschoepft."""
        for _ in range(len(self.keys)):
            self._active = (self._active + 1) % len(self.keys)
            if self.is_available(self._active):
                return True
        return False

    def reset_all(self):
        self._cooldown.clear()
        self._save()

    def status_lines(self) -> list[str]:
        now = time.time()
        lines = []
        for i, key in enumerate(self.keys):
            entry = self._cooldown.get(i)
            if not entry:
                tag = "OK"
            elif entry["kind"] == "auth":
                tag = "AUTH-FEHLER"
            elif now < entry["until"]:
                mins = int((entry["until"] - now) / 60)
                tag = f"cooldown {mins}min ({entry['kind']})"
            else:
                tag = "OK (cooldown abgelaufen)"
            marker = " <--" if i == self._active else ""
            lines.append(f"  Key {i:2d}: ...{key[-6:]}{marker}  [{tag}]")
        return lines

    # -- Internal --

    def _set_cooldown(self, idx: int, kind: str, duration: float):
        self._cooldown[idx] = {"until": time.time() + duration, "kind": kind}
        self._save()

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._state_file), exist_ok=True)
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump(self._cooldown, f)
        except Exception:
            pass

    def _load(self):
        if not os.path.exists(self._state_file):
            return
        try:
            raw = json.load(open(self._state_file, encoding="utf-8"))
            # int-keys nach JSON-Load sind strings
            self._cooldown = {int(k): v for k, v in raw.items() if isinstance(v, dict)}
        except Exception:
            self._cooldown = {}


# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------

SYSTEM_INSTRUCTION = """Du bist Sonu — ein autonomer Engineering-Agent im Terminal von Shubham Jayswal.

## Verhalten

**Denke zuerst, handle dann.** Bevor du Code schreibst oder Dateien aenderst: lies zuerst den relevanten Code (`grep_search` -> `read_file` mit Zeilenangaben). Aendere nie blind.

**Sei ehrlich ueber Unsicherheit.** Wenn du dir nicht sicher bist, sage es. Kein Erfinden von APIs, Pfaden oder Verhalten. Verifiziere mit Tools.

**Chirurgische Edits bevorzugen.** `replace` > `write_file`. Aendere nur was noetig ist. Keine unnötigen Umstrukturierungen nebenbei.

**Antworte kurz und praezise.** Keine langen Einleitungen. Direkt zum Punkt. Auf Deutsch, ausser der Nutzer schreibt Englisch.

**Validiere nach Aenderungen.** Nach Code-Edits: `run_shell("python -c 'import ast; ast.parse(open(\"file.py\").read())'")` oder Tests ausfuehren.

**Secrets niemals loggen oder committen.** `.env`, API-Keys, Passwoerter bleiben lokal.

## Tool-Strategie

Suche -> Lies -> Plane -> Handle -> Validiere

- **Finde Code**: `grep_search(pattern, context=3)` dann `read_file(path, start, end)`
- **Editiere**: `replace` fuer chirurgische Aenderungen, `write_file` nur fuer neue Dateien
- **Fuehre aus**: `run_shell` fuer Tests, Builds, Git-Status
- **Rechne/Teste**: `run_python` fuer Berechnungen, Datenanalyse, schnelle Tests
- **Recherchiere**: `google_search` fuer Fehler/Docs, `web_fetch` fuer spezifische URLs
- **Delegiere**: `delegate_to_subagent` wenn parallele Analyse sinnvoll ist

## Qualitaetsstandards

- Bestehende Konventionen des Projekts uebernehmen (Stil, Struktur, Benennung)
- Typen und Fehlerbehandlung nur wo noetig
- Keine Kommentare die das Offensichtliche erklaeren
- Bei Bugs: Root Cause finden, nicht Symptome pflastern
"""


# ---------------------------------------------------------------------------
# SonuClient — Kernklasse, analog zu GeminiChat + Turn in Gemini CLI
# ---------------------------------------------------------------------------

class SonuClient:

    # Modell-Kette: erst 2.5-flash, bei Quota-Erschoepfung → 2.0-flash
    MODEL_CHAIN = ["gemini-2.5-flash", "gemini-2.0-flash"]

    # Backoff wie Gemini CLI retry.ts: initialDelay=5s, max=30s, exponentiell
    BACKOFF = [5, 10, 20, 30]

    def __init__(self, model_name: str | None = None):
        _base = os.path.dirname(os.path.abspath(__file__))
        load_dotenv(os.path.join(_base, ".env"), override=True)

        # Keys laden
        keys = self._load_keys(_base)
        if not keys:
            raise RuntimeError("Kein Gemini API-Key gefunden. Bitte GEMINI_API_KEY oder GEMINI_KEY_FILE setzen.")

        state_file = os.path.join(_base, "logs", "keys_cooldown.json")
        self._pool = KeyPool(keys, state_file)

        # Modell
        self.model_name = model_name or os.getenv("GEMINI_MODEL", self.MODEL_CHAIN[0])

        # Gemini SDK Client + Chat
        self._client = None
        self._chat = None
        self._current_key_index = -1  # erzwingt Init beim ersten Call

        # Lazy module instances
        self._process_mgr = None
        self._skills_mgr = None
        self._plan_mode = None

        # YOLO-Modus
        self._yolo = False

    # -- Oeffentliche Properties --

    @property
    def yolo(self) -> bool:
        return self._yolo

    @yolo.setter
    def yolo(self, val: bool):
        self._yolo = val

    @property
    def process_mgr(self):
        if self._process_mgr is None:
            from process_manager import ProcessManager
            self._process_mgr = ProcessManager()
        return self._process_mgr

    @property
    def skills_mgr(self):
        if self._skills_mgr is None:
            from skills_manager import SkillsManager
            self._skills_mgr = SkillsManager()
        return self._skills_mgr

    @property
    def plan_mode(self):
        if self._plan_mode is None:
            from plan_mode import PlanMode
            self._plan_mode = PlanMode()
        return self._plan_mode

    @property
    def key_pool(self) -> KeyPool:
        return self._pool

    # -- Hauptmethode: run_agent_turn --
    # Portiert von Gemini CLI Turn.run() + agent loop

    def run_agent_turn(self, user_input: str, ui, max_steps: int = 30) -> str:
        """
        Fuehrt einen vollen Agenten-Turn durch:
        1. send_message
        2. Tool-Calls ausfuehren
        3. Ergebnis senden
        4. Wiederholen bis kein Tool-Call mehr
        Exakt wie Gemini CLI turn.ts, nur mit Key-Rotation bei 429.
        """
        import tools as _tools

        self._ensure_client()
        ui.update_status(f"{self.model_name} · k{self._pool.active_index()}/{self._pool.count()} verarbeitet...")

        resp = self._send(user_input)
        collected_text = []

        for step in range(max_steps):
            # Text aus dieser Response sammeln
            t = self._text(resp)
            if t:
                collected_text.append(t)

            fcs = self._extract_function_calls(resp)

            if not fcs:
                # Kein Tool-Call mehr → fertig
                return "\n".join(collected_text) if collected_text else ""

            # Zwischen-Text anzeigen
            if t:
                ui.show_agent_status(t)
                collected_text.clear()  # wird schon angezeigt, nicht doppelt ausgeben

            # Tools ausfuehren
            response_parts = []
            for fc in fcs:
                name = fc.name
                args = dict(fc.args) if fc.args else {}

                ui.show_tool_call(name, args)

                if not self._yolo and not _tools.is_safe(name):
                    answer = ui.confirm_action(name, args)
                    result = _tools.dispatch(name, args) if answer else "[Abgelehnt vom Nutzer]"
                else:
                    result = _tools.dispatch(name, args)

                ui.show_tool_result(name, result)

                response_parts.append(
                    types.Part.from_function_response(
                        name=name,
                        response={"result": str(result)},
                    )
                )

            ui.update_status(f"{self.model_name} · k{self._pool.active_index()}/{self._pool.count()} verarbeitet...")
            resp = self._send(response_parts)

        return self._text(resp) or "\n".join(collected_text) or "(max_steps erreicht)"

    # -- Chat-Verwaltung --

    def reset_chat(self, history=None):
        """Startet einen neuen Chat (z.B. nach /clear)."""
        self._chat = None
        self._ensure_client()
        import tools as _tools
        self._chat = self._client.chats.create(
            model=self.model_name,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                tools=[_tools.get_tool_object()],
                temperature=0.0,
            ),
            history=history or [],
        )

    def get_history(self):
        if self._chat is None:
            return []
        try:
            return self._chat.get_history()
        except Exception:
            return []

    def set_model(self, model_name: str):
        """Wechselt das Modell und erstellt einen neuen Chat mit der alten History."""
        old_history = self.get_history()
        self.model_name = model_name
        self._client = None
        self._chat = None
        self._current_key_index = -1
        self._ensure_client()
        self.reset_chat(history=old_history)

    # -- Internes --

    def _load_keys(self, base_dir: str) -> list[str]:
        keys = []

        # 1. Key-Datei (bevorzugt, utf-8-sig entfernt BOM automatisch)
        key_file = os.getenv("GEMINI_KEY_FILE", "")
        if key_file:
            if not os.path.isabs(key_file):
                key_file = os.path.join(base_dir, key_file)
            if os.path.exists(key_file):
                try:
                    with open(key_file, "r", encoding="utf-8-sig") as f:
                        keys = [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]
                except Exception as e:
                    print(f"Fehler beim Laden der Key-Datei: {e}")

        # 2. Key-Pool aus .env
        if not keys:
            pool_str = os.getenv("GEMINI_KEY_POOL", "")
            if pool_str:
                keys = [k.strip() for k in pool_str.split(",") if k.strip()]

        # 3. Einzelner Key als Fallback
        if not keys:
            single = os.getenv("GEMINI_API_KEY", "")
            if single:
                keys = [single]

        return keys

    def _ensure_client(self):
        """Erstellt SDK-Client fuer den aktiven Key, falls noetig."""
        idx = self._pool.active_index()
        if self._client is not None and idx == self._current_key_index:
            return

        key = self._pool.active_key()
        if not key:
            raise QuotaExhaustedException(self.model_name, 0)

        from google import genai as _genai
        self._client = _genai.Client(api_key=key)
        self._current_key_index = idx
        self._chat = None  # Chat gehoert zum alten Key

    def _send(self, message) -> object:
        """
        Sendet eine Nachricht mit:
        - Key-Rotation bei 429/daily-quota (Sonu-spezifisch)
        - Exponential Backoff bei 5xx/rate-limit (wie Gemini CLI retry.ts)
        - Auth-Fehler → Key permanent deaktivieren, weiter mit naechstem
        """
        if self._chat is None:
            self.reset_chat()

        last_err: Exception | None = None  # noqa: F841
        # Aeussere Schleife: Keys durchprobieren
        keys_tried = 0
        while keys_tried < self._pool.count():
            # Innere Schleife: Backoff-Versuche pro Key (wie Gemini CLI)
            for attempt, delay_s in enumerate([0] + self.BACKOFF):
                if delay_s > 0:
                    time.sleep(delay_s)
                try:
                    resp = self._chat.send_message(message)
                    return resp
                except Exception as e:
                    last_err = e
                    err = str(e)

                    if _is_auth_error(err):
                        # Key permanent kaputt — direkt weiter zum naechsten
                        self._pool.mark_auth_failed(self._pool.active_index())
                        break  # aus Backoff-Schleife, rotate

                    if _is_daily_quota(err):
                        # Tages-Quota voll — naechsten Key
                        self._pool.mark_daily_exhausted(self._pool.active_index())
                        break

                    if _is_rate_error(err):
                        # RPM-Limit — kurz warten, dann gleichem Key nochmal
                        self._pool.mark_rate_limited(self._pool.active_index())
                        if attempt < len(self.BACKOFF):
                            continue  # Backoff-Loop weiter
                        break  # Backoff erschoepft → rotate

                    if _is_server_error(err):
                        # 5xx — Backoff wie Gemini CLI
                        if attempt < len(self.BACKOFF):
                            continue
                        break

                    # Unbekannter Fehler → sofort weiterwerfen
                    raise

            # Key wechseln
            if not self._pool.rotate():
                break  # Alle Keys erschoepft

            keys_tried += 1
            # Neuen Client + Chat fuer den neuen Key erstellen
            old_history = self.get_history()
            self._ensure_client()
            self.reset_chat(history=old_history)

        raise QuotaExhaustedException(self.model_name, self._pool.count())

    @staticmethod
    def _extract_function_calls(resp) -> list:
        """Extrahiert Function Calls robust aus der Response — wie Gemini CLI functionCalls()."""
        # Methode 1: direktes Attribut
        try:
            fcs = resp.function_calls
            if fcs:
                return list(fcs)
        except Exception:
            pass
        # Methode 2: ueber candidates.content.parts (zuverlaessiger bei gemischten Responses)
        try:
            parts = resp.candidates[0].content.parts
            return [p.function_call for p in parts if getattr(p, "function_call", None)]
        except Exception:
            return []

    @staticmethod
    def _text(resp) -> str:
        """Extrahiert Text aus einer Gemini-Response (wie getResponseText in Gemini CLI)."""
        # Methode 1: ueber parts — sicherer als resp.text das bei function_calls warnt
        try:
            parts = resp.candidates[0].content.parts
            texts = [p.text for p in parts if getattr(p, "text", None) and not getattr(p, "function_call", None)]
            if texts:
                return "".join(texts)
        except Exception:
            pass
        # Methode 2: resp.text als Fallback
        try:
            return resp.text or ""
        except Exception:
            return ""
