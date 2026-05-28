"""
JIT (Just-In-Time) Context — portiert von Google Gemini CLI jit-context.ts
Lädt SONU.md Dateien dynamisch wenn Tools auf Verzeichnisse zugreifen.
"""
import os

JIT_PREFIX = "\n\n--- Projekt-Kontext (SONU.md) ---\n"
JIT_SUFFIX = "\n--- Ende Kontext ---"
MAX_JIT_CHARS = 2000

# Session-Cache: welche SONU.md Dateien wurden bereits injiziert
_loaded_paths: set[str] = set()

# Tools die JIT-Kontext auslösen
JIT_TRIGGER_TOOLS = {"read_file", "write_file", "replace", "grep_search", "list_directory", "edit_many"}


def discover_jit_context(accessed_path: str, workspace_root: str) -> str:
    """
    Läuft von accessed_path aufwärts bis workspace_root.
    Sammelt SONU.md Inhalte die noch nicht geladen wurden.
    Gibt "" zurück wenn nichts Neues gefunden.
    """
    try:
        accessed_path = os.path.abspath(accessed_path)
        workspace_root = os.path.abspath(workspace_root)

        # Wenn accessed_path eine Datei ist: mit dem Verzeichnis starten
        if os.path.isfile(accessed_path):
            current = os.path.dirname(accessed_path)
        else:
            current = accessed_path

        collected = []

        while True:
            sonu_md = os.path.join(current, "SONU.md")
            if os.path.isfile(sonu_md) and sonu_md not in _loaded_paths:
                try:
                    with open(sonu_md, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                    if content:
                        _loaded_paths.add(sonu_md)
                        collected.append(f"[{os.path.relpath(sonu_md, workspace_root)}]\n{content}")
                except Exception:
                    pass

            # Aufhören wenn workspace_root erreicht
            if os.path.abspath(current) == workspace_root:
                break
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent

        if not collected:
            return ""

        result = "\n\n".join(collected)
        if len(result) > MAX_JIT_CHARS:
            result = result[:MAX_JIT_CHARS] + "\n...[gekürzt]"
        return result

    except Exception:
        return ""


def append_jit_context(tool_output: str, jit_context: str) -> str:
    """Hängt JIT-Kontext an Tool-Output an. Gibt tool_output unverändert zurück wenn leer."""
    if not jit_context:
        return tool_output
    return f"{tool_output}{JIT_PREFIX}{jit_context}{JIT_SUFFIX}"


def reset_session_cache():
    """Leert den Session-Cache — aufrufen bei /clear."""
    _loaded_paths.clear()


def extract_path_from_args(tool_name: str, args: dict) -> str | None:
    """Extrahiert den Dateipfad aus Tool-Argumenten."""
    for key in ("path", "file_path", "filepath", "directory", "dir"):
        val = args.get(key)
        if val and isinstance(val, str):
            return val
    return None
