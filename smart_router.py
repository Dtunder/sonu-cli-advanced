import json
import time

class AIClassifierRouter:
    def __init__(self):
        self._last_classification = None

    def classify_with_ai(self, user_input: str, history_tail: list, gemini_client, model: str) -> dict:
        start_time = time.time()

        system_prompt = """Du bist ein Routing-Klassifikator. Analysiere die Eingabe und den Kontext.
Entscheide, ob "flash" (gemini-2.5-flash) oder "lite" (gemini-2.0-flash-lite) besser geeignet ist.
Wähle 'lite' für einfache Fragen, Chat, Begrüßungen oder kurze Anfragen.
Wähle 'flash' für komplexe Aufgaben, Programmieren, tiefe Analysen, lange Kontexte oder logisches Denken.
Antworte NUR in JSON: {"model_choice": "flash" | "lite", "reasoning": "deine Begründung"}"""

        history_text = ""
        for msg in history_tail[-4:]:
            try:
                if hasattr(msg, "parts"):
                    text_parts = [p.text for p in msg.parts if hasattr(p, "text") and p.text]
                    if text_parts:
                        role = getattr(msg, "role", "user")
                        history_text += f"{role}: {' '.join(text_parts)}\n"
                elif isinstance(msg, dict):
                    if "parts" in msg:
                        text_parts = [p.get("text") for p in msg["parts"] if "text" in p]
                        if text_parts:
                            history_text += f"{msg.get('role', 'user')}: {' '.join(text_parts)}\n"
            except Exception:
                pass

        prompt = f"{system_prompt}\n\nKontext:\n{history_text}\n\nEingabe: {user_input}"

        try:
            response = gemini_client.models.generate_content(
                model="gemini-2.0-flash-lite",
                contents=prompt,
                config={
                    "max_output_tokens": 150,
                    "response_mime_type": "application/json",
                    "http_options": {"timeout": 0.8}
                }
            )
            latency_ms = int((time.time() - start_time) * 1000)

            if latency_ms > 800:
                result = {"model_choice": "flash", "reasoning": f"latency timeout ({latency_ms}ms > 800ms)", "latency_ms": latency_ms}
                self._last_classification = result
                return result

            try:
                data = json.loads(response.text)
                if "model_choice" not in data or data["model_choice"] not in ["flash", "lite"]:
                    raise ValueError()
                result = {
                    "model_choice": data["model_choice"],
                    "reasoning": data.get("reasoning", ""),
                    "latency_ms": latency_ms
                }
            except Exception:
                result = {"model_choice": "flash", "reasoning": "classifier failed", "latency_ms": latency_ms}

        except Exception:
            latency_ms = int((time.time() - start_time) * 1000)
            result = {"model_choice": "flash", "reasoning": "classifier failed", "latency_ms": latency_ms}

        self._last_classification = result
        return result

    def select_model(self, user_input: str, history_tail: list, gemini_client, available_models: list) -> tuple:
        if len(user_input) <= 15:
            lite_model = available_models[-1] if available_models else "gemini-2.0-flash-lite"
            return (lite_model, 512)

        if len(available_models) < 2:
            return (available_models[0] if available_models else "gemini-2.5-flash", 4096)

        result = self.classify_with_ai(user_input, history_tail, gemini_client, available_models[-1])
        choice = result.get("model_choice", "flash")

        if choice == "flash":
            return (available_models[0], 4096)
        else:
            return (available_models[-1], 1024)
