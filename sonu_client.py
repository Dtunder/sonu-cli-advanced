import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

import tools

SYSTEM_INSTRUCTION = """Du bist Sonu, ein autonomer Coding- und Recherche-Agent, der direkt im Terminal des Nutzers laeuft.

Du hast echte Werkzeuge und handelst damit selbststaendig, statt nur zu reden:
- read_file(path): Datei lesen
- list_dir(path): Verzeichnis auflisten
- search_files(pattern, path): Textsuche ueber Dateien
- write_file(path, content): Datei schreiben/ueberschreiben
- run_shell(command): PowerShell-Befehl ausfuehren

Arbeitsweise:
- Wenn eine Aufgabe Dateizugriff oder Befehle erfordert, BENUTZE die Werkzeuge. Rate nicht ueber Dateiinhalte.
- Gehe schrittweise vor: erst erkunden (lesen/listen/suchen), dann handeln (schreiben/ausfuehren).
- Du kannst mehrere Werkzeuge nacheinander aufrufen, bis die Aufgabe geloest ist.
- Schreibende und ausfuehrende Aktionen werden dem Nutzer zur Bestaetigung vorgelegt. Wird etwas abgelehnt, respektiere das und schlage eine Alternative vor.
- Nutze bevorzugt relative Pfade zum aktuellen Arbeitsverzeichnis.
- Antworte am Ende knapp auf Deutsch in einem praezisen, mechatronisch-kompetenten Ton und fasse zusammen, was du getan hast.
"""


class SonuClient:
    def __init__(self, model_name="gemini-3.5-flash"):
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
            raise ValueError(
                "Kein API-Key in der .env-Datei gefunden.\n"
                "Bitte trage deinen API Key unter GEMINI_API_KEY dort ein."
            )

        self.active_index = 0
        if self.api_key in self.keys:
            self.active_index = self.keys.index(self.api_key)
        else:
            self.api_key = self.keys[0]

        self.client = genai.Client(api_key=self.api_key)
        self.model_name = model_name
        self.chat = None
        self.reset_chat()

    def _build_config(self):
        return types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[tools.get_tool_object()],
        )

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

    def run_agent_turn(self, user_input, ui, max_steps=25):
        """Agentischer Loop: sendet die Eingabe, fuehrt angeforderte Tools aus und
        speist die Ergebnisse zurueck, bis das Modell eine finale Textantwort liefert.
        """
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
        try:
            for m in self.client.models.list():
                name = m.name.replace("models/", "")
                models.append(name)
        except Exception as e:
            raise Exception(f"Fehler beim Auflisten der Modelle: {str(e)}")
        return models

    def set_model(self, model_name):
        self.model_name = model_name
        self.reset_chat()
