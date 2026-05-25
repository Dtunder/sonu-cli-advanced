import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

import providers
import tools
from skills_manager import SkillsManager
from process_manager import ProcessManager
from memory_manager import MemoryManager
from multi_provider_client import MultiProviderClient
from openai_agent import OpenAICompatibleAgent

SYSTEM_INSTRUCTION = """Du bist Sonu, ein autonomer Coding- und Recherche-Agent, der direkt im Terminal des Nutzers laeuft.

Du hast echte Werkzeuge und handelst damit selbststaendig, statt nur zu reden:
- read_file(path): Datei lesen
- list_dir(path): Verzeichnis auflisten
- search_files(pattern, path): Textsuche ueber Dateien
- write_file(path, content): Datei schreiben/ueberschreiben
- edit_file(path, old_string, new_string): eindeutige Textstelle chirurgisch ersetzen (bevorzugt vor write_file fuer Teiländerungen)
- run_shell(command): PowerShell-Befehl ausfuehren
- start_background_task(command): PowerShell-Befehl asynchron im Hintergrund ausfuehren
- list_background_tasks(): Hintergrund-Prozesse auflisten
- read_background_task_output(task_id): Output eines Tasks ausgeben
- kill_background_task(task_id): Hintergrundprozess beenden
- delegate_to_subagent(task_description, provider): Spawnt einen isolierten Sonu-Subagenten fuer Recherche/Code-Aufgaben, um den Haupt-Kontext nicht zu ueberlasten.
- delegate_to_jules(prompt): Komplexe Aufgabe headless im Hintergrund an Google Jules delegieren
- activate_skill(name): ein Experten-Skill-Profil aktivieren, das deinen Fokus/Workflow umstellt

Arbeitsweise:
- Wenn eine Aufgabe viel Recherche/Dateizugriff erfordert (mehrere Dateien durchsuchen, Code verstehen), nutze ZWINGEND delegate_to_subagent, damit der Subagent das macht und dir nur das Destillat/Ergebnis liefert.
- Wenn eine Aufgabe nach einem klaren Expertenfokus verlangt (Architektur, Performance, Review, kybernetische Analyse), aktiviere zuerst das passende Skill via activate_skill.
- Wenn eine Aufgabe Dateizugriff, Befehle oder Delegierungen erfordert, BENUTZE die entsprechenden Werkzeuge. Rate nicht ueber Dateiinhalte.
- Gehe schrittweise vor: erst erkunden (lesen/listen/suchen), dann handeln (schreiben/ausfuehren/delegieren).
- Du kannst mehrere Werkzeuge nacheinander aufrufen, bis die Aufgabe geloest ist.
- Schreibende, ausfuehrende und delegierende Aktionen werden dem Nutzer zur Bestaetigung vorgelegt. Wird etwas abgelehnt, respektiere das und schlage eine Alternative vor.
- Nutze bevorzugt relative Pfade zum aktuellen Arbeitsverzeichnis.
- Antworte am Ende knapp auf Deutsch in einem praezisen, mechatronisch-kompetenten Ton und fasse zusammen, was du getan hast.
"""


class SonuClient:
    def __init__(self, model_name=None):
        load_dotenv(override=True)
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        load_dotenv(env_path, override=True)

        self.api_key = os.getenv("GEMINI_API_KEY")
        key_pool_str = os.getenv("GEMINI_KEY_POOL", "")

        if key_pool_str:
            self.keys = [k.strip() for k in key_pool_str.split(",") if k.strip()]
        else:
            self.keys = [self.api_key] if self.api_key else []

        if not self.keys:
            pass # We might not need gemini key if another provider is used, we'll check later.

        self.active_index = 0
        if self.api_key in self.keys:
            self.active_index = self.keys.index(self.api_key)
        elif self.keys:
            self.api_key = self.keys[0]

        # Initialisierung der fortgeschrittenen Manager
        self.skills_mgr = SkillsManager()
        self.process_mgr = ProcessManager()
        self.memory_mgr = MemoryManager()
        tools.set_process_manager(self.process_mgr)

        self.client = None
        if self.api_key:
             self.client = genai.Client(api_key=self.api_key)
             
        self.chat = None
        self.provider = "gemini"
        self.oa_agents = {}
        
        prov_info = providers.get_provider("gemini")
        self.model_name = model_name or prov_info["default_model"]
        
        if self.client:
             self.reset_chat()
             
    def set_provider(self, name):
        prov_info = providers.get_provider(name)
        if not prov_info:
            return False, f"Unbekannter Provider: {name}"
            
        env_var = prov_info["env_var"]
        if not os.getenv(env_var):
            return False, f"Kein API Key gefunden fuer {name}. Setze {env_var} in .env"
            
        self.provider = name
        self.model_name = prov_info["default_model"]
        
        if prov_info["kind"] == "openai":
            if name not in self.oa_agents:
                try:
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

    def _build_config(self):
        # 1. 4-Level Gedaechtnis abrufen
        mem_context = self.memory_mgr.load_memory(os.getcwd())

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
        full_sys_prompt = (
            f"{active_instruction}\n\n"
            f"=== ERMITTELTER SYSTEMKONTEXT (4-EBENEN-GEDÄCHTNIS) ===\n"
            f"{mem_context}\n"
        )

        return types.GenerateContentConfig(
            system_instruction=full_sys_prompt,
            tools=[tools.get_tool_object(), self._skill_tool()],
        )

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
    def _is_quota_error(error_str: str) -> bool:
        s = error_str.lower()
        # Bewusst eng gefasst: nur echte Quota-/Key-Probleme loesen Rotation aus.
        # 'invalid argument' o.ae. (z.B. falscher Modellname) wird NICHT als Quota gewertet.
        return (
            "quota" in s
            or "rate limit" in s
            or "resource_exhausted" in s
            or "429" in s
            or "api key expired" in s
            or "api_key_invalid" in s
            or "permission_denied" in s
        )

    def rotate_key(self):
        """Rotiert zum naechsten Key im Pool, erhaelt den Gespraechsverlauf und aktualisiert .env."""
        if len(self.keys) <= 1:
            return False

        old_history = None
        try:
            old_history = self.chat.get_history() if self.chat else None
        except Exception:
            old_history = None

        self.active_index = (self.active_index + 1) % len(self.keys)
        new_key = self.keys[self.active_index]
        self.api_key = new_key

        from rich.console import Console
        Console().print(
            f"\n[bold yellow][!] Quota erschoepft oder Key ungueltig. Rotiere zu Key-Index "
            f"{self.active_index + 1} (...{new_key[-6:]}) und wiederhole Anfrage...[/bold yellow]\n"
        )

        self.client = genai.Client(api_key=new_key)
        self._update_env_file(new_key)
        self.reset_chat(history=old_history)
        return True

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
        """Sendet eine Nachricht (str oder Part-Liste) und rotiert bei Quota-Fehlern."""
        if not self.chat:
            self.reset_chat()
        for _ in range(len(self.keys)):
            try:
                return self.chat.send_message(message)
            except Exception as e:
                if self._is_quota_error(str(e)) and len(self.keys) > 1:
                    if self.rotate_key():
                        continue
                raise
        raise Exception("Alle verfuegbaren API-Keys im Pool sind erschoepft oder gesperrt!")

    def send_message_stream(self, message):
        """Sendet eine Nachricht als Stream und rotiert bei Quota-Fehlern.
        Da der Stream lazy ist, erzwingen wir das Abrufen des ersten Chunks,
        um Quota-Fehler sofort abzufangen und den Key zu rotieren.
        """
        if not self.chat:
            self.reset_chat()
        for _ in range(len(self.keys)):
            try:
                response_stream = self.chat.send_message_stream(message)
                iterator = iter(response_stream)
                
                # Erste Antwort abfragen, um Netzwerkverbindung/Quota sofort zu testen
                first_chunk = next(iterator)
                
                # Generator zurueckgeben, der den ersten Chunk und danach den Rest liefert
                def stream_generator():
                    yield first_chunk
                    for chunk in iterator:
                        yield chunk
                return stream_generator()
            except StopIteration:
                # Leerer Stream
                def empty_generator():
                    return
                    yield
                return empty_generator()
            except Exception as e:
                if self._is_quota_error(str(e)) and len(self.keys) > 1:
                    if self.rotate_key():
                        continue
                raise
        raise Exception("Alle verfuegbaren API-Keys im Pool sind erschoepft!")

    def _get_fallback_providers(self):
        """Findet alle Provider, fuer die ein API-Key in der .env existiert, ausser dem aktuellen."""
        available = []
        for p in providers.list_providers():
            if p == self.provider: 
                continue
            prov_info = providers.get_provider(p)
            if os.getenv(prov_info["env_var"]):
                available.append(p)
        return available

    def run_agent_turn(self, user_input, ui, max_steps=25):
        """Wrapper fuer den Agent-Loop mit kaskadierendem automatischem Provider-Fallback.
        Versucht alle verfuegbaren Provider nacheinander, bis einer erfolgreich antwortet.
        """
        active_providers = [self.provider] + self._get_fallback_providers()
        last_error = None
        
        for prov in active_providers:
            if prov != self.provider:
                ui.show_info(f"Provider '{self.provider}' ausgelastet (Quota). Wechsle automatisch zu: [bold cyan]{prov}[/bold cyan] ...")
                ok, msg = self.set_provider(prov)
                if not ok:
                    continue
            
            try:
                return self._run_agent_turn_internal(user_input, ui, max_steps)
            except Exception as e:
                err_str = str(e).lower()
                is_quota = any(k in err_str for k in [
                    "erschoepft", "quota", "rate limit", "429", "limit reached", 
                    "exhausted", "forbidden", "invalid argument", "model not found", 
                    "insufficient permissions", "error code: 400", "error code: 403"
                ])
                if is_quota:
                    last_error = e
                    continue
                else:
                    raise
                    
        raise Exception(
            f"Alle konfigurierten Provider (Gemini, Groq, OpenRouter, xAI, Hugging Face) "
            f"sind erschoepft oder gesperrt!\nLetzter Fehler: {last_error}"
        )

    def _run_agent_turn_internal(self, user_input, ui, max_steps=25):
        """Agentischer Loop: sendet die Eingabe, fuehrt angeforderte Tools aus und
        speist die Ergebnisse zurueck, bis das Modell eine finale Textantwort liefert.
        """
        if self.provider != "gemini":
            return self.oa_agents[self.provider].run_agent_turn(user_input, ui, max_steps)

        resp = self._send_with_rotation(user_input)

        for _ in range(max_steps):
            function_calls = getattr(resp, "function_calls", None) or []

            if not function_calls:
                return self._extract_text(resp)

            interim = self._extract_text(resp)
            if interim:
                ui.show_agent_thought(interim)

            response_parts = []
            for fc in function_calls:
                name = fc.name
                args = dict(fc.args) if fc.args else {}

                ui.show_tool_call(name, args)

                # Skill-Aktivierung wird im Client behandelt (aendert den System-Prompt),
                # nicht ueber tools.dispatch. Keine Bestaetigung noetig.
                if name == "activate_skill":
                    ok, msg = self.set_skill(args.get("name"))
                    ui.show_tool_result(name, msg, rejected=not ok)
                    response_parts.append(
                        types.Part.from_function_response(name=name, response={"result": msg})
                    )
                    continue

                if not tools.is_safe(name):
                    if not ui.confirm_action(name, args):
                        result = "ABGELEHNT: Der Nutzer hat diese Aktion abgelehnt."
                        ui.show_tool_result(name, result, rejected=True)
                        response_parts.append(
                            types.Part.from_function_response(name=name, response={"result": result})
                        )
                        continue

                result = tools.dispatch(name, args)
                ui.show_tool_result(name, result)
                response_parts.append(
                    types.Part.from_function_response(name=name, response={"result": result})
                )

            resp = self._send_with_rotation(response_parts)

        return "(Abbruch: maximale Anzahl an Tool-Schritten erreicht.)"

    @staticmethod
    def _extract_text(resp):
        try:
            return (resp.text or "").strip()
        except Exception:
            return ""

    # --- Hilfsbefehle fuer die REPL -------------------------------------------------

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
