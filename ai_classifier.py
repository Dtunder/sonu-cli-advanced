"""
AI Classifier Router — portiert von Google Gemini CLI classifierStrategy.ts + numericalClassifierStrategy.ts
Nutzt gemini-2.0-flash-lite um Komplexität zu bewerten und das richtige Modell zu wählen.
"""
import json

CLASSIFIER_MODEL = "gemini-2.0-flash-lite"
MAX_CLASSIFIER_LATENCY_MS = 800
HISTORY_TURNS = 4

# Complexity Score Schwellwert: >= 50 → starkes Modell, < 50 → lite
COMPLEXITY_THRESHOLD = 50

# Regelbasierte Klassifizierung — kein extra API-Call nötig
_HEAVY_KEYWORDS = (
    "refactor", "refaktorier", "architektur", "migration", "migriere",
    "implementier", "erkläre", "analysiere", "debug", "warum", "optimier",
    "schreib", "erstell", "entwirf", "überarbeite", "mehrere dateien",
    "write", "create", "implement", "explain", "analyze", "architecture",
    "redesign", "migrate", "optimize", "why does", "how does",
)
_LITE_KEYWORDS = (
    "lies", "zeig", "list", "read", "show", "open", "cat", "print",
    "status", "version", "help", "hilfe", "hallo", "hi", "hey", "ok",
)

CLASSIFIER_SYSTEM_PROMPT = """Du bist ein spezialisierter Task-Router. Deine einzige Aufgabe ist es, die Komplexität der Nutzer-Anfrage zu bewerten und einen Wert von 1-100 zurückzugeben.

# Komplexitäts-Rubrik
**1-20: Trivial / Direkt**
- Einfache Lesebefehle (Datei lesen, Verzeichnis auflisten)
- Einzelne, explizite Anweisung ohne Mehrdeutigkeit
- 1 Tool-Call nötig

**21-50: Standard / Routine**
- Einzelne Datei editieren
- Einfachen Fehler beheben wenn Ursache klar ist
- Linearer Mehrschritt-Task

**51-80: Hoch / Analytisch**
- Mehrere Dateien betroffen
- Unbekannte Fehlerursache debuggen
- Feature implementieren mit Kontext-Verständnis

**81-100: Extrem / Strategisch**
- System-Architektur entwerfen
- Migration oder Refactoring großer Codebasen
- Sehr vage Anfragen ("mach das besser")
- 10+ Dateien betroffen

# Output Format
Antworte NUR mit JSON:
{"complexity_reasoning": "kurze Begründung", "complexity_score": <1-100>}

# Beispiele
User: lies package.json
{"complexity_reasoning": "Einzelner Lesebefehl.", "complexity_score": 8}

User: rename variable 'data' to 'userData' in utils.py
{"complexity_reasoning": "Lokale Änderung in einer Datei.", "complexity_score": 25}

User: warum crasht mein server beim Start?
{"complexity_reasoning": "Unbekannte Fehlerursache, erfordert Analyse.", "complexity_score": 65}

User: refactore die gesamte Auth-Logik auf JWT
{"complexity_reasoning": "Große Refaktorierung über mehrere Dateien.", "complexity_score": 88}
"""


class AIClassifierRouter:
    """
    Nutzt ein billiges Modell (flash-lite) um zu entscheiden welches Modell
    für die eigentliche Anfrage genutzt werden soll.
    Portiert von Google Gemini CLI ClassifierStrategy + NumericalClassifierStrategy.
    """

    def __init__(self):
        self._last_classification: dict = {}

    def classify(self, user_input: str, _history_tail: list, _gemini_client, available_models: list) -> tuple[str, int]:
        """
        Gibt (model_name, max_tokens) zurück.
        available_models[0] = stärkstes Modell (z.B. gemini-2.5-flash)
        available_models[-1] = schwächstes/günstigstes (z.B. gemini-2.0-flash-lite)
        """
        if not available_models:
            return "gemini-2.5-flash", 4096

        # Regelbasierte Klassifizierung — kein extra API-Call, keine Latenz
        score, reasoning = self._rule_score(user_input)

        lite = available_models[-1] if len(available_models) > 1 else available_models[0]
        strong = available_models[0]

        if score >= COMPLEXITY_THRESHOLD:
            model = strong
            budget = 8192 if score >= 80 else 4096
        else:
            model = lite
            budget = 512 if score < 15 else 2048

        self._last_classification = {
            "model_choice": model,
            "score": score,
            "reasoning": reasoning,
            "latency_ms": 0,
            "skipped": False,
        }
        return model, budget

    def _rule_score(self, user_input: str) -> tuple[int, str]:
        """Regelbasierte Komplexitätsbewertung ohne API-Call."""
        text = user_input.lower().strip()
        if len(text) < 15:
            return 5, "Sehr kurze Eingabe"
        if any(kw in text for kw in _LITE_KEYWORDS):
            return 20, "Einfacher Lese-/Status-Befehl"
        if any(kw in text for kw in _HEAVY_KEYWORDS):
            return 75, "Komplexe Aufgabe erkannt"
        # Länge als Proxy: längere Eingaben → höhere Komplexität
        if len(text) > 200:
            return 65, "Lange Eingabe"
        if len(text) > 80:
            return 45, "Mittlere Eingabe"
        return 30, "Standard-Anfrage"

    def _call_classifier(self, user_input: str, history_tail: list, gemini_client) -> dict | None:
        """Macht einen stateless API-Call zum Classifier-Modell."""
        from google.genai import types as _types

        # Letzte N Text-Turns aus der History extrahieren (keine Tool-Calls)
        context_parts = []
        for content in history_tail[-HISTORY_TURNS:]:
            try:
                for part in content.parts:
                    if part.text and not getattr(part, "function_call", None):
                        context_parts.append(f"{content.role.upper()}: {part.text[:200]}")
            except Exception:
                pass

        context_str = "\n".join(context_parts)
        prompt = f"{context_str}\nUSER: {user_input}" if context_str else user_input

        resp = gemini_client.models.generate_content(
            model=CLASSIFIER_MODEL,
            contents=prompt,
            config=_types.GenerateContentConfig(
                system_instruction=CLASSIFIER_SYSTEM_PROMPT,
                max_output_tokens=100,
                temperature=0.0,
            ),
        )
        text = (resp.text or "").strip()

        # JSON aus Antwort extrahieren
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(l for l in lines if not l.startswith("```"))

        parsed = json.loads(text)
        score = int(parsed.get("complexity_score", 50))
        score = max(1, min(100, score))
        return {"complexity_score": score, "complexity_reasoning": parsed.get("complexity_reasoning", "")}

    def status_line(self) -> str:
        c = self._last_classification
        if not c:
            return "AI Classifier: noch kein Call"
        if c.get("skipped"):
            return f"AI Classifier: übersprungen — {c.get('reasoning', '')} ({c.get('latency_ms', 0)}ms)"
        return (f"AI Classifier: score={c.get('score')} -> {c.get('model_choice', '?')} "
                f"| {c.get('reasoning', '')} ({c.get('latency_ms', 0)}ms)")
