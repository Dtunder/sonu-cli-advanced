# LLM CLI Dashboard (Multi-Provider)

Dieses Tool basiert auf Simon Willison's `llm` und unterstützt Gemini, Grok, Ollama und viele andere.

## 1. Gemini (Bereits konfiguriert)
Frage stellen:
`python -m llm -m gemini-2.0-flash "Hallo, wie geht's?"`

## 2. Grok (xAI) einrichten
1. Key von [console.x.ai](https://console.x.ai/) holen.
2. Key setzen:
   `python -m llm keys set grok`
3. Nutzen:
   `python -m llm -m grok-2-latest "Was ist neu in Grok?"`

## 3. Ollama (Lokal auf deinem Laptop)
1. Installiere Ollama von [ollama.com](https://ollama.com/).
2. Lade ein Modell (z.B. Llama 3): `ollama run llama3`
3. In diesem CLI registrieren:
   `python -m llm ollama refresh`
4. Nutzen:
   `python -m llm -m llama3 "Antworte mir lokal."`

## 4. Kostenlose Anbieter (OpenRouter)
OpenRouter bietet Zugriff auf viele kostenlose Modelle.
1. Key von [openrouter.ai](https://openrouter.ai/) holen.
2. Key setzen:
   `python -m llm keys set openrouter`
3. Kostenlose Modelle nutzen:
   `python -m llm -m openrouter/google/gemini-2.0-flash-lite-preview-09-2025:free "Test"`

## 5. Interaktiver Chat-Modus
Starte eine Unterhaltung mit Gedächtnis:
`python -m llm chat -m gemini-2.0-flash`

---
Deine Logs werden standardmäßig in einer SQLite-Datenbank gespeichert. Du kannst sie jederzeit einsehen mit:
`python -m llm logs`
