# Sonu CLI — Project-Wide Memory

## 1. Architektur-Regeln
- Modular, asynchron: alle blockierenden Befehle via `ProcessManager` in den Hintergrund
- API-Keys: transparente Rotation bei 429 (lautlos, kein Traceback sichtbar)
- Silent Failover + exponential Backoff (2s, 4s, 8s) bei 503/429 über alle Provider
- Dynamisches Skill-System (`/activate <name>`) für on-the-fly Expertenprofile

## 2. Provider-Hierarchie (Mai 2026)
- **Primär:** `gemini-3.5-flash` (20 req/day, 5 Keys = ~100/day total via Rotation)
- **Parallel-Backup:** `groq/llama-3.3-70b-versatile` (startet im Daemon-Thread bei jedem Gemini-Call)
- **Fallback-Kette:** gemini → groq → openrouter → xai → huggingface → ollama (offline)
- **Swarm:** alle Provider parallel für reine Wissensfragen (kein Tool-Use)
- KRITISCH: `gemini-3.5-flash` nie auf `2.5-flash` ändern — andere Quota-Klasse

## 3. Verfügbare Commands
- `/generate-problems [file]` — generiert 100 Mechatronik/HFT-Forschungsprobleme
- `/batch [file]` — autonomer Batch-Researcher im Hintergrund (Standard: problems.json)
- `/watchdog <script>` — Absturz-Detektion + auto-Fix via Sonu
- `/swarm <frage>` — alle Provider parallel für beste Wissensantwort
- `/debate <prompt>` — Gemini + Groq + OpenRouter diskutieren gegeneinander
- `/delegate <prompt>` — headless Jules-Delegierung im Hintergrund
- `/activate <skill>` — Experten-Skill laden (cybernetic-thinking, system-architect, etc.)

## 4. Modul-Übersicht
- `sonu_client.py` — Haupt-Agent, QuotaExhaustedException, Groq-Parallel-Backup
- `main.py` — CLI-Loop, alle Command-Handler
- `tools.py` — 12 Agent-Tools (read/write/edit/shell/background/subagent/jules)
- `providers.py` — Provider-Config (gemini/groq/openrouter/xai/huggingface/ollama)
- `swarm_consensus.py` — Parallel-Abfrage, Scoring: len×0.3 + code_blocks×50 + vocab×0.5
- `batch_researcher.py` — liest problems.json, forscht autonom, speichert in recherche_ergebnisse/
- `sonu_watchdog.py` — Skript überwachen, Absturz → Sonu analysiert & fixt (max 3 Retries)
- `generate_100_problems.py` — 100 Mechatronik/HFT/RL Forschungsfragen generieren
- `skills_manager.py` + `skills/` — Skill-Profile (cybernetic-thinking, system-architect, etc.)
- `memory_manager.py` — 4-Ebenen: global (~/.sonu/), private (.sonu/), project (SONU.md), module

## 5. Neue Module (Mai 2026 — Gemini CLI Port)
- `model_availability.py` — Key-Health per (key_index, model): quota/auth/network getrennt
- `ai_classifier.py` — AI-basierter Komplexitäts-Router (1-100 Score via flash-lite, <800ms)
- `jit_context.py` — JIT Context: lädt SONU.md automatisch wenn Tools auf Verzeichnisse zugreifen
- Provider-Status: xAI=deaktiviert (keine Credits), OpenRouter=deaktiviert (keine Credits)
- Keys: 20 Gemini Keys in `.gemini_keys` (linter-proof), nie in `.env` hardcoden
- Neue Tools: `read_many_files`, `write_todos`, `get_todos`, `list_background_processes`, `read_background_output`

## 6. Bekannte Quirks & Fixes
- `QuotaExhaustedException` darf nicht durch `finally` propagieren → `_fb_failed` Flag in main.py
- `generate_100_problems.generate()` gibt `problems`-Liste zurück (return wurde hinzugefügt)
- `ziegler_nichols_simulation.py`: `T1` (nicht `t1`), plt.axvline strings sind einzeilig
- `.env` ist git-tracked ohne .gitignore — KRITISCH vor Push!

## 6. Google Jules Integration (Native Chat-Tools)
Sonu hat zwei native Agent-Tools für Jules. **Nutze diese direkt – fange NIE an, den jules-Binärpfad zu debuggen!**

### Verfügbare Jules-Tools (tools.py):
- `jules_remote_list()` — Listet alle remote Google Jules Sessions ab. Repariert Tarball automatisch.
- `jules_remote_pull(session_id)` — Zieht Patch von Jules-Session und wendet ihn lokal an. Repariert Tarball automatisch.
- `delegate_to_jules(prompt)` — Delegiert eine Aufgabe headless an Jules im Hintergrund.

### KRITISCH — Der Windows Tarball-Crash:
Die lokale `jules.exe` sucht beim Start nach:
`C:\Users\user\AppData\Local\Temp\jules_tmp\jules_external_v0.1.42_windows_amd64.tar.gz`
Diese Datei wird von Windows Temp-Bereinigungen oder von der CLI selbst gelöscht.
**Das ist KEIN Konfigurationsfehler und KEIN Deployment-Problem.**
**Lösung:** Die Tools `jules_remote_list` und `jules_remote_pull` kopieren das Backup (`sonu-cli-advanced/jules.tar.gz`) automatisch vor jedem Aufruf. Wenn der User fragt "Zeig mir Jules Sessions" → rufe `jules_remote_list()` auf. Fertig.

### Aktive Remote Jules Sessions (Stand: 26.05.2026):
- Seed 42:   Session ID `17720669482229403242` — IN_PROGRESS
- Seed 100:  Session ID `18340245822553121329` — IN_PROGRESS
- Seed 2026: Session ID `13889975897502573483` — IN_PROGRESS
- Seed 999:  Session ID `18285874929547409623` — IN_PROGRESS
- Seed 7:    In Warteschlange (wartet auf freien Slot)
Orchestrierung via: `C:\Users\user\.gemini\antigravity-ide\scratch\run_jules_multiseed.py`

