import os
import json
import time
import asyncio
import re
import concurrent.futures
from dotenv import load_dotenv


class QuotaExhaustedException(Exception):
    def __init__(self, model_name, key_count):
        self.model_name = model_name
        self.key_count = key_count
        super().__init__(
            f"Alle {key_count} API-Keys haben die Tagesquota für '{model_name}' erschöpft."
        )


# Lazy Proxy Classes for heavy SDK imports
class LazyGenaiProxy:
    def __getattr__(self, name):
        from google import genai
        return getattr(genai, name)

class LazyTypesProxy:
    def __getattr__(self, name):
        from google.genai import types
        return getattr(types, name)

genai = LazyGenaiProxy()
types = LazyTypesProxy()


import providers
import tools
from context_compressor import compress_gemini_history
from model_availability import ModelAvailabilityService, classify_error
from ai_classifier import AIClassifierRouter
from jit_context import discover_jit_context, append_jit_context, reset_session_cache, JIT_TRIGGER_TOOLS, extract_path_from_args
# Lazy imports for agents_swarm are moved inside property/methods

SYSTEM_INSTRUCTION = """Du bist Sonu — ein autonomer Engineering-Agent im Terminal von Shubham Jayswal.

## Verhalten

**Denke zuerst, handle dann.** Bevor du Code schreibst oder Dateien änderst: lies zuerst den relevanten Code (`grep_search` → `read_file` mit Zeilenangaben). Ändere nie blind.

**Sei ehrlich über Unsicherheit.** Wenn du dir nicht sicher bist, sage es. Kein Erfinden von APIs, Pfaden oder Verhalten. Verifiziere mit Tools.

**Chirurgische Edits bevorzugen.** `replace` > `write_file`. Ändere nur was nötig ist. Keine unnötigen Umstrukturierungen nebenbei.

**Antworte kurz und präzise.** Keine langen Einleitungen. Direkt zum Punkt. Auf Deutsch, außer der Nutzer schreibt Englisch.

**Validiere nach Änderungen.** Nach Code-Edits: `run_shell("python -c 'import ast; ast.parse(open(\"file.py\").read())'")` oder Tests ausführen.

**Secrets niemals loggen oder committen.** `.env`, API-Keys, Passwörter bleiben lokal.

## Tool-Strategie

Suche → Lies → Plane → Handle → Validiere

- **Finde Code**: `grep_search(pattern, context=3)` dann `read_file(path, start, end)`
- **Editiere**: `replace` für chirurgische Änderungen, `write_file` nur für neue Dateien
- **Führe aus**: `run_shell` für Tests, Builds, Git-Status
- **Rechne/Teste**: `run_python` für Berechnungen, Datenanalyse, schnelle Tests
- **Recherchiere**: `google_search` für Fehler/Docs, `web_fetch` für spezifische URLs
- **Delegiere**: `delegate_to_subagent` wenn parallele Analyse sinnvoll ist

## Qualitätsstandards

- Bestehende Konventionen des Projekts übernehmen (Stil, Struktur, Benennung)
- Typen und Fehlerbehandlung nur wo nötig — keine defensiven Wrapper für internen Code
- Keine Kommentare die das Offensichtliche erklären
- Bei Bugs: Root Cause finden, nicht Symptome pflastern
"""


class SonuClient:
    def __init__(self, model_name=None):
        self.provider = os.getenv("DEFAULT_PROVIDER", "gemini")
        self._orchestrator = None
        self._initialized = False
        from dotenv import load_dotenv
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        load_dotenv(env_path, override=True)

        self.api_key = os.getenv("GEMINI_API_KEY")
        key_pool_str = os.getenv("GEMINI_KEY_POOL", "")
        key_file = os.getenv("GEMINI_KEY_FILE", "")

        self.keys = []
        # Resolve key_file relative to the script directory, not CWD
        _script_dir = os.path.dirname(os.path.abspath(__file__))
        if key_file and not os.path.isabs(key_file):
            key_file = os.path.join(_script_dir, key_file)
        if key_file and os.path.exists(key_file):
            try:
                with open(key_file, "r", encoding="utf-8-sig") as f:
                    self.keys = [line.strip() for line in f if line.strip()]
            except Exception as e:
                print(f"[bold red]Fehler beim Laden der Key-Datei: {e}[/bold red]")

        if not self.keys and key_pool_str:
            self.keys = [k.strip() for k in key_pool_str.split(",") if k.strip()]

        if self.keys:
            # Kybernetische Lastenverteilung fuer Multi-Instanz-Szenarien
            instance_id_str = os.getenv("SONU_INSTANCE_ID")
            if instance_id_str:
                try:
                    inst_id = int(instance_id_str)
                    shift = inst_id % len(self.keys)
                    self.keys = self.keys[shift:] + self.keys[:shift]
                except ValueError:
                    pass
        else:
            self.keys = [self.api_key] if (self.api_key and len(self.api_key) > 5) else []

        self.active_index = 0
        self._key_cooldowns = {}
        self._key_request_times: dict = {}
        self._RPM_LIMIT = 12
        self._shared_cooldown_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "keys_cooldown.json")
        self._availability = ModelAvailabilityService(self._shared_cooldown_file)
        self._ai_classifier = AIClassifierRouter()
        self._current_turn_budget = 4096

        if self.api_key in self.keys:
            self.active_index = self.keys.index(self.api_key)
        elif self.keys:
            self.api_key = self.keys[0]
            print(f"[dim]Note: Active key was empty/invalid, rotated to pool key {self.active_index+1}[/dim]")

        # Private Attribute fuer Lazy Properties initialisieren
        self._skills_mgr = None
        self._process_mgr = None
        self._memory_mgr = None
        self._storage_mgr = None
        self._living_docs = None
        self._health_monitor = None
        self._predictive = None
        self._redundancy_mgr = None
        self._ghost = None
        self._swarm = None
        self._personality = None
        self._temporal_mem = None
        self._router = None
        self._todo_mgr = None
        self._plan_mode = None

        self._config_cache = None  # invalidated only on skill change

        self._client = None
        self._chat = None
        self.oa_agents = {}

        # Standard-Provider initialisieren
        self.provider = os.getenv("DEFAULT_PROVIDER", "gemini")

        # Modell-Name initialisieren (ohne providers zu importieren, wenn möglich)
        # Wir laden den Provider-Namen lazy
        self._model_name = model_name

    @property
    def provider(self):
        if not hasattr(self, "_provider"):
            self._provider = os.getenv("DEFAULT_PROVIDER", "gemini")
        return self._provider

    @provider.setter
    def provider(self, value):
        self._provider = value

    @property
    def model_name(self):
        if self._model_name is None:
            import providers
            default_prov = os.getenv("DEFAULT_PROVIDER", "gemini")
            prov_info = providers.get_provider(default_prov)
            self._model_name = prov_info["default_model"]
        return self._model_name

    @model_name.setter
    def model_name(self, value):
        self._model_name = value

    @property
    def client(self):
        if self._client is None and self.api_key:
             from google import genai
             self._client = genai.Client(api_key=self.api_key)
        return self._client

    @client.setter
    def client(self, value):
        self._client = value

    @property
    def chat(self):
        if self._chat is None:
            self.reset_chat()
        return self._chat

    @chat.setter
    def chat(self, value):
        self._chat = value

    @property
    def skills_mgr(self):

        if self._skills_mgr is None:
            from skills_manager import SkillsManager
            self._skills_mgr = SkillsManager()
        return self._skills_mgr

    @property
    def process_mgr(self):
        if self._process_mgr is None:
            from process_manager import ProcessManager
            self._process_mgr = ProcessManager()
            import tools
            tools.set_process_manager(self._process_mgr)
        return self._process_mgr

    @property
    def memory_mgr(self):
        if self._memory_mgr is None:
            from memory_manager import MemoryManager
            self._memory_mgr = MemoryManager()
        return self._memory_mgr

    @property
    def storage_mgr(self):
        if self._storage_mgr is None:
            from storage import StorageManager
            self._storage_mgr = StorageManager()
        return self._storage_mgr

    @property
    def living_docs(self):
        if self._living_docs is None:
            from living_docs import LivingDocs
            self._living_docs = LivingDocs()
        return self._living_docs

    @property
    def health_monitor(self):
        if self._health_monitor is None:
            from health_monitor import HealthMonitor
            self._health_monitor = HealthMonitor(
                process_manager=self.process_mgr,
                memory_manager=self.memory_mgr,
            )
            self._health_monitor.start()
        return self._health_monitor

    @property
    def predictive(self):
        if self._predictive is None:
            from predictive_debugger import PredictiveDebugger
            self._predictive = PredictiveDebugger(log_path=self.health_monitor.log_path)
        return self._predictive

    @property
    def redundancy_mgr(self):
        if self._redundancy_mgr is None:
            from redundancy_manager import RedundancyManager
            self._redundancy_mgr = RedundancyManager(self)
        return self._redundancy_mgr

    @property
    def ghost(self):
        if self._ghost is None:
            from ghost_integrator import GhostIntegrator
            self._ghost = GhostIntegrator(
                repo_path=os.path.dirname(os.path.abspath(__file__)),
            )
            self._ghost.inject_client(self)
        return self._ghost

    @property
    def swarm(self):
        if self._swarm is None:
            from swarm_consensus import SwarmConsensus
            self._swarm = SwarmConsensus(self)
        return self._swarm

    @property
    def personality(self):
        if self._personality is None:
            from personality_engine import PersonalityEngine
            self._personality = PersonalityEngine()
        return self._personality

    @property
    def temporal_mem(self):
        if self._temporal_mem is None:
            from temporal_memory import TemporalMemory
            self._temporal_mem = TemporalMemory()
        return self._temporal_mem

    @property
    def router(self):
        if self._router is None:
            from smart_router import SmartRouter
            self._router = SmartRouter()
        return self._router

    @property
    def todo_mgr(self):
        if self._todo_mgr is None:
            from todo_manager import TodoManager
            self._todo_mgr = TodoManager()
        return self._todo_mgr

    @property
    def plan_mode(self):
        if self._plan_mode is None:
            from plan_mode import PlanMode
            self._plan_mode = PlanMode()
        return self._plan_mode

    def active_key_num_str(self) -> str:
        """Gibt RPM-Auslastung des aktiven Keys als String zurück (für UI)."""
        rpm = self._key_rpm(self.active_index)
        return f"{rpm}rpm"

    def set_provider(self, name):
        prov_info = providers.get_provider(name)
        if not prov_info:
            return False, f"Unbekannter Provider: {name}"

        env_var = prov_info["env_var"]
        if env_var is not None and not os.getenv(env_var):
            return False, f"Kein API Key gefunden fuer {name}. Setze {env_var} in .env"

        self.provider = name
        self.model_name = prov_info["default_model"]

        if prov_info["kind"] == "openai":
            if name not in self.oa_agents:
                try:
                    from openai_agent import OpenAICompatibleAgent
                    from openai_agent import OpenAICompatibleAgent
                    self.oa_agents[name] = OpenAICompatibleAgent(name, self.model_name, self)
                except Exception as e:
                    return False, f"Fehler beim Initialisieren von {name}: {e}"
            else:
                self.oa_agents[name].model = self.model_name
                self.oa_agents[name]._build_system_message() # rebuild memory context

        elif prov_info["kind"] == "gemini":
            if not self.client:
                return False, "Gemini Client ist nicht konfiguriert (Key fehlt)."
            self.reset_chat()

        return True, f"Provider gewechselt zu {name}. Standardmodell: {self.model_name}"

    def _skill_tool(self):
        from google.genai import types
        """Zusatz-Tool, mit dem der Agent selbst ein Skill-Profil aktivieren kann."""
        names = self.skills_mgr.list_skills()
        desc = (
            "Aktiviert ein Experten-Skill-Profil, das deinen Fokus, deine Methodik und deinen Ton umstellt. "
            "Mit name='off' deaktivierst du das aktive Skill. Verfuegbare Skills: "
            + (", ".join(names) if names else "(keine)")
        )
        return types.Tool(function_declarations=[types.FunctionDeclaration(
            name="activate_skill",
            description=desc,
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={"name": types.Schema(type=types.Type.STRING, description="Name des zu aktivierenden Skills, oder 'off' zum Deaktivieren.")},
                required=["name"],
            ),
        )])

    def _scrub_sensitive_data(self, text: str) -> str:
        if text is None:
            return ""
        import re
        # Names
        text = text.replace('Shubham Jayswal', 'Lead Systems Architect')
        text = text.replace('Shubham', 'Developer')
        text = text.replace('Jayswal', 'Architect')

        # Paths - Keep Windows format so Sonu generates correct shell commands
        text = re.sub(r'C:\\Users\\[^\\]+\\sonu-cli-advanced', r'C:\\Users\\developer\\workspace', text, flags=re.IGNORECASE)
        text = re.sub(r'C:\\Users\\[^\\]+', r'C:\\Users\\developer', text, flags=re.IGNORECASE)

        return text

    def _get_git_context(self) -> str:
        """Gibt aktuellen Git-Kontext zurück: Branch, staged/unstaged changes, letzte Commits."""
        try:
            import subprocess
            def _git(cmd):
                r = subprocess.run(["git"] + cmd, capture_output=True, text=True, timeout=5,
                                   cwd=os.getcwd())
                return r.stdout.strip() if r.returncode == 0 else ""

            branch = _git(["rev-parse", "--abbrev-ref", "HEAD"])
            if not branch:
                return ""
            # Nur getrackte Änderungen, keine untracked Files (kann hunderte sein)
            status = _git(["status", "--short", "--untracked-files=no"])
            log = _git(["log", "--oneline", "-3"])

            parts = [f"Branch: {branch}"]
            if status:
                lines = status.splitlines()[:15]
                parts.append("Geändert:\n" + "\n".join(lines))
            if log:
                parts.append(f"Letzte Commits:\n{log}")
            return "\n".join(parts)
        except Exception:
            return ""

    def _build_config(self):
        from google.genai import types
        if self._config_cache is not None:
            return self._config_cache

        # 1. 4-Level Gedaechtnis abrufen (einmalig pro Session / Skill-Wechsel)
        mem_context = self.memory_mgr.load_memory(os.getcwd())
        ltm_context = self.temporal_mem.get_all_memories()

        # Cross-project typed memory
        xmem_context = ""
        try:
            from cross_project_memory import load_all_memories
            xmem_context = load_all_memories()
        except Exception:
            pass

        # 2. Aktiven Experten-Skill laden
        active_instruction = SYSTEM_INSTRUCTION
        if self.skills_mgr.active_skill:
            try:
                skill_content = self.skills_mgr.activate_skill(self.skills_mgr.active_skill)
                active_instruction += (
                    f"\n\n=== ERWÄHLTE EXPERTEN-SKILL-REGELN ({self.skills_mgr.active_skill}) ===\n"
                    f"{skill_content}\n"
                )
            except Exception:
                pass

        # 3. Systemkontext assemblieren
        style_instruction = self.personality.get_style_instruction()
        git_context = self._get_git_context()
        full_sys_prompt = (
            f"{active_instruction}\n\n"
            f"=== KOMMUNIKATIONSSTIL ===\n"
            f"{style_instruction}\n\n"
            f"=== LANGZEITGEDÄCHTNIS (LTM) ===\n"
            f"{ltm_context}\n\n"
            f"=== ERMITTELTER SYSTEMKONTEXT (4-EBENEN-GEDÄCHTNIS) ===\n"
            f"{mem_context}\n"
        )
        if xmem_context:
            full_sys_prompt += f"\n=== CROSS-PROJECT MEMORY (~/.sonu/memory/) ===\n{xmem_context}\n"
        if git_context:
            full_sys_prompt += f"\n=== GIT WORKSPACE ===\n{git_context}\n"
        todo_context = self.todo_mgr.format_for_prompt()
        if todo_context:
            full_sys_prompt += f"\n{todo_context}\n"
        if self.plan_mode.active:
            full_sys_prompt += self.plan_mode.get_system_addon()

        full_sys_prompt = self._scrub_sensitive_data(full_sys_prompt)

        config = types.GenerateContentConfig(
            system_instruction=full_sys_prompt,
            tools=[tools.get_tool_object(), self._skill_tool()],
            thinking_config=types.ThinkingConfig(thinking_budget=8192),
        )
        # Only cache when no dynamic context (todo/plan) is active
        if not todo_context and not self.plan_mode.active:
            self._config_cache = config
        return config

    def _rebuild_preserving_history(self):
        """Baut die Chat-Session neu auf (z.B. nach Skill-Wechsel), ohne den Verlauf zu verlieren."""
        old_history = None
        try:
            old_history = self.chat.get_history() if self.chat else None
        except Exception:
            old_history = None
        self.reset_chat(history=old_history)

    def set_skill(self, name):
        """Aktiviert/deaktiviert ein Skill und baut den Prompt neu auf. Gibt (ok, nachricht)."""
        self._config_cache = None  # invalidate so _build_config() rebuilds with new skill
        if name in (None, "", "none", "clear", "off", "aus", "deactivate"):
            self.skills_mgr.deactivate_skill()
            self._rebuild_preserving_history()
            return True, "Skill deaktiviert. Zurueck zum Baseline-Modus."
        try:
            self.skills_mgr.activate_skill(name)
        except Exception:
            avail = ", ".join(self.skills_mgr.list_skills()) or "(keine)"
            return False, f"Skill '{name}' nicht gefunden. Verfuegbar: {avail}"
        self._rebuild_preserving_history()
        return True, f"Skill '{name}' aktiviert."

    def reset_chat(self, history=None):
        """Initialisiert oder resettet die Chat-Session, optional mit erhaltenem Verlauf."""
        try:
            self.chat = self.client.chats.create(
                model=self.model_name,
                config=self._build_config(),
                history=history,
            )
        except Exception as e:
            raise Exception(f"Fehler beim Erstellen des Chats fuer Modell '{self.model_name}': {str(e)}")

    @staticmethod
    def _is_rate_limit_error(error_str: str) -> bool:
        """429-class: key rotation + backoff is the correct response."""
        s = error_str.lower()
        return any(k in s for k in [
            "quota", "rate limit", "resource_exhausted", "429", "limit reached",
        ])

    @staticmethod
    def _is_auth_error(error_str: str) -> bool:
        """403-class: key revoked/blocked — evict from pool, do NOT rotate blindly."""
        s = error_str.lower()
        return any(k in s for k in [
            "api key expired", "api_key_invalid", "permission_denied",
            "api key not valid", "403", "forbidden", "insufficient permissions",
        ])

    @staticmethod
    def _is_quota_error(error_str: str) -> bool:
        """Legacy shim: True if either rate-limit or auth error (used by upstream callers)."""
        return (
            SonuClient._is_rate_limit_error(error_str)
            or SonuClient._is_auth_error(error_str)
        )

    @staticmethod
    def _is_server_error(error_str: str) -> bool:
        s = error_str.lower()
        return any(k in s for k in ["503", "high demand", "unavailable", "server error", "500", "502", "504"])

    def _load_shared_cooldowns(self):
        """Lädt Cooldowns von anderen Instanzen aus der gemeinsamen Datei."""
        if not os.path.exists(self._shared_cooldown_file):
            return {}
        try:
            with open(self._shared_cooldown_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Bereinige abgelaufene Einträge
            now = time.time()
            return {k: v for k, v in data.items() if v > now}
        except Exception:
            return {}

    def _save_shared_cooldown(self, key, expiry):
        """Speichert einen neuen Cooldown-Eintrag in der gemeinsamen Datei."""
        os.makedirs(os.path.dirname(self._shared_cooldown_file), exist_ok=True)
        # Lock-frei (einfaches Überschreiben ist hier akzeptabel, da Race-Conditions nur zu redundanten Cooldowns führen)
        try:
            data = self._load_shared_cooldowns()
            data[key] = expiry
            with open(self._shared_cooldown_file, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass

    def _is_key_healthy(self, key_index: int) -> bool:
        if not (0 <= key_index < len(self.keys)):
            return False
        return self._availability.is_available(key_index, self.model_name)

    def _record_request(self, key_index: int):
        """Merkt sich den Zeitpunkt eines Requests für RPM-Tracking."""
        if not (0 <= key_index < len(self.keys)):
            return
        key = self.keys[key_index]
        now = time.time()
        times = self._key_request_times.get(key, [])
        times = [t for t in times if now - t < 60.0]  # nur letzten 60s behalten
        times.append(now)
        self._key_request_times[key] = times

    def _key_rpm(self, key_index: int) -> int:
        """Gibt die aktuelle RPM-Nutzung eines Keys zurück."""
        if not (0 <= key_index < len(self.keys)):
            return 0
        key = self.keys[key_index]
        now = time.time()
        times = self._key_request_times.get(key, [])
        return sum(1 for t in times if now - t < 60.0)

    def _is_key_rpm_safe(self, key_index: int) -> bool:
        """True wenn Key noch unter dem RPM-Proaktiv-Limit liegt."""
        return self._key_rpm(key_index) < self._RPM_LIMIT

    def _mark_key_exhausted(self, key_index: int, duration: float = 30.0, err_str: str = ""):
        if 0 <= key_index < len(self.keys):
            if err_str:
                self._availability.mark_failure_from_error(key_index, self.model_name, err_str)
            else:
                kind = "quota" if duration >= 3600 else "quota"
                self._availability.mark_failure(key_index, self.model_name, kind, duration)
            print(f"\n[Key {key_index + 1}/{len(self.keys)} cooldown {duration:.0f}s]")

    def rotate_key(self):
        """Rotiere zum naechsten gesunden Key im Pool, erhaelt den Gespraechsverlauf.
        Gibt False zurück wenn kein gesunder Key mehr verfügbar ist."""
        if len(self.keys) <= 1:
            return False

        old_history = None
        try:
            old_history = self.chat.get_history() if self.chat else None
        except Exception:
            old_history = None

        start_idx = self.active_index
        found = False
        while True:
            self.active_index = (self.active_index + 1) % len(self.keys)
            if self._is_key_healthy(self.active_index):
                found = True
                break
            if self.active_index == start_idx:
                break  # voller Kreis — kein gesunder Key

        if not found:
            return False  # KRITISCH: alle Keys erschöpft, sofort abbrechen

        new_key = self.keys[self.active_index]
        self.api_key = new_key
        self._rotate_ip_or_proxy()
        from google import genai
        self.client = genai.Client(api_key=new_key)
        self.reset_chat(history=old_history)
        return True

    def _rotate_ip_or_proxy(self):
        """Rotiert die Egress-IP-Adresse über Tor oder einen konfigurierten Proxy-Pool."""
        import os

        # 1. Tor-Rotation falls aktiviert
        if os.getenv("TOR_ROTATION", "").lower() == "true":
            try:
                from stem import Signal
                from stem.control import Controller
                tor_port = int(os.getenv("TOR_CONTROL_PORT", "9051"))
                tor_pw = os.getenv("TOR_PASSWORD", "")

                with Controller.from_port(port=tor_port) as controller:
                    if tor_pw:
                        controller.authenticate(password=tor_pw)
                    else:
                        controller.authenticate()
                    controller.signal(Signal.NEWNYM)

                # httpx (google-genai intern) akzeptiert socks5:// NUR über ALL_PROXY + socksio
                os.environ["ALL_PROXY"] = "socks5://127.0.0.1:9050"
                os.environ.pop("HTTP_PROXY", None)
                os.environ.pop("HTTPS_PROXY", None)
                print(f"\n[Anonymisierung] Tor-Route erfolgreich neu aufgebaut. Neue IP aktiv.")
                return
            except Exception as e:
                print(f"\n[Warnung] Tor-Rotation fehlgeschlagen: {e}. Prüfe ob Tor auf Port 9051 läuft.")

        # 2. Proxy-Pool Rotation falls konfiguriert
        proxy_pool_str = os.getenv("PROXY_POOL", "")
        if proxy_pool_str:
            try:
                proxies = [p.strip() for p in proxy_pool_str.split(",") if p.strip()]
                if proxies:
                    active_proxy = proxies[self.active_index % len(proxies)]
                    # Authentifizierung im Proxy-String berücksichtigen (z.B. user:pass@ip:port oder ip:port)
                    if "@" not in active_proxy and len(active_proxy.split(":")) == 4:
                        parts = active_proxy.split(":")
                        active_proxy = f"{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"

                    proxy_url = f"http://{active_proxy}" if not active_proxy.startswith("http") else active_proxy
                    os.environ["HTTP_PROXY"] = proxy_url
                    os.environ["HTTPS_PROXY"] = proxy_url
                    print(f"\n[Anonymisierung] Egress-Proxy rotiert zu: {active_proxy.split('@')[-1]}")
                    return
            except Exception as e:
                print(f"\n[Warnung] Proxy-Rotation fehlgeschlagen: {e}")

    def _evict_key_from_env_file(self, bad_key):
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        if not os.path.exists(env_path):
            return
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            new_lines = []
            for line in lines:
                stripped = line.lstrip()
                if stripped.startswith("GEMINI_KEY_POOL="):
                    pool_val = stripped.split("=", 1)[1].strip()
                    keys_in_pool = [k.strip() for k in pool_val.split(",") if k.strip()]
                    if bad_key in keys_in_pool:
                        keys_in_pool.remove(bad_key)
                    new_lines.append(f"GEMINI_KEY_POOL={','.join(keys_in_pool)}\n")
                else:
                    new_lines.append(line)
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
        except Exception:
            pass

    def _evict_current_key(self):
        """Entfernt den aktuell aktiven Key aus dem Pool (403/revoked). Kein Backoff — Key ist dauerhaft ungueltig."""
        if not self.keys:
            return
        bad_key = self.keys[self.active_index]
        self._evict_key_from_env_file(bad_key)

        old_history = None
        try:
            old_history = self.chat.get_history() if self.chat else None
        except Exception:
            old_history = None
        self.keys.pop(self.active_index)
        if not self.keys:
            self.api_key = None
            self.client = None
            self._update_env_file("")
            return
        self.active_index = self.active_index % len(self.keys)
        self.api_key = self.keys[self.active_index]
        self._update_env_file(self.api_key)
        from google import genai
        self.client = genai.Client(api_key=self.api_key)
        try:
            self.reset_chat(history=old_history)
        except Exception:
            pass

    def _update_env_file(self, new_key):
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        if not os.path.exists(env_path):
            return
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            with open(env_path, "w", encoding="utf-8") as f:
                for line in lines:
                    if line.lstrip().startswith("GEMINI_API_KEY="):
                        f.write(f"GEMINI_API_KEY={new_key}\n")
                    else:
                        f.write(line)
        except Exception:
            pass

    def _send_with_rotation(self, message):
        """Sendet eine Nachricht mit proaktivem Token-Pacing und Fallback-Rotation."""
        # 1. Proaktive Rotation bei hoher Auslastung (Token-Budgeting für 30min-Fenster)
        # Wir prüfen, ob der aktuelle Key in den letzten 30 Min schon viel konsumiert hat
        pass

        if not self._is_key_healthy(self.active_index):
            if not self.rotate_key():
                raise QuotaExhaustedException(self.model_name, len(self.keys))

        if not self.chat:
            self.reset_chat()

        backoff_schedule = [2, 4, 8]

        last_error = None
        for attempt in range(len(backoff_schedule) + 1):
            for key_idx in range(max(1, len(self.keys))):
                try:
                    if not self._is_key_healthy(self.active_index):
                        if not self.rotate_key():
                            raise QuotaExhaustedException(self.model_name, len(self.keys))

                    start_time = time.time()
                    resp = self.chat.send_message(message)
                    latency = (time.time() - start_time) * 1000

                    prompt_tokens = getattr(resp.usage_metadata, "prompt_token_count", 0) if resp.usage_metadata else 0
                    completion_tokens = getattr(resp.usage_metadata, "candidates_token_count", 0) if resp.usage_metadata else 0

                    self._record_request(self.active_index)
                    if prompt_tokens or completion_tokens:
                        self.storage_mgr.log_token_usage(
                            provider=self.provider,
                            model=self.model_name,
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            latency_ms=latency
                        )
                        # Auto-Komprimierung bei ~80% Context-Nutzung (1M Token Limit)
                        self._auto_compress_if_needed(prompt_tokens)
                    return resp
                except Exception as e:
                    last_error = e
                    err_str = str(e)
                    if self._is_rate_limit_error(err_str):
                        # Tages-Quota? Dann 1h Cooldown statt 65s
                        is_daily = any(w in err_str.lower() for w in ["daily", "per day", "day quota", "exceeded your"])
                        cooldown = 3600.0 if is_daily else 65.0
                        self._mark_key_exhausted(self.active_index, duration=cooldown)
                        if self.rotate_key(): continue
                        raise QuotaExhaustedException(self.model_name, len(self.keys))
                    elif self._is_auth_error(err_str):
                        self._evict_current_key()
                        if not self.keys: raise QuotaExhaustedException(self.model_name, 0)
                        continue
                    elif self._is_server_error(err_str):
                        self._mark_key_exhausted(self.active_index, duration=30.0)
                        if self.rotate_key(): continue
                        break
                    else: raise

            if last_error and attempt < len(backoff_schedule):
                time.sleep(backoff_schedule[attempt])
                continue
            if last_error: raise last_error

    def send_message_stream(self, message):
        """Sendet eine Nachricht als Stream mit Backoff und Key-Rotation."""
        # Proaktive Rotation
        self._rotate_to_next_key(silent=True)

        if not self.chat:
            self.reset_chat()

        backoff_schedule = [2, 4, 8]

        for attempt in range(len(backoff_schedule) + 1):
            try:
                for _ in range(max(1, len(self.keys))):
                    try:
                        response_stream = self.chat.send_message_stream(message)
                        iterator = iter(response_stream)

                        # Erste Antwort abfragen, um Quota sofort zu testen
                        first_chunk = next(iterator)

                        def stream_generator():
                            yield first_chunk
                            for chunk in iterator:
                                yield chunk
                        return stream_generator()
                    except StopIteration:
                        def empty_generator():
                            yield from []
                        return empty_generator()
                    except Exception as e:
                        err_str = str(e)
                        if self._is_rate_limit_error(err_str) and len(self.keys) > 1:
                            self._mark_key_exhausted(self.active_index, duration=65.0)
                            if self.rotate_key():
                                continue
                        elif self._is_auth_error(err_str):
                            self._evict_current_key()
                            if self.keys:
                                continue
                        raise
            except Exception as e:
                err_str = str(e)
                if self._is_server_error(err_str) and attempt < len(backoff_schedule):
                    time.sleep(backoff_schedule[attempt])
                    continue
                raise e

        return None

    def _get_fallback_providers(self):
        """Findet alle Provider mit gültigem Key, außer dem aktuellen.
        Ollama wird nur einbezogen wenn localhost:11434 erreichbar ist."""
        available = []
        for p in providers.list_providers():
            if p == self.provider:
                continue
            prov_info = providers.get_provider(p)
            if prov_info["env_var"] is None:
                # Offline-Provider (Ollama): nur wenn wirklich erreichbar
                if p == "ollama":
                    import socket
                    try:
                        socket.create_connection(("127.0.0.1", 11434), timeout=0.5)
                    except OSError:
                        continue  # Ollama nicht aktiv → überspringen
                available.append(p)
            elif os.getenv(prov_info["env_var"]):
                available.append(p)
        return available

    def _check_internet_connection(self):
        now = time.time()
        if hasattr(self, '_last_net_check') and now - self._last_net_check < 60:
            return self._is_online_cache

        import socket
        try:
            # Versuche, eine Verbindung zu einem zuverlaessigen Server herzustellen
            socket.create_connection(("1.1.1.1", 53), timeout=1.5)
            self._is_online_cache = True
        except OSError:
            self._is_online_cache = False

        self._last_net_check = now
        return self._is_online_cache

    def _start_groq_parallel(self, user_input):
        """Startet Groq aggressiv im Hintergrund.
        Gibt (thread, result_container) zurück.
        """
        import threading
        result = [None]
        if not os.getenv("GROQ_API_KEY") or self.provider != "gemini":
            return None, result

        def _worker():
            try:
                # Schnellste Llama-Version für Instant-Feedback
                model = "llama-3.3-70b-versatile"
                if "groq" not in self.oa_agents:
                    from openai_agent import OpenAICompatibleAgent
                    self.oa_agents["groq"] = OpenAICompatibleAgent("groq", model, self)

                agent = self.oa_agents["groq"]
                # Nur die letzten paar Nachrichten für Geschwindigkeit
                short_history = agent.messages[-6:] if len(agent.messages) > 6 else agent.messages
                msgs = list(short_history) + [{"role": "user", "content": user_input}]

                resp = agent.client.chat.completions.create(
                    model=model,
                    messages=msgs,
                    max_tokens=800,
                    timeout=15,
                )
                res_text = (resp.choices[0].message.content or "").strip()
                result[0] = res_text

                # Optional: UI über schnelles Ergebnis informieren
                if hasattr(self, 'ui') and self.ui:
                     # Wir zeigen es nur an, wenn Gemini noch arbeitet
                     pass
            except Exception:
                result[0] = None

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        return t, result

    @property
    def orchestrator(self):
        if self._orchestrator is None:
            from agents_swarm.orchestrator import SwarmOrchestrator
            self._orchestrator = SwarmOrchestrator()
        return self._orchestrator

    # Free-Tier-Schonung: bei diesem Prompt-Token-Stand History komprimieren,
    # damit nicht jeder Turn die Tagesquota (~1M/Tag pro Key) auffrisst.
    _COMPRESS_AT_TOKENS = 40_000

    def _auto_compress_if_needed(self, prompt_tokens: int):
        """Komprimiert den Gesprächsverlauf wenn der Prompt zu groß wird."""
        if prompt_tokens < self._COMPRESS_AT_TOKENS:
            return
        try:
            history = self.chat.get_history() if self.chat else []
            if len(history) < 4:
                return
            compressed = compress_gemini_history(history, self.model_name, self.client)
            if compressed and len(compressed) < len(history):
                self.reset_chat(history=compressed)
                saved = len(history) - len(compressed)
                print(f"\n[dim]Auto-Komprimierung: {len(history)} → {len(compressed)} Turns (-{saved})[/dim]")
        except Exception:
            pass

    def _lazy_init(self):
        if not self._initialized:
            from agents_swarm.meta_learning_hook import start_meta_learning
            try:
                start_meta_learning()
            except Exception:
                pass
            # Workspace im Hintergrund indexieren (non-blocking)
            import threading
            threading.Thread(target=self._index_workspace_bg, daemon=True).start()
            self._initialized = True

    def _index_workspace_bg(self):
        """Indexiert den aktuellen Workspace im Hintergrund für semantische Suche."""
        try:
            from agents_swarm.vector_memory import VectorMemory
            vm = VectorMemory()
            root = os.path.dirname(os.path.abspath(__file__))
            vm.index_workspace(root)
        except Exception:
            pass

    def get_workspace_context(self, query: str) -> str:
        """Gibt relevante Workspace-Snippets für eine Anfrage zurück."""
        try:
            from agents_swarm.vector_memory import VectorMemory
            vm = VectorMemory()
            return vm.query_summary(query, n_results=4)
        except Exception:
            return ""

    def save_session(self, session_turns: list, topic: str = ""):
        """Speichert Session-Learnings ins persistente Gedächtnis."""
        try:
            self.memory_mgr.save_session_learnings(session_turns, topic)
        except Exception:
            pass

    async def run_agent_turn_async(self, user_input, ui, max_steps=25):
        """Asynchrone Version der Agenten-Ausführung."""
        self._lazy_init()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.run_agent_turn, user_input, ui, max_steps)

    def run_agent_turn(self, user_input, ui, max_steps=25):
        """Wrapper fuer den Agent-Loop mit kaskadierendem automatischem Provider-Fallback.
        Versucht alle verfuegbaren Provider nacheinander, bis einer erfolgreich antwortet.
        """
        self._lazy_init()
        self.ui = ui

        # Wenn alle Gemini-Keys im Cooldown: sofort auf Groq wechseln ohne Chain-Versuch
        if self.provider == "gemini" and self.keys:
            healthy = sum(1 for i in range(len(self.keys)) if self._is_key_healthy(i))
            if healthy == 0 and os.getenv("GROQ_API_KEY"):
                ui.show_info("[dim]Alle Gemini-Keys im Cooldown — Groq übernimmt automatisch[/dim]")
                ok, _ = self.set_provider("groq")
                if ok:
                    try:
                        result = self._run_agent_turn_internal(user_input, ui, max_steps)
                        self.set_provider("gemini")
                        return result
                    except Exception:
                        self.set_provider("gemini")

        ui.update_status(f"Orchestrierung der Anfrage läuft ({self.provider})...")
        orig_prov = self.provider
        orig_model = self.model_name
        try:
            active_providers = [self.provider] + self._get_fallback_providers()

            if "ollama" in active_providers and active_providers[0] != "ollama":
                active_providers.remove("ollama")
                active_providers.append("ollama")

            # Smart Router: Wissensfragen → Groq zuerst (schneller, spart Gemini-Quota)
            preferred = self.router.preferred_provider(user_input, active_providers)
            if preferred != active_providers[0] and preferred in active_providers:
                active_providers.remove(preferred)
                active_providers.insert(0, preferred)
                ui.show_info(f"[dim][Smart Router] -> {preferred} (Wissensfrage)[/dim]")

            # Groq parallel nur wenn Gemini primär läuft
            _groq_thread, _groq_result = (None, [None])
            if active_providers[0] != "groq":
                _groq_thread, _groq_result = self._start_groq_parallel(user_input)

            last_error = None
            backoff_schedule = [2, 4, 8]

            for prov in active_providers:
                if prov != self.provider:
                    ok, msg = self.set_provider(prov)
                    if not ok:
                        continue

                # Gemini: ganze Modell-Fallback-Kette durchlaufen, bevor zu Groq gewechselt wird.
                if prov == "gemini":
                    result, last_error = self._run_gemini_model_chain(
                        user_input, ui, max_steps, backoff_schedule
                    )
                    if result is not None:
                        return result
                    # Alle Gemini-Modelle erschöpft → Groq-Backup falls vorhanden
                    if _groq_thread:
                        _groq_thread.join(timeout=30)
                        if _groq_result[0]:
                            ui.show_info("[dim]Alle Gemini-Modelle erschöpft — Groq-Backup aktiv[/dim]")
                            return _groq_result[0]
                    continue  # nächsten Provider in active_providers probieren

                for attempt in range(len(backoff_schedule) + 1):
                    try:
                        return self._run_agent_turn_internal(user_input, ui, max_steps)
                    except QuotaExhaustedException as qe:
                        last_error = qe
                        break  # nächsten Provider in active_providers probieren
                    except Exception as e:
                        err_str = str(e).lower()
                        if self._is_rate_limit_error(err_str) or self._is_auth_error(err_str):
                            if self.rotate_key():
                                continue
                            last_error = QuotaExhaustedException(self.model_name, len(self.keys))
                            break

                        # "connection error" von httpx/genai-SDK = oft erschöpfter Key, NICHT echtes Netzwerkproblem
                        if "connection error" in err_str or "connectionerror" in err_str:
                            self._mark_key_exhausted(self.active_index, duration=65.0)
                            if self.rotate_key():
                                continue
                            last_error = QuotaExhaustedException(self.model_name, len(self.keys))
                            break
                        is_real_network = any(k in err_str for k in [
                            "connection refused", "name or service not known",
                            "nodename nor servname", "network is unreachable",
                        ])
                        if is_real_network:
                            last_error = ConnectionError("Kein Internet. Netzwerk prüfen.")
                            raise last_error

                        if self._is_server_error(err_str) and attempt < len(backoff_schedule):
                            time.sleep(backoff_schedule[attempt])
                            continue

                        last_error = e
                        break # Zum naechsten Provider wechseln

            if isinstance(last_error, QuotaExhaustedException):
                # Zeige wann Keys wieder verfügbar sind
                cooldowns = self._load_shared_cooldowns()
                if cooldowns:
                    min_wait = min(max(0, int(v - time.time())) for v in cooldowns.values())
                    raise Exception(f"Alle Gemini-Keys erschöpft. Kürzeste Wartezeit: {min_wait//60}min {min_wait%60}s. Groq-Fallback auch fehlgeschlagen.")
                raise last_error
            if isinstance(last_error, ConnectionError):
                raise last_error
            raise Exception(f"Fehler: {last_error}")
        finally:
            if self.provider != orig_prov:
                try:
                    self.set_provider(orig_prov)
                    self.set_model(orig_model)
                except Exception:
                    pass

    # Reihenfolge der Gemini-Modelle: nur aktiv unterstützte Modelle.
    GEMINI_MODEL_CHAIN = [
        "gemini-2.5-flash",  # primär
        "gemini-2.0-flash",  # Fallback
    ]

    def _rotate_to_next_key(self, silent=True):
        """Proaktive Round-Robin-Rotation mit RPM-Awareness.
        Wechselt wenn: aktueller Key ungesund ODER RPM-Limit fast erreicht.
        Bevorzugt Keys mit niedrigster aktueller Auslastung."""
        if len(self.keys) <= 1:
            return self._is_key_healthy(0)

        # Aktuellen Key behalten wenn er gesund ist und RPM noch ok
        if self._is_key_healthy(self.active_index) and self._is_key_rpm_safe(self.active_index):
            self._record_request(self.active_index)
            return True

        # Finde den gesunden Key mit der niedrigsten RPM-Auslastung
        best_idx = None
        best_rpm = 999
        start = (self.active_index + 1) % len(self.keys)
        for i in range(len(self.keys)):
            idx = (start + i) % len(self.keys)
            if self._is_key_healthy(idx):
                rpm = self._key_rpm(idx)
                if rpm < best_rpm:
                    best_rpm = rpm
                    best_idx = idx

        if best_idx is None:
            return False  # alle Keys erschöpft

        if best_idx != self.active_index:
            old_history = None
            try:
                old_history = self.chat.get_history() if self.chat else None
            except Exception:
                pass
            self.active_index = best_idx
            self.api_key = self.keys[self.active_index]
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
            try:
                self.reset_chat(history=old_history)
            except Exception:
                pass
            if not silent:
                print(f"[dim]rotate -> key {self.active_index + 1}/{len(self.keys)} ({best_rpm} rpm)[/dim]")

        self._record_request(self.active_index)
        return True

    def _send_parallel_cheap(self, user_input, num_keys=5, ui=None):
        """MoA Phase 1: Feuert Cheap-Modell auf num_keys gesunde Keys gleichzeitig (stateless).
        Gibt Liste von Draft-Antworten zurück — Fehler werden als Leerstring ignoriert."""
        cheap_model = os.getenv("GEMINI_CHEAP_MODEL", "gemini-2.5-flash")

        healthy_keys_with_idx = []
        for i in range(len(self.keys)):
            idx = (self.active_index + i) % len(self.keys)
            if self._is_key_healthy(idx):
                healthy_keys_with_idx.append((idx, self.keys[idx]))
                if len(healthy_keys_with_idx) >= num_keys:
                    break

        if not healthy_keys_with_idx:
            return []

        total = len(healthy_keys_with_idx)

        def _call_one(idx, key):
            try:
                c = genai.Client(api_key=key)
                resp = c.models.generate_content(
                    model=cheap_model,
                    contents=user_input,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        max_output_tokens=1024,
                    ),
                )
                return resp.text or ""
            except Exception as e:
                if self._is_rate_limit_error(str(e)):
                    self._mark_key_exhausted(idx, duration=45.0)
                return ""

        drafts = []
        completed = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=total) as pool:
            futures = {pool.submit(_call_one, idx, k): idx for idx, k in healthy_keys_with_idx}
            try:
                for fut in concurrent.futures.as_completed(futures, timeout=8.0):
                    completed += 1
                    if ui:
                        ui.update_status(f"MoA [{cheap_model}]: {completed}/{total} Agenten fertig...")
                    try:
                        res = fut.result()
                        if res:
                            drafts.append(res)
                    except Exception:
                        pass
            except concurrent.futures.TimeoutError:
                # Bereits gesammelte Drafts nutzen, hängende abbrechen
                for fut in futures:
                    fut.cancel()
        return drafts

    def _run_gemini_model_chain(self, user_input, ui, max_steps, backoff_schedule):
        """Durchlaeuft die Gemini-Modell-Kette. Jedes Modell nutzt den vollen Key-Pool.
        Gibt (result, last_error) zurueck: result!=None => Erfolg; sonst alle Modelle erschoepft.
        """
        last_error = None
        for model in self.GEMINI_MODEL_CHAIN:
            if self.model_name != model:
                old_history = None
                try:
                    old_history = self.chat.get_history() if self.chat else None
                except Exception:
                    old_history = None
                try:
                    self.model_name = model
                    self.reset_chat(history=old_history)
                    ui.show_info(f"[dim]-> Gemini-Modell: {model}[/dim]")
                except Exception as e:
                    last_error = e
                    continue  # Modell nicht nutzbar → nächstes

            for attempt in range(len(backoff_schedule) + 1):
                try:
                    return (self._run_agent_turn_internal(user_input, ui, max_steps), None)
                except QuotaExhaustedException as qe:
                    last_error = qe
                    break  # nächstes Modell in der Kette
                except Exception as e:
                    err_str = str(e).lower()
                    if self._is_rate_limit_error(err_str) or self._is_auth_error(err_str):
                        if self.rotate_key():
                            continue
                        last_error = QuotaExhaustedException(self.model_name, len(self.keys))
                        break

                    # "connection error" vom genai-SDK = erschöpfter/blockierter Key → rotieren
                    if "connection error" in err_str or "connectionerror" in err_str:
                        self._mark_key_exhausted(self.active_index, duration=65.0)
                        if self.rotate_key():
                            continue
                        last_error = QuotaExhaustedException(self.model_name, len(self.keys))
                        break
                    is_real_network = any(k in err_str for k in [
                        "connection refused", "name or service not known",
                        "nodename nor servname", "network is unreachable",
                    ])
                    if is_real_network:
                        last_error = ConnectionError("Kein Internet. Netzwerk prüfen.")
                        return (None, last_error)

                    if self._is_server_error(err_str) and attempt < len(backoff_schedule):
                        time.sleep(backoff_schedule[attempt])
                        continue
                    last_error = e
                    break  # nächstes Modell in der Kette
        return (None, last_error)

    def _run_agent_turn_internal(self, user_input, ui, max_steps=25):
        """Agentischer Loop: sendet die Eingabe, fuehrt angeforderte Tools aus und
        speist die Ergebnisse zurueck, bis das Modell eine finale Textantwort liefert.
        """
        if self.provider != "gemini":
            return self.oa_agents[self.provider].run_agent_turn(user_input, ui, max_steps)

        # Pro-aktive Rotation: Nutze alle Google-Konten (Keys) gleichmäßig (Round Robin)
        self._rotate_to_next_key()

        if self.chat:
            old_history = self.chat.get_history()
            new_history = compress_gemini_history(old_history, self.model_name, self.client)
            if len(new_history) != len(old_history):
                self.reset_chat(history=new_history)

        # AI Classifier: wählt Modell + Token-Budget basierend auf Komplexität
        _orig_model = self.model_name
        try:
            history_tail = self.chat.get_history()[-8:] if self.chat else []
            _selected_model, self._current_turn_budget = self._ai_classifier.classify(
                user_input, history_tail, self.client, self.GEMINI_MODEL_CHAIN
            )
            if _selected_model != self.model_name:
                self.model_name = _selected_model
                self.reset_chat(history=self.chat.get_history() if self.chat else None)
        except Exception:
            pass

        # Direkt senden — Modell bereits vom AI Classifier gewählt
        ui.update_status(f"{self.model_name} verarbeitet...")
        resp = self._send_with_rotation(user_input)

        for _ in range(max_steps):
            function_calls = getattr(resp, "function_calls", None) or []

            if not function_calls:
                if self.model_name != _orig_model:
                    try:
                        self.model_name = _orig_model
                        self.reset_chat(history=self.chat.get_history() if self.chat else None)
                    except Exception:
                        pass
                return self._extract_text(resp)

            interim = self._extract_text(resp)
            if interim:
                ui.show_agent_thought(interim)

            response_parts = []

            # Harness permission check
            try:
                import harness as _harness
                _perm = _harness.permissions()
                _hooks = _harness.hooks()
            except Exception:
                _perm = None
                _hooks = None

            # Parallelisierbare vs. sequentielle Tools
            parallel_candidates = []
            sequential_calls = []

            for fc in function_calls:
                name = fc.name
                args = dict(fc.args) if fc.args else {}

                # Hard deny from harness
                if _perm and _perm.is_denied(name):
                    response_parts = getattr(response_parts, '__class__', list)()
                    continue

                # Interaktive oder spezielle Tools müssen sequentiell laufen
                if name in ["ask_user", "activate_skill"]:
                    sequential_calls.append(fc)
                elif tools.is_safe(name) or ui.yolo or (_perm and _perm.is_auto_approved(name, tools.is_safe(name))):
                    parallel_candidates.append(fc)
                else:
                    # Nicht-sichere Tools ohne YOLO brauchen Bestätigung (sequentiell)
                    sequential_calls.append(fc)

            # 1. Parallele Ausführung
            if parallel_candidates:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, len(parallel_candidates))) as executor:
                    def _dispatch_with_hooks(fc_item):
                        _name = fc_item.name
                        _args = dict(fc_item.args) if fc_item.args else {}
                        if _hooks:
                            _hooks.pre_tool(_name, _args)
                        _res = tools.dispatch(_name, _args)
                        if _hooks:
                            _hooks.post_tool(_name, _args, _res)
                        if _name in JIT_TRIGGER_TOOLS:
                            _path = extract_path_from_args(_name, _args)
                            if _path:
                                _jit = discover_jit_context(_path, os.getcwd())
                                _res = append_jit_context(_res, _jit)
                        return _res

                    futures = {
                        executor.submit(_dispatch_with_hooks, fc): fc
                        for fc in parallel_candidates
                    }
                    for future in concurrent.futures.as_completed(futures):
                        fc = futures[future]
                        name = fc.name
                        try:
                            result = future.result()
                        except Exception as e:
                            result = f"FEHLER bei paralleler Ausführung: {e}"

                        ui.show_tool_result(name, result)
                        response_parts.append(
                            types.Part.from_function_response(name=name, response={"result": result})
                        )

            # 2. Sequentielle Ausführung (Interaktion, Bestätigung, Skills)
            for fc in sequential_calls:
                name = fc.name
                args = dict(fc.args) if fc.args else {}

                if name == "ask_user":
                    question = args.get("question", "")
                    ui.stop_thinking()
                    user_ans = ui.prompt_user(f"\n[bold yellow]❓ Frage von Sonu:[/bold yellow] {question}")
                    ui.start_thinking("Sonu verarbeitet Antwort...")
                    response_parts.append(
                        types.Part.from_function_response(name=name, response={"result": user_ans})
                    )
                    continue

                if name == "activate_skill":
                    ok, msg = self.set_skill(args.get("name"))
                    ui.show_tool_result(name, msg, rejected=not ok)
                    response_parts.append(
                        types.Part.from_function_response(name=name, response={"result": msg})
                    )
                    continue

                # Bestätigung einholen für nicht-sichere Tools (da nicht in parallel_candidates)
                ui.show_tool_call(name, args)
                if not ui.confirm_action(name, args):
                    result = "ABGELEHNT: Der Nutzer hat diese Aktion abgelehnt."
                    ui.show_tool_result(name, result, rejected=True)
                else:
                    if _hooks:
                        _hooks.pre_tool(name, args)
                    result = tools.dispatch(name, args)
                    if _hooks:
                        _hooks.post_tool(name, args, result)
                    if name in JIT_TRIGGER_TOOLS:
                        _path = extract_path_from_args(name, args)
                        if _path:
                            _jit = discover_jit_context(_path, os.getcwd())
                            result = append_jit_context(result, _jit)
                    ui.show_tool_result(name, result)

                response_parts.append(
                    types.Part.from_function_response(name=name, response={"result": result})
                )

            resp = self._send_with_rotation(response_parts)

        return "(Abbruch: maximale Anzahl an Tool-Schritten erreicht.)"

    @staticmethod
    def _extract_text(resp):
        try:
            parts = []
            if hasattr(resp, "candidates") and resp.candidates:
                candidate = resp.candidates[0]
                if hasattr(candidate, "content") and candidate.content:
                    if hasattr(candidate.content, "parts") and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, "text") and part.text:
                                parts.append(part.text)
            if parts:
                return "".join(parts).strip()
            # Falls Funktionsaufrufe existieren, resp.text nicht aufrufen, um Warnung zu vermeiden
            if getattr(resp, "function_calls", None):
                return ""
            return (resp.text or "").strip()
        except Exception:
            return ""

    # --- Hilfsbefehle fuer die REPL -------------------------------------------------

    def get_key_pool_status(self):
        """Gibt eine Liste mit dem Status aller Keys zurück."""
        status_list = []
        shared = self._load_shared_cooldowns()
        now = time.time()

        for i, key in enumerate(self.keys):
            local_expiry = self._key_cooldowns.get(key, 0.0)
            shared_expiry = shared.get(key, 0.0)

            expiry = max(local_expiry, shared_expiry)
            remaining = max(0, expiry - now)

            status_list.append({
                "index": i + 1,
                "active": (i == self.active_index),
                "healthy": remaining <= 0,
                "remaining_cooldown": remaining,
                # Key maskieren für Sicherheit
                "key_hint": f"{key[:6]}...{key[-4:]}" if len(key) > 10 else "invalid"
            })
        return status_list

    def list_available_models(self):
        models = []
        if self.provider == "gemini":
            try:
                for m in self.client.models.list():
                    name = m.name.replace("models/", "")
                    models.append(name)
            except Exception as e:
                raise Exception(f"Fehler beim Auflisten der Modelle: {str(e)}")
        else:
            try:
                for m in self.oa_agents[self.provider].client.models.list():
                    models.append(m.id)
            except Exception as e:
                pass # Many OpenAI compatible providers fail or return 404 for models.list()
        return models

    def set_model(self, model_name):
        self.model_name = model_name
        if self.provider == "gemini":
            self.reset_chat()
        else:
            self.oa_agents[self.provider].model = model_name
