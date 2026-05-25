# Multi-Provider-Integration — Handoff-Plan

Ziel: Sonu CLI soll neben Gemini auch **xAI (Grok), Groq, OpenRouter und Hugging Face**
nutzen koennen. Alle vier sind OpenAI-kompatibel und werden ueber EINE Adapter-Schicht
(`openai`-SDK mit unterschiedlicher `base_url`) angesprochen. Gemini bleibt unveraendert
auf dem `google-genai`-Pfad.

Status: ~50% fertig. Unten steht exakt, was erledigt ist und was noch fehlt.

---

## BEREITS ERLEDIGT (nicht erneut machen)

1. **Sicherheit**
   - `.gitignore` angelegt (ignoriert `.env`, `__pycache__/`, `logs/`, `.sonu/`, `*.log`, `SONU.local.md`).
   - `.env` und `__pycache__` aus dem Git-Index entfernt (`git rm --cached`), Dateien bleiben auf Platte.
   - OFFEN (manuell durch Nutzer): der ALTE Baseline-Commit enthaelt noch die alte `.env` mit Keys.
     Da nie gepusht → geringes Risiko. Echte Loesung: Keys rotieren oder History scrubben (git filter-repo).

2. **`.env`** — 4 neue Keys ergaenzt: `XAI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `HF_TOKEN`.

3. **`requirements.txt`** — `openai` hinzugefuegt. (SDK 2.38.0 ist installiert.)

4. **`providers.py`** — fertig. Enthaelt `PROVIDERS` (gemini, xai, groq, openrouter, huggingface)
   mit label/kind/env_var/base_url/default_model, plus `get_provider(name)` und `list_providers()`.

5. **`tools.py`** — Konverter ergaenzt:
   - `_type_to_str(t)`, `_schema_to_json(schema)` (rekursiv google-genai Schema -> JSON-Schema)
   - `get_openai_tools()` -> Tool-Liste im OpenAI-Function-Calling-Format aus der REGISTRY.
   Die bestehende `dispatch(name, args)` und `is_safe(name)` werden vom OpenAI-Pfad mitbenutzt.

---

## NOCH ZU TUN

### Schritt 1 — `openai_agent.py` (NEU anlegen)

Eine Klasse `OpenAICompatibleAgent`, die denselben agentischen Loop wie
`SonuClient.run_agent_turn` bietet, aber ueber das `openai`-SDK laeuft. Sie teilt sich
die Manager (skills_mgr, memory_mgr, process_mgr) mit dem SonuClient.

Wichtige Designpunkte:
- Konstruktor bekommt: `provider_name`, `model`, und eine Referenz auf den `SonuClient`
  (fuer `skills_mgr`, `memory_mgr`, und die Basis-`SYSTEM_INSTRUCTION`).
- `from openai import OpenAI`; Client = `OpenAI(api_key=os.getenv(env_var), base_url=base_url)`.
- System-Prompt identisch komponieren wie im Gemini-Pfad: BASE `SYSTEM_INSTRUCTION`
  + aktives Skill (`skills_mgr`) + 4-Ebenen-Memory (`memory_mgr.load_memory(os.getcwd())`).
- Tools = `tools.get_openai_tools()` PLUS das `activate_skill`-Tool (siehe unten), als
  OpenAI-Spec angehaengt.
- `self.messages` haelt den Verlauf pro Session (beginnend mit dem System-Prompt).
  Bei Skill-Wechsel die system-Message (messages[0]) neu setzen.

Loop-Skizze fuer `run_agent_turn(self, user_input, ui, max_steps=25)`:
```python
self.messages.append({"role": "user", "content": user_input})
for _ in range(max_steps):
    resp = self.client.chat.completions.create(
        model=self.model, messages=self.messages,
        tools=self.tool_specs, tool_choice="auto",
    )
    msg = resp.choices[0].message
    if not msg.tool_calls:
        self.messages.append({"role": "assistant", "content": msg.content or ""})
        return (msg.content or "").strip()
    # Assistant-Turn mit tool_calls in den Verlauf aufnehmen (WICHTIG: exakt so zurueckgeben)
    self.messages.append({
        "role": "assistant",
        "content": msg.content or "",
        "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
    })
    for tc in msg.tool_calls:
        name = tc.function.name
        import json
        try:
            args = json.loads(tc.function.arguments or "{}")
        except Exception:
            args = {}
        ui.show_tool_call(name, args)
        # activate_skill wird lokal behandelt (wie im Gemini-Pfad)
        if name == "activate_skill":
            ok, m = self._set_skill(args.get("name"))
            ui.show_tool_result(name, m, rejected=not ok)
            result = m
        else:
            if not tools.is_safe(name) and not ui.confirm_action(name, args):
                result = "ABGELEHNT: Der Nutzer hat diese Aktion abgelehnt."
                ui.show_tool_result(name, result, rejected=True)
            else:
                result = tools.dispatch(name, args)
                ui.show_tool_result(name, result)
        self.messages.append({
            "role": "tool", "tool_call_id": tc.id, "content": str(result),
        })
return "(Abbruch: maximale Anzahl an Tool-Schritten erreicht.)"
```
- `_set_skill(name)`: ruft `skills_mgr.activate_skill/deactivate_skill`, baut messages[0]
  (system) neu. Verlauf NICHT loeschen.
- Quota/Rate-Limit (429): `openai.RateLimitError` abfangen; OpenRouter/xAI/Groq haben je
  EINEN Key (keine Pool-Rotation noetig) -> Fehler sauber an `ui.show_error` zurueckgeben.
- Gotcha HF: nicht jedes HF-Modell unterstuetzt tool_calls. Wenn `tools` 400 wirft,
  Fallback: Request ohne `tools` wiederholen (reiner Chat). Optional, aber empfohlen.
- Gotcha OpenRouter: optionale Header `extra_headers={"HTTP-Referer": "...", "X-Title": "Sonu CLI"}`
  via `default_headers` beim Client moeglich, nicht zwingend.

`activate_skill`-OpenAI-Spec (im Agent zusammenbauen, da skill-namen dynamisch):
```python
{"type": "function", "function": {
  "name": "activate_skill",
  "description": "Aktiviert ein Experten-Skill-Profil. name='off' deaktiviert. Verfuegbar: " + ", ".join(skills_mgr.list_skills()),
  "parameters": {"type": "object",
    "properties": {"name": {"type": "string", "description": "Skill-Name oder 'off'."}},
    "required": ["name"]}}}
```

### Schritt 2 — `sonu_client.py` (Provider-Switching)

- `import providers`, `from openai_agent import OpenAICompatibleAgent`.
- In `__init__`: `self.provider = "gemini"`, `self.oa_agents = {}` (Cache).
- Neue Methode `set_provider(name)`:
  - validiert via `providers.get_provider(name)`; prueft, ob der env_var-Key gesetzt ist.
  - setzt `self.provider`; bei kind=="openai" Agent aus Cache holen/erstellen
    (`OpenAICompatibleAgent(name, default_model, self)`), Manager teilen.
  - Rueckgabe (ok, nachricht).
- `run_agent_turn(user_input, ui)`: wenn `self.provider == "gemini"` -> bestehender Loop;
  sonst `return self.oa_agents[self.provider].run_agent_turn(user_input, ui)`.
- `set_model(model)`: wenn Gemini -> wie bisher; sonst Modell am aktiven OpenAI-Agenten setzen.
- `list_available_models()`: optional pro Provider (Gemini wie bisher; OpenAI-Provider
  koennen `self.client.models.list()` anbieten — bei manchen 404, dann leere Liste/Hinweis).

### Schritt 3 — `main.py` (Befehle)

- `import providers`.
- Neuer Befehl `/provider`:
  - ohne Arg: aktuellen Provider + Liste aller `providers.list_providers()` mit Label zeigen.
  - mit Arg: `client.set_provider(arg)` -> Erfolg/Fehler via ui.
- `/help`-Tabelle (in `terminal_ui.py show_help`) um `/provider` ergaenzen.
- Optional: aktiven Provider im Welcome/Prompt anzeigen.

### Schritt 4 — Test

- Syntaxcheck aller Module.
- Provider-Switch ohne API: `set_provider("groq")` -> ok, Agent angelegt.
- EIN echter Tool-Calling-Turn ueber Groq (meist groesszuegige Quota), z.B.
  "Liste die Dateien hier auf" -> erwartet `list_dir`-Tool-Call + finale Antwort.
  Mit FakeUI (yolo=True) testen, damit keine stdin-Bestaetigung noetig ist.
- Achtung Default-Modellnamen in `providers.py` ggf. anpassen, falls ein Anbieter den
  Namen ablehnt (xai: evtl. "grok-3"/"grok-2-1212"; openrouter/hf: exakte Repo-IDs).

---

## Designentscheidungen (Begruendung)
- EINE OpenAI-Adapter-Klasse statt 4 SDKs: xAI/Groq/OpenRouter/HF sind alle OpenAI-kompatibel
  -> nur base_url + key unterscheiden sich. Minimaler Code, maximale Abdeckung.
- Gemini bleibt nativ: voller getesteter Funktionsumfang (Function-Calling, Key-Pool-Rotation).
- Tools werden NICHT dupliziert: derselbe `tools.REGISTRY` + `dispatch`; nur das Schema wird
  per `get_openai_tools()` ins OpenAI-Format konvertiert.
- Manager (skills/memory/process) werden geteilt -> Skills, Gedaechtnis und Hintergrund-Tasks
  funktionieren provider-uebergreifend identisch.
```
