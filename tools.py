"""Agent-Werkzeuge fuer Sonu CLI: Datei- und Shell-Operationen mit Schema-Deklarationen.

Jedes Tool gibt einen String zurueck (Erfolg ODER lesbare Fehlermeldung), damit das
Modell aus Fehlern lernen und sich selbst korrigieren kann. Read-only-Tools sind als
sicher markiert und laufen ohne Rueckfrage; schreibende/ausfuehrende Tools verlangen
eine Bestaetigung durch den Aufrufer.
"""

import os
import subprocess
from google.genai import types

# Maximale Ausgabelaenge, die wir ans Modell zurueckgeben (Token-Schutz).
_MAX_OUTPUT = 20000


def _truncate(text: str) -> str:
    if len(text) > _MAX_OUTPUT:
        return (
            text[:_MAX_OUTPUT]
            + f"\n\n[... gekuerzt, {len(text) - _MAX_OUTPUT} Zeichen weggelassen ...]"
        )
    return text


def read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return _truncate(content) if content else "(Datei ist leer)"
    except FileNotFoundError:
        return f"FEHLER: Datei nicht gefunden: {path}"
    except IsADirectoryError:
        return f"FEHLER: '{path}' ist ein Verzeichnis, keine Datei. Nutze list_dir."
    except Exception as e:
        return f"FEHLER beim Lesen von '{path}': {e}"


def list_dir(path: str = ".") -> str:
    try:
        entries = sorted(os.listdir(path))
        if not entries:
            return f"(Verzeichnis '{path}' ist leer)"
        lines = []
        for name in entries:
            full = os.path.join(path, name)
            marker = "[DIR] " if os.path.isdir(full) else "      "
            size = ""
            if os.path.isfile(full):
                try:
                    size = f"  ({os.path.getsize(full)} B)"
                except OSError:
                    size = ""
            lines.append(f"{marker}{name}{size}")
        return _truncate("\n".join(lines))
    except FileNotFoundError:
        return f"FEHLER: Verzeichnis nicht gefunden: {path}"
    except Exception as e:
        return f"FEHLER beim Auflisten von '{path}': {e}"


def search_files(pattern: str, path: str = ".") -> str:
    """Sucht 'pattern' (Teilstring, case-insensitive) in allen Textdateien unter 'path'."""
    import fnmatch

    matches = []
    needle = pattern.lower()
    skip_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv"}
    try:
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for fname in files:
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        for lineno, line in enumerate(f, 1):
                            if needle in line.lower():
                                matches.append(
                                    f"{fpath}:{lineno}: {line.strip()[:200]}"
                                )
                                if len(matches) >= 200:
                                    matches.append(
                                        "[... weitere Treffer abgeschnitten ...]"
                                    )
                                    return _truncate("\n".join(matches))
                except (OSError, UnicodeError):
                    continue
        if not matches:
            return f"Keine Treffer fuer '{pattern}' unter '{path}'."
        return _truncate("\n".join(matches))
    except Exception as e:
        return f"FEHLER bei der Suche: {e}"


def write_file(path: str, content: str) -> str:
    try:
        parent = os.path.dirname(os.path.abspath(path))
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"OK: {len(content)} Zeichen nach '{path}' geschrieben."
    except Exception as e:
        return f"FEHLER beim Schreiben von '{path}': {e}"


def edit_file(path: str, old_string: str, new_string: str) -> str:
    """Ersetzt 'old_string' durch 'new_string' in einer Datei (chirurgischer Edit).

    'old_string' muss exakt EINMAL vorkommen, sonst wird abgebrochen, damit nicht
    versehentlich die falsche Stelle geaendert wird.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return f"FEHLER: Datei nicht gefunden: {path}. Nutze write_file, um sie neu anzulegen."
    except Exception as e:
        return f"FEHLER beim Lesen von '{path}': {e}"

    count = content.count(old_string)
    if count == 0:
        return f"FEHLER: Der zu ersetzende Text wurde in '{path}' nicht gefunden."
    if count > 1:
        return (
            f"FEHLER: Der zu ersetzende Text kommt {count}x in '{path}' vor. "
            "Gib mehr Kontext an, damit die Stelle eindeutig ist."
        )

    new_content = content.replace(old_string, new_string)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return f"OK: 1 Stelle in '{path}' ersetzt ({len(old_string)} -> {len(new_string)} Zeichen)."
    except Exception as e:
        return f"FEHLER beim Schreiben von '{path}': {e}"


def run_shell(command: str) -> str:
    """Fuehrt einen Befehl in PowerShell aus (Windows-Standardshell des Nutzers)."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=120,
        )
        out = result.stdout or ""
        err = result.stderr or ""
        combined = ""
        if out:
            combined += out
        if err:
            combined += ("\n[stderr]\n" + err) if combined else ("[stderr]\n" + err)
        combined = combined.strip() or "(kein Output)"
        return _truncate(f"[exit {result.returncode}]\n{combined}")
    except subprocess.TimeoutExpired:
        return "FEHLER: Befehl hat das Zeitlimit von 120s ueberschritten."
    except Exception as e:
        return f"FEHLER bei der Ausfuehrung: {e}"


_process_manager = None


def set_process_manager(pm):
    global _process_manager
    _process_manager = pm


def start_background_task(command: str) -> str:
    """Startet einen PowerShell-Befehl asynchron im Hintergrund (keine Blockade des CLIs)."""
    if not _process_manager:
        return "FEHLER: ProcessManager nicht initialisiert."
    try:
        tid = _process_manager.start_task(command)
        return f"OK: Hintergrundprozess gestartet mit Task-ID {tid}."
    except Exception as e:
        return f"FEHLER beim Starten des Hintergrundprozesses: {e}"


def list_background_tasks() -> str:
    """Listet alle aktiven und kuerzlich beendeten Hintergrund-Tasks auf."""
    if not _process_manager:
        return "FEHLER: ProcessManager nicht initialisiert."
    try:
        tasks = _process_manager.list_tasks()
        if not tasks:
            return "(Keine Hintergrundprozesse aktiv)"
        lines = []
        for t in tasks:
            lines.append(
                f"Task-ID {t['id']}: '{t['command']}' - Status: {t['status']} (Laufzeit: {t['elapsed']})"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"FEHLER beim Auflisten der Hintergrundprozesse: {e}"


def read_background_task_output(task_id: int, tail_lines: int = 25) -> str:
    """Liest den kuerzlichen Output (stdout/stderr) eines Hintergrund-Tasks aus."""
    if not _process_manager:
        return "FEHLER: ProcessManager nicht initialisiert."
    try:
        return _process_manager.read_task_output(task_id, tail_lines)
    except Exception as e:
        return f"FEHLER beim Lesen der Task-Ausgabe: {e}"


def kill_background_task(task_id: int) -> str:
    """Beendet einen aktiven Hintergrundprozess gewaltsam."""
    if not _process_manager:
        return "FEHLER: ProcessManager nicht initialisiert."
    try:
        _process_manager.kill_task(task_id)
        return f"OK: Task {task_id} wurde beendet."
    except Exception as e:
        return f"FEHLER beim Beenden des Tasks {task_id}: {e}"


def delegate_to_jules(prompt: str) -> str:
    """Delegiert eine komplexe, repo-weite Coding-Aufgabe headless an Google Jules im Hintergrund."""
    if not _process_manager:
        return "FEHLER: ProcessManager nicht initialisiert."
    try:
        curr_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(curr_dir, "jules_delegator.py")
        cmd = f'python "{script_path}" "{prompt}"'
        tid = _process_manager.start_task(cmd)
        return f"OK: Google Jules Delegierung im Hintergrund gestartet (Task-ID {tid}). Nutze read_background_task_output, um den Fortschritt zu sehen."
    except Exception as e:
        return f"FEHLER beim Starten der Jules-Delegierung: {e}"


def delegate_to_subagent(task_description: str, provider: str = None) -> str:
    """Delegiert eine isolierte Teilaufgabe an einen autonomen Sub-Agenten (headless)."""
    try:
        from sonu_client import SonuClient
        import terminal_ui
        import providers

        # Headless UI mock
        class HeadlessUI(terminal_ui.TerminalUI):
            def __init__(self):
                super().__init__()
                self.yolo = True  # Immer durchlaufen ohne zu fragen
                self.log = []

            def show_spinner(self, message="..."):
                class DummyContext:
                    def __enter__(self):
                        pass

                    def __exit__(self, *args):
                        pass

                return DummyContext()

            def display_response(self, text):
                self.log.append(f"Ergebnis: {text}")

            def display_stream(self, stream):
                return ""

            def show_error(self, err):
                self.log.append(f"Fehler: {err}")

            def show_info(self, info):
                self.log.append(f"Info: {info}")

            def show_agent_thought(self, text):
                pass

            def show_tool_call(self, name, args):
                self.log.append(f"-> Sub-Agent fuehrt '{name}' aus...")

            def show_tool_result(self, name, result, rejected=False):
                pass

            def confirm_action(self, name, args):
                return True

        ui = HeadlessUI()
        client = SonuClient()

        # Override provider if specified
        if provider and providers.get_provider(provider):
            client.set_provider(provider)

        ui.log.append(
            f"=== Starte autonomen Sub-Agenten (Provider: {client.provider}) ==="
        )

        final_answer = client.run_agent_turn(
            f"SUB-AGENT TASK: {task_description}\nErledige dies autonom. Verwende deine Werkzeuge (lies Dateien, suche, etc). Antworte am Ende mit einer ausfuehrlichen, endgueltigen Zusammenfassung deiner Ergebnisse und Analysen.",
            ui,
            max_steps=15,
        )

        summary = "\n".join(ui.log)
        return f"--- Sub-Agent Execution Log ---\n{summary}\n\n--- Sub-Agent Final Answer ---\n{final_answer}"
    except Exception as e:
        return f"FEHLER bei Sub-Agenten-Delegierung: {e}"


def create_git_branch(branch_name: str) -> str:
    """Erstellt einen neuen Git-Branch und wechselt in diesen."""
    try:
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            check=True,
            capture_output=True,
            text=True,
        )
        result = subprocess.run(
            ["git", "checkout", "-b", branch_name],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return f"OK: Branch '{branch_name}' erstellt und ausgecheckt."
        return f"FEHLER: Konnte Branch nicht erstellen.\n{result.stderr.strip()}"
    except subprocess.CalledProcessError:
        return "FEHLER: Nicht in einem Git-Repository."
    except Exception as e:
        return f"FEHLER bei Git-Branch-Erstellung: {e}"


def commit_git_changes(message: str) -> str:
    """Fuegt alle Aenderungen hinzu und committet sie."""
    try:
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(["git", "add", "."], check=True, capture_output=True, text=True)
        result = subprocess.run(
            ["git", "commit", "-m", message],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return f"OK: Aenderungen committet mit Nachricht '{message}'.\n{result.stdout.strip()}"
        elif "nothing to commit" in result.stdout:
            return "OK: Keine Aenderungen zu committen."
        return f"FEHLER beim Committen.\nstdout: {result.stdout.strip()}\nstderr: {result.stderr.strip()}"
    except subprocess.CalledProcessError as e:
        if e.cmd[1] == "add":
            return f"FEHLER beim Hinzufuegen der Dateien: {e.stderr}"
        return "FEHLER: Nicht in einem Git-Repository."
    except Exception as e:
        return f"FEHLER beim Committen: {e}"


def create_github_pull_request(title: str, body: str) -> str:
    """Erstellt einen Pull Request via GitHub CLI (gh)."""
    try:
        formatted_body = f"""# {title}

## Description
{body}

---
*Created automatically by Sonu CLI*
"""
        result = subprocess.run(
            ["gh", "pr", "create", "--title", title, "--body", formatted_body],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return (
                f"OK: Pull Request erfolgreich erstellt.\nURL: {result.stdout.strip()}"
            )
        return f"FEHLER beim Erstellen des Pull Requests.\n{result.stderr.strip()}"
    except FileNotFoundError:
        return "FEHLER: GitHub CLI (gh) ist nicht installiert oder nicht im PATH."
    except Exception as e:
        return f"FEHLER bei Pull-Request-Erstellung: {e}"


# ---------------------------------------------------------------------------
# Registry: name -> dict(func, declaration, safe)
# 'safe' = read-only, laeuft ohne Bestaetigung.
# ---------------------------------------------------------------------------


def _schema(props: dict, required: list) -> types.Schema:
    return types.Schema(type=types.Type.OBJECT, properties=props, required=required)


def _str(desc: str) -> types.Schema:
    return types.Schema(type=types.Type.STRING, description=desc)


REGISTRY = {
    "create_git_branch": {
        "func": create_git_branch,
        "safe": False,
        "declaration": types.FunctionDeclaration(
            name="create_git_branch",
            description="Erstellt einen neuen Git-Branch und wechselt dorthin.",
            parameters=_schema(
                {"branch_name": _str("Name des neuen Branches")}, ["branch_name"]
            ),
        ),
    },
    "commit_git_changes": {
        "func": commit_git_changes,
        "safe": False,
        "declaration": types.FunctionDeclaration(
            name="commit_git_changes",
            description="Fuegt alle Aenderungen ('git add .') hinzu und committet sie mit der angegebenen Nachricht.",
            parameters=_schema({"message": _str("Die Commit-Nachricht")}, ["message"]),
        ),
    },
    "create_github_pull_request": {
        "func": create_github_pull_request,
        "safe": False,
        "declaration": types.FunctionDeclaration(
            name="create_github_pull_request",
            description="Erstellt einen Pull Request auf GitHub mittels 'gh' CLI.",
            parameters=_schema(
                {
                    "title": _str("Titel des Pull Requests"),
                    "body": _str(
                        "Inhalt/Beschreibung des Pull Requests (wird als Markdown formatiert)"
                    ),
                },
                ["title", "body"],
            ),
        ),
    },
    "read_file": {
        "func": read_file,
        "safe": True,
        "declaration": types.FunctionDeclaration(
            name="read_file",
            description="Liest den vollstaendigen Inhalt einer Textdatei und gibt ihn zurueck.",
            parameters=_schema(
                {"path": _str("Pfad zur Datei, relativ oder absolut.")}, ["path"]
            ),
        ),
    },
    "list_dir": {
        "func": list_dir,
        "safe": True,
        "declaration": types.FunctionDeclaration(
            name="list_dir",
            description="Listet Dateien und Unterordner eines Verzeichnisses auf.",
            parameters=_schema(
                {"path": _str("Verzeichnispfad. Standard: aktuelles Verzeichnis '.'.")},
                [],
            ),
        ),
    },
    "search_files": {
        "func": search_files,
        "safe": True,
        "declaration": types.FunctionDeclaration(
            name="search_files",
            description="Durchsucht alle Textdateien unter einem Pfad nach einem Teilstring (case-insensitive) und gibt Datei:Zeile:Inhalt zurueck.",
            parameters=_schema(
                {
                    "pattern": _str("Zu suchender Text."),
                    "path": _str("Startverzeichnis der Suche. Standard '.'."),
                },
                ["pattern"],
            ),
        ),
    },
    "write_file": {
        "func": write_file,
        "safe": False,
        "declaration": types.FunctionDeclaration(
            name="write_file",
            description="Schreibt Inhalt in eine Datei (ueberschreibt vorhandene). Legt fehlende Ordner an.",
            parameters=_schema(
                {
                    "path": _str("Zielpfad der Datei."),
                    "content": _str(
                        "Vollstaendiger Inhalt, der geschrieben werden soll."
                    ),
                },
                ["path", "content"],
            ),
        ),
    },
    "edit_file": {
        "func": edit_file,
        "safe": False,
        "declaration": types.FunctionDeclaration(
            name="edit_file",
            description="Ersetzt eine eindeutige Textstelle in einer bestehenden Datei (chirurgischer Edit). Bevorzugt gegenueber write_file, wenn nur ein Teil geaendert werden soll.",
            parameters=_schema(
                {
                    "path": _str("Pfad zur zu bearbeitenden Datei."),
                    "old_string": _str(
                        "Exakter, eindeutiger Text, der ersetzt werden soll (inkl. Einrueckung)."
                    ),
                    "new_string": _str("Der neue Text, der an die Stelle tritt."),
                },
                ["path", "old_string", "new_string"],
            ),
        ),
    },
    "run_shell": {
        "func": run_shell,
        "safe": False,
        "declaration": types.FunctionDeclaration(
            name="run_shell",
            description="Fuehrt einen PowerShell-Befehl aus und gibt Exit-Code, stdout und stderr zurueck.",
            parameters=_schema(
                {"command": _str("Der auszufuehrende PowerShell-Befehl.")}, ["command"]
            ),
        ),
    },
    "start_background_task": {
        "func": start_background_task,
        "safe": False,
        "declaration": types.FunctionDeclaration(
            name="start_background_task",
            description="Startet einen PowerShell-Befehl asynchron im Hintergrund, ohne die REPL zu blockieren.",
            parameters=_schema(
                {
                    "command": _str(
                        "Der im Hintergrund auszufuehrende PowerShell-Befehl."
                    )
                },
                ["command"],
            ),
        ),
    },
    "list_background_tasks": {
        "func": list_background_tasks,
        "safe": True,
        "declaration": types.FunctionDeclaration(
            name="list_background_tasks",
            description="Listet alle laufenden und kuerzlich beendeten asynchronen Hintergrundprozesse auf.",
            parameters=_schema({}, []),
        ),
    },
    "read_background_task_output": {
        "func": read_background_task_output,
        "safe": True,
        "declaration": types.FunctionDeclaration(
            name="read_background_task_output",
            description="Liest die Ausgaben (stdout/stderr) eines bestimmten Hintergrund-Tasks.",
            parameters=_schema(
                {
                    "task_id": types.Schema(
                        type=types.Type.INTEGER, description="ID des Tasks."
                    ),
                    "tail_lines": types.Schema(
                        type=types.Type.INTEGER,
                        description="Anzahl der Zeilen vom Ende des Logs (Standard: 25).",
                    ),
                },
                ["task_id"],
            ),
        ),
    },
    "kill_background_task": {
        "func": kill_background_task,
        "safe": False,
        "declaration": types.FunctionDeclaration(
            name="kill_background_task",
            description="Beendet einen laufenden Hintergrund-Task gewaltsam.",
            parameters=_schema(
                {
                    "task_id": types.Schema(
                        type=types.Type.INTEGER,
                        description="ID des zu beendenden Tasks.",
                    )
                },
                ["task_id"],
            ),
        ),
    },
    "delegate_to_jules": {
        "func": delegate_to_jules,
        "safe": False,
        "declaration": types.FunctionDeclaration(
            name="delegate_to_jules",
            description="Delegiert eine komplexe Programmieraufgabe an Google Jules headless im Hintergrund. Polle danach den Output, um die Fertigstellung zu ueberwachen.",
            parameters=_schema(
                {"prompt": _str("Detaillierter Prompt der Aufgabe fuer Google Jules.")},
                ["prompt"],
            ),
        ),
    },
    "delegate_to_subagent": {
        "func": delegate_to_subagent,
        "safe": False,
        "declaration": types.FunctionDeclaration(
            name="delegate_to_subagent",
            description="Delegiert eine Recherche, Analyse oder Coding-Teilaufgabe an einen isolierten, autonomen Sonu-Subagenten. Verhindert, dass dein eigener Kontext ueberflutet wird. Gib ihm eine SEHR ausfuehrliche Anweisung.",
            parameters=_schema(
                {
                    "task_description": _str(
                        "Detaillierte Anweisung und Ziel fuer den Sub-Agenten."
                    ),
                    "provider": _str(
                        "Optional: Spezifischer Provider (z.B. 'groq', 'xai', 'gemini') fuer den Subagenten."
                    ),
                },
                ["task_description"],
            ),
        ),
    },
    "invoke_swarm_consensus": {
        "func": lambda prompt: __import__("debate_engine").invoke_swarm(prompt),
        "safe": True,
        "declaration": types.FunctionDeclaration(
            name="invoke_swarm_consensus",
            description="Invokes the SwarmConsensusEngine, which spins up multiple parallel AI agents (using different providers like Gemini, Groq, OpenRouter) to debate and synthesize the ultimate top-level answer to a complex prompt.",
            parameters=_schema(
                {
                    "prompt": _str(
                        "The complex question or task for the parallel swarm to answer."
                    )
                },
                ["prompt"],
            ),
        ),
    },
    "consult_expert_panel": {
        "func": lambda task: __import__("expert_agents").consult_expert_panel(task),
        "safe": True,
        "declaration": types.FunctionDeclaration(
            name="consult_expert_panel",
            description="Assembles a Mixture of Experts (MoE) panel containing a Performance Architect, Security Auditor, and Clean Code Guru. They analyze the task in parallel and a Master Synthesizer fuses their insights into a definitive master plan.",
            parameters=_schema(
                {
                    "task": _str(
                        "The complex task, architecture question, or problem to be analyzed by the experts."
                    )
                },
                ["task"],
            ),
        ),
    },
}


def get_tool_object() -> types.Tool:
    """Baut das types.Tool mit allen Funktionsdeklarationen fuer die GenerateContentConfig."""
    return types.Tool(
        function_declarations=[t["declaration"] for t in REGISTRY.values()]
    )


def _type_to_str(t) -> str:
    """google-genai types.Type (Enum oder String) -> JSON-Schema-Typ-String."""
    if t is None:
        return "string"
    name = getattr(t, "name", None) or str(t)
    return name.split(".")[-1].lower()


def _schema_to_json(schema) -> dict:
    """Konvertiert ein google-genai types.Schema rekursiv in ein OpenAI/JSON-Schema-Dict."""
    if schema is None:
        return {"type": "object", "properties": {}}
    out = {"type": _type_to_str(getattr(schema, "type", None))}
    desc = getattr(schema, "description", None)
    if desc:
        out["description"] = desc
    props = getattr(schema, "properties", None)
    if props:
        out["properties"] = {k: _schema_to_json(v) for k, v in props.items()}
    required = getattr(schema, "required", None)
    if required:
        out["required"] = list(required)
    items = getattr(schema, "items", None)
    if items is not None:
        out["items"] = _schema_to_json(items)
    if out["type"] == "object" and "properties" not in out:
        out["properties"] = {}
    return out


def get_openai_tools() -> list:
    """Baut die Tool-Liste im OpenAI-Function-Calling-Format aus der REGISTRY."""
    specs = []
    for entry in REGISTRY.values():
        decl = entry["declaration"]
        specs.append(
            {
                "type": "function",
                "function": {
                    "name": decl.name,
                    "description": decl.description or "",
                    "parameters": _schema_to_json(getattr(decl, "parameters", None)),
                },
            }
        )
    return specs


def is_safe(name: str) -> bool:
    entry = REGISTRY.get(name)
    return bool(entry and entry["safe"])


def dispatch(name: str, args: dict) -> str:
    """Fuehrt das benannte Tool mit den gegebenen Argumenten aus."""
    entry = REGISTRY.get(name)
    if not entry:
        return f"FEHLER: Unbekanntes Tool '{name}'."
    try:
        return entry["func"](**(args or {}))
    except TypeError as e:
        return f"FEHLER: Falsche Argumente fuer '{name}': {e}"
    except Exception as e:
        return f"FEHLER bei Tool '{name}': {e}"
