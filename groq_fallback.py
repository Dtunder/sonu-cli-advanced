import os
import groq

class GroqFallback:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY nicht in .env gefunden.")
        self.client = groq.Groq(api_key=self.api_key)
        self.model = "llama-3.3-70b-versatile"

    def run_turn(self, user_input, history, ui) -> str:
        ui.show_info(f"Führe Groq Fallback durch mit Modell: {self.model}...")

        messages = [{"role": "system", "content": "Du bist ein hilfreicher Assistent (Groq Fallback)."}]

        # Konvertiere letzte 10 History-Turns
        # history ist eine Liste von Gemini Content-Objekten
        if history:
            for item in history[-10:]:
                role = "assistant" if item.role == "model" else "user"
                text = ""
                if hasattr(item, "parts"):
                    for part in item.parts:
                        if hasattr(part, "text") and part.text:
                            text += part.text
                if text:
                    messages.append({"role": role, "content": text})

        messages.append({"role": "user", "content": user_input})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Fehler im Groq Fallback: {e}"
