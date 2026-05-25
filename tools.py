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
        return text[:_MAX_OUTPUT] + f"\n\n[... gekuerzt, {len(text) - _MAX_OUTPUT} Zeichen weggelassen ...]"
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
                                matches.append(f"{fpath}:{lineno}: {line.strip()[:200]}")
                                if len(matches) >= 200:
                                    matches.append("[... weitere Treffer abgeschnitten ...]")
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


# ---------------------------------------------------------------------------
# Registry: name -> dict(func, declaration, safe)
# 'safe' = read-only, laeuft ohne Bestaetigung.
# ---------------------------------------------------------------------------

def _schema(props: dict, required: list) -> types.Schema:
    return types.Schema(type=types.Type.OBJECT, properties=props, required=required)


def _str(desc: str) -> types.Schema:
    return types.Schema(type=types.Type.STRING, description=desc)


REGISTRY = {
    "read_file": {
        "func": read_file,
        "safe": True,
        "declaration": types.FunctionDeclaration(
            name="read_file",
            description="Liest den vollstaendigen Inhalt einer Textdatei und gibt ihn zurueck.",
            parameters=_schema({"path": _str("Pfad zur Datei, relativ oder absolut.")}, ["path"]),
        ),
    },
    "list_dir": {
        "func": list_dir,
        "safe": True,
        "declaration": types.FunctionDeclaration(
            name="list_dir",
            description="Listet Dateien und Unterordner eines Verzeichnisses auf.",
            parameters=_schema({"path": _str("Verzeichnispfad. Standard: aktuelles Verzeichnis '.'.")}, []),
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
                    "content": _str("Vollstaendiger Inhalt, der geschrieben werden soll."),
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
                    "old_string": _str("Exakter, eindeutiger Text, der ersetzt werden soll (inkl. Einrueckung)."),
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
            parameters=_schema({"command": _str("Der auszufuehrende PowerShell-Befehl.")}, ["command"]),
        ),
    },
}


def get_tool_object() -> types.Tool:
    """Baut das types.Tool mit allen Funktionsdeklarationen fuer die GenerateContentConfig."""
    return types.Tool(function_declarations=[t["declaration"] for t in REGISTRY.values()])


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
