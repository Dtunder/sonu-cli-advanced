"""Agent-Werkzeuge fuer Sonu CLI: Die volle Power von Gemini CLI + Sonu Custom Addons.

Jedes Tool gibt einen String zurueck (Erfolg ODER lesbare Fehlermeldung).
Read-only-Tools sind als sicher markiert; schreibende/ausfuehrende Tools verlangen
eine Bestaetigung (ausser im YOLO-Modus).
"""

import os
import subprocess
import glob
import re
import time
import concurrent.futures

class LazyTypesProxy:
    def __getattr__(self, name):
        from google.genai import types
        return getattr(types, name)
types = LazyTypesProxy()

_MAX_OUTPUT = 20000

def _truncate(text: str) -> str:
    if len(text) > _MAX_OUTPUT:
        return text[:_MAX_OUTPUT] + f"\n\n[... gekuerzt, {len(text) - _MAX_OUTPUT} Zeichen weggelassen ...]"
    return text

# --- DATEI OPERATIONEN ---

def read_file(path: str, start_line: int = None, end_line: int = None) -> str:
    """Liest den Inhalt einer Textdatei. Unterstuetzt chirurgische Reads."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            if start_line is not None or end_line is not None:
                lines = f.readlines()
                start = (start_line - 1) if start_line else 0
                end = end_line if end_line else len(lines)
                content = "".join(lines[start:end])
                return _truncate(content) if content else "(Kein Inhalt im Bereich)"
            content = f.read()
        return _truncate(content) if content else "(Datei leer)"
    except Exception as e:
        return f"FEHLER beim Lesen von '{path}': {e}"

def list_dir(path: str = ".") -> str:
    """Listet Dateien und Verzeichnisse auf."""
    try:
        entries = sorted(os.listdir(path))
        lines = []
        for name in entries:
            full = os.path.join(path, name)
            marker = "[DIR] " if os.path.isdir(full) else "      "
            lines.append(f"{marker}{name}")
        return _truncate("\n".join(lines))
    except Exception as e:
        return f"FEHLER: {e}"

def glob_files(pattern: str, path: str = ".") -> str:
    """Findet Dateien via Glob-Pattern (z.B. '**/*.py')."""
    try:
        files = glob.glob(os.path.join(path, pattern), recursive=True)
        if not files: return "Keine Treffer."
        files.sort(key=lambda x: os.path.getmtime(x) if os.path.isfile(x) else 0, reverse=True)
        return _truncate("\n".join(files[:100]))
    except Exception as e:
        return f"FEHLER: {e}"

def grep_search(pattern: str, path: str = ".", context: int = 0) -> str:
    """Sucht Regex in Dateien mit Kontextzeilen. Nutzt ripgrep wenn verfügbar (10-50x schneller)."""
    # Try ripgrep first
    try:
        rg_args = ["rg", "--line-number", "--no-heading", "--color=never", "--max-count=200"]
        if context > 0:
            rg_args += ["-C", str(context)]
        rg_args += [pattern, path]
        result = subprocess.run(rg_args, capture_output=True, text=True, timeout=30)
        if result.returncode in (0, 1):  # 0=matches, 1=no matches
            out = result.stdout.strip()
            return _truncate(out) if out else "Keine Treffer."
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # rg not available, fall through to Python impl

    # Python fallback
    matches = []
    try: regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e: return f"Ungueltiger Regex: {e}"

    skip = {".git", "__pycache__", "node_modules", "venv"}
    try:
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in skip]
            for fname in files:
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                        for i, line in enumerate(lines):
                            if regex.search(line):
                                s, e = max(0, i-context), min(len(lines), i+context+1)
                                match_block = [f"{j+1:4}: {'>> ' if j==i else '   '}{lines[j].strip()[:200]}" for j in range(s, e)]
                                matches.append(f"--- {fpath} ---\n" + "\n".join(match_block))
                                if len(matches) >= 50: return _truncate("\n\n".join(matches) + "\n[Limit erreicht]")
                except: continue
        return _truncate("\n\n".join(matches)) if matches else "Keine Treffer."
    except Exception as e: return f"FEHLER: {e}"

def _show_diff(old_lines: list, new_lines: list, path: str) -> str:
    """Gibt einen farbigen unified diff als String zurück."""
    import difflib
    diff = list(difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{path}", tofile=f"b/{path}", lineterm=""))
    if not diff:
        return ""
    lines = []
    for line in diff[:80]:  # max 80 Zeilen zeigen
        if line.startswith("+++") or line.startswith("---"):
            lines.append(f"\033[1m{line}\033[0m")
        elif line.startswith("+"):
            lines.append(f"\033[32m{line}\033[0m")
        elif line.startswith("-"):
            lines.append(f"\033[31m{line}\033[0m")
        elif line.startswith("@@"):
            lines.append(f"\033[36m{line}\033[0m")
        else:
            lines.append(line)
    if len(diff) > 80:
        lines.append(f"\033[33m... +{len(diff)-80} weitere Zeilen ...\033[0m")
    return "\n".join(lines)


def _confirm_edit(path: str, diff_str: str) -> bool:
    """Zeigt Diff und fragt nach Bestätigung. Gibt True zurück bei yolo oder y/j."""
    import __main__
    ui = getattr(__main__, "ui", None)
    if ui and getattr(ui, "yolo", False):
        return True
    print(f"\n\033[1mDiff für {path}:\033[0m")
    print(diff_str)
    try:
        ans = input("\n  Apply? [y/N]: ").strip().lower()
        return ans in ("y", "yes", "j", "ja")
    except (EOFError, KeyboardInterrupt):
        return False


def write_file(path: str, content: str) -> str:
    """Schreibt/Ueberschreibt eine Datei. Zeigt Diff und fragt nach Bestätigung."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        old_lines = []
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    old_lines = f.readlines()
            except Exception:
                pass
        new_lines = content.splitlines(keepends=True)
        diff_str = _show_diff(old_lines, new_lines, path)
        if diff_str:
            if not _confirm_edit(path, diff_str):
                return "ABGEBROCHEN: Nutzer hat Änderung abgelehnt."
        with open(path, "w", encoding="utf-8") as f: f.write(content)
        return f"OK: {len(content)} Bytes geschrieben."
    except Exception as e: return f"FEHLER: {e}"

def replace(path: str, old_string: str, new_string: str) -> str:
    """Ersetzt Textstelle chirurgisch. Zeigt Diff und fragt nach Bestätigung."""
    try:
        with open(path, "r", encoding="utf-8") as f: content = f.read()
    except Exception as e: return f"FEHLER beim Lesen: {e}"

    count = content.count(old_string)
    if count == 0: return "FEHLER: 'old_string' nicht gefunden."
    if count > 1: return f"FEHLER: {count} Treffer. Sei praeziser."

    new_content = content.replace(old_string, new_string)
    old_lines = content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    diff_str = _show_diff(old_lines, new_lines, path)
    if diff_str:
        if not _confirm_edit(path, diff_str):
            return "ABGEBROCHEN: Nutzer hat Änderung abgelehnt."
    try:
        with open(path, "w", encoding="utf-8") as f: f.write(new_content)
        return "OK: 1 Stelle ersetzt."
    except Exception as e: return f"FEHLER beim Schreiben: {e}"

# --- SYSTEM & TOOLS ---

def run_shell(command: str, stream: bool = False, timeout: int = 600) -> str:
    """Fuehrt PowerShell-Befehl aus. stream=True gibt Output live im Terminal aus. timeout in Sekunden (default 600)."""
    try:
        proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", command],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace"
        )
        lines = []
        if stream:
            import sys
            for line in proc.stdout:
                print(line, end="", flush=True)
                lines.append(line)
            proc.wait(timeout=timeout)
        else:
            try:
                out, _ = proc.communicate(timeout=timeout)
                lines = [out]
            except subprocess.TimeoutExpired:
                proc.kill()
                return f"FEHLER: Timeout nach {timeout}s"
        full = "".join(lines).strip()
        return _truncate(f"[exit {proc.returncode}]\n{full or '(kein Output)'}")
    except Exception as e:
        return f"FEHLER: {e}"

# --- WEB & SUCHE ---

def web_fetch(url: str) -> str:
    """Ruft eine Webseite ab und extrahiert den Text."""
    import requests
    from bs4 import BeautifulSoup
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        for s in soup(["script", "style"]): s.decompose()
        text = soup.get_text(separator=' ', strip=True)
        return _truncate(text)
    except Exception as e: return f"FEHLER beim Web-Fetch: {e}"

def google_search(query: str) -> str:
    """Sucht im Web via DuckDuckGo (Gemini CLI Ersatz)."""
    from duckduckgo_search import DDGS
    try:
        with DDGS() as ddgs:
            results = [f"{r['title']}: {r['body']} ({r['href']})" for r in ddgs.text(query, max_results=5)]
        return "\n\n".join(results) if results else "Keine Ergebnisse."
    except Exception as e: return f"FEHLER bei Suche: {e}"

# --- ORCHESTRIERUNG ---

def update_topic(title: str, summary: str, strategic_intent: str = None) -> str:
    """Aktualisiert Kapitel-Status im UI."""
    try:
        import __main__
        if hasattr(__main__, 'ui'):
            __main__.ui.show_topic(title, summary, strategic_intent)
            return "Topic aktualisiert."
    except: pass
    return "OK"

def read_many_files(include: list, exclude: list = None, recursive: bool = True) -> str:
    """Liest mehrere Dateien via Glob-Pattern und gibt alle Inhalte konkateniert zurück.
    Portiert von Gemini CLI ReadManyFilesTool."""
    import fnmatch
    exclude = exclude or []
    DEFAULT_EXCLUDES = ["node_modules/**", ".git/**", "__pycache__/**", "*.pyc", "dist/**", "build/**", ".venv/**"]
    all_excludes = DEFAULT_EXCLUDES + exclude
    cwd = os.getcwd()
    matched = set()
    for pattern in include:
        try:
            found = glob.glob(os.path.join(cwd, pattern), recursive=recursive)
            for f in found:
                if os.path.isfile(f):
                    rel = os.path.relpath(f, cwd).replace("\\", "/")
                    skip = any(fnmatch.fnmatch(rel, ex.rstrip("/**") + "*") or fnmatch.fnmatch(rel, ex) for ex in all_excludes)
                    if not skip:
                        matched.add(f)
        except Exception:
            pass
    if not matched:
        return "Keine Dateien gefunden."
    parts = []
    skipped = []
    for fpath in sorted(matched):
        rel = os.path.relpath(fpath, cwd).replace("\\", "/")
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            if len(content) > 50000:
                content = content[:50000] + "\n[... gekürzt ...]"
            parts.append(f"--- {fpath} ---\n\n{content}\n\n")
        except Exception as e:
            skipped.append(f"{rel} ({e})")
    result = "".join(parts)
    if skipped:
        result += f"\n\nÜbersprungen: {', '.join(skipped)}"
    return _truncate(result)


# Session-Todo-Liste (in-memory, wird bei /clear resettet)
_todos: list = []

def write_todos(todos: list) -> str:
    """Setzt die komplette Todo-Liste. Portiert von Gemini CLI WriteTodosTool.
    todos: Liste von {description: str, status: pending|in_progress|completed|cancelled|blocked}"""
    global _todos
    VALID_STATUSES = {"pending", "in_progress", "completed", "cancelled", "blocked"}
    if not isinstance(todos, list):
        return "FEHLER: todos muss eine Liste sein."
    in_progress = sum(1 for t in todos if t.get("status") == "in_progress")
    if in_progress > 1:
        return "FEHLER: Nur eine Aufgabe kann gleichzeitig 'in_progress' sein."
    for t in todos:
        if not isinstance(t, dict) or not t.get("description", "").strip():
            return "FEHLER: Jedes Todo braucht eine 'description'."
        if t.get("status") not in VALID_STATUSES:
            return f"FEHLER: Ungültiger Status '{t.get('status')}'. Erlaubt: {', '.join(VALID_STATUSES)}"
    _todos = todos
    if not todos:
        return "Todo-Liste geleert."
    lines = [f"{i+1}. [{t['status']}] {t['description']}" for i, t in enumerate(todos)]
    return "Todo-Liste aktualisiert:\n" + "\n".join(lines)


def get_todos() -> str:
    """Zeigt die aktuelle Todo-Liste."""
    if not _todos:
        return "Todo-Liste ist leer."
    lines = [f"{i+1}. [{t['status']}] {t['description']}" for i, t in enumerate(_todos)]
    return "\n".join(lines)


def list_background_processes() -> str:
    """Listet alle Hintergrundprozesse der aktuellen Session.
    Portiert von Gemini CLI ListBackgroundProcessesTool."""
    try:
        import __main__
        client = getattr(__main__, 'client', None)
        if client and hasattr(client, 'process_mgr'):
            tasks = client.process_mgr.list_tasks()
            if not tasks:
                return "Keine Hintergrundprozesse aktiv."
            lines = [f"- [PID {t.get('id','?')}] {t.get('status','?').upper()}: `{t.get('command','?')}`" for t in tasks]
            return "\n".join(lines)
    except Exception:
        pass
    return "Keine Hintergrundprozesse gefunden."


def read_background_output(pid: int, lines: int = 100) -> str:
    """Liest den Output-Log eines Hintergrundprozesses.
    Portiert von Gemini CLI ReadBackgroundOutputTool."""
    try:
        import __main__
        client = getattr(__main__, 'client', None)
        if client and hasattr(client, 'process_mgr'):
            output = ""
            for chunk in client.process_mgr.watch_task_output(pid):
                output += chunk
                if len(output) > 64 * 1024:
                    break
            if not output:
                return f"Kein Output für Prozess {pid}."
            tail = output.strip().split("\n")
            return "\n".join(tail[-lines:])
    except Exception as e:
        return f"FEHLER beim Lesen von Prozess {pid}: {e}"
    return f"Prozess {pid} nicht gefunden."


def ask_user(question: str) -> str:
    """Fragt Nutzer nach Information (Interaktiv)."""
    return f"FRAGE: {question}"

def delegate_to_subagent(agent_name: str, prompt: str) -> str:
    """Delegiert an einen Spezial-Agenten (Investigator, Generalist, Architect)."""
    try:
        from sonu_client import SonuClient
        import terminal_ui
        
        class HeadlessUI(terminal_ui.TerminalUI):
            def __init__(self): super().__init__(); self.yolo=True; self.log=[]
            def display_response(self, text): self.log.append(text)
            def show_tool_call(self, n, a): self.log.append(f"Tool: {n}")
            def confirm_action(self, n, a): return True

        client = SonuClient()
        ui = HeadlessUI()
        ui.log.append(f"=== SUB-AGENT: {agent_name} ===")
        ans = client.run_agent_turn(prompt, ui, max_steps=15)
        return f"--- SUB-AGENT LOG ---\n" + "\n".join(ui.log) + f"\n\n--- FINALES ERGEBNIS ---\n{ans}"
    except Exception as e: return f"FEHLER: {e}"

def run_python(code: str) -> str:
    """Führt Python-Code aus und gibt stdout/stderr zurück. Ideal für Berechnungen, Datenanalyse und schnelle Tests."""
    import sys
    import io
    import traceback
    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()
    try:
        exec(compile(code, "<sonu>", "exec"), {})
        out = sys.stdout.getvalue()
        err = sys.stderr.getvalue()
        result = out
        if err:
            result += f"\n[stderr]\n{err}"
        return _truncate(result.strip()) if result.strip() else "(kein Output)"
    except Exception:
        err = sys.stderr.getvalue()
        tb = traceback.format_exc()
        return f"FEHLER:\n{err}\n{tb}"
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr


def edit_many(edits_json: str) -> str:
    """Wendet mehrere chirurgische Edits auf verschiedene Dateien in einer Aktion an.
    edits_json: JSON-Array von {path, old_string, new_string} Objekten.
    Alle Edits werden zuerst validiert, dann erst angewendet (atomic).
    """
    import json as _json
    try:
        edits = _json.loads(edits_json)
    except Exception as e:
        return f"FEHLER: Ungültiges JSON: {e}"

    if not isinstance(edits, list) or not edits:
        return "FEHLER: edits_json muss ein nicht-leeres Array sein."

    # Validierungsphase
    validated = []
    for i, edit in enumerate(edits):
        path = edit.get("path", "")
        old_str = edit.get("old_string", "")
        new_str = edit.get("new_string", "")
        if not path:
            return f"FEHLER: Edit #{i+1} hat keinen 'path'."
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            return f"FEHLER: Datei '{path}' nicht lesbar: {e}"
        count = content.count(old_str)
        if count == 0:
            return f"FEHLER: Edit #{i+1} '{path}': 'old_string' nicht gefunden."
        if count > 1:
            return f"FEHLER: Edit #{i+1} '{path}': {count} Treffer. Sei präziser."
        validated.append((path, content, old_str, new_str))

    # Diff-Preview
    import difflib
    diff_lines = []
    for path, content, old_str, new_str in validated:
        new_content = content.replace(old_str, new_str)
        old_lines = content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = list(difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{path}", tofile=f"b/{path}", lineterm=""))
        diff_lines.extend(diff[:30])

    if diff_lines:
        colored = []
        for line in diff_lines:
            if line.startswith("+") and not line.startswith("+++"):
                colored.append(f"\033[32m{line}\033[0m")
            elif line.startswith("-") and not line.startswith("---"):
                colored.append(f"\033[31m{line}\033[0m")
            elif line.startswith("@@"):
                colored.append(f"\033[36m{line}\033[0m")
            else:
                colored.append(line)
        print(f"\n\033[1mBatch-Edit: {len(validated)} Dateien\033[0m")
        print("\n".join(colored))
        import __main__
        ui = getattr(__main__, "ui", None)
        if not (ui and getattr(ui, "yolo", False)):
            try:
                ans = input(f"\n  Apply all {len(validated)} edits? [y/N]: ").strip().lower()
                if ans not in ("y", "yes", "j", "ja"):
                    return "ABGEBROCHEN: Nutzer hat Batch-Edit abgelehnt."
            except (EOFError, KeyboardInterrupt):
                return "ABGEBROCHEN."

    # Anwenden
    results = []
    for path, content, old_str, new_str in validated:
        new_content = content.replace(old_str, new_str)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
            results.append(f"OK: {path}")
        except Exception as e:
            results.append(f"FEHLER {path}: {e}")
    return "\n".join(results)


def patch_file(path: str, patch: str) -> str:
    """Wendet einen unified-diff Patch auf eine Datei an. Patch-Format: --- a/file +++ b/file @@ ... @@"""
    try:
        import difflib
        with open(path, "r", encoding="utf-8") as f:
            original = f.readlines()

        # Parse unified diff
        result_lines = list(original)
        patch_lines = patch.splitlines(keepends=True)
        hunks = []
        i = 0
        while i < len(patch_lines):
            line = patch_lines[i]
            if line.startswith("@@"):
                # parse @@ -start,count +start,count @@
                import re
                m = re.search(r"-(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))?", line)
                if m:
                    old_start = int(m.group(1)) - 1
                    old_count = int(m.group(2)) if m.group(2) else 1
                    hunks.append({"old_start": old_start, "old_count": old_count, "lines": []})
            elif hunks and (line.startswith("+") or line.startswith("-") or line.startswith(" ")):
                hunks[-1]["lines"].append(line)
            i += 1

        if not hunks:
            return "FEHLER: Kein gültiger unified-diff Hunk gefunden."

        # Apply hunks in reverse order to preserve line numbers
        for hunk in reversed(hunks):
            old_start = hunk["old_start"]
            removes = [l[1:] for l in hunk["lines"] if l.startswith("-")]
            adds = [l[1:] for l in hunk["lines"] if l.startswith("+")]
            old_count = len(removes)
            result_lines[old_start:old_start + old_count] = adds

        with open(path, "w", encoding="utf-8") as f:
            f.writelines(result_lines)
        return f"OK: Patch auf {path} angewendet ({len(hunks)} Hunk(s))."
    except Exception as e:
        return f"FEHLER beim Patchen: {e}"


# --- ERWEITERTER DATEI-SUPPORT ---

def read_pdf(path: str, pages: str = None) -> str:
    """Liest Text aus einer PDF-Datei. pages z.B. '1-5' oder '3'."""
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            total = len(pdf.pages)
            if pages:
                parts = pages.split("-")
                start = int(parts[0]) - 1
                end = int(parts[1]) if len(parts) > 1 else int(parts[0])
                page_range = pdf.pages[start:end]
            else:
                page_range = pdf.pages[:20]  # max 20 pages default
            text_parts = []
            for i, page in enumerate(page_range):
                t = page.extract_text() or ""
                text_parts.append(f"--- Seite {i+1} ---\n{t}")
            result = "\n\n".join(text_parts)
            if not pages and total > 20:
                result += f"\n\n[{total - 20} weitere Seiten. Nutze pages='1-{total}' für den Rest.]"
            return _truncate(result) if result.strip() else "(Kein Text extrahierbar)"
    except ImportError:
        return "FEHLER: pdfplumber nicht installiert. Führe aus: pip install pdfplumber"
    except Exception as e:
        return f"FEHLER beim Lesen der PDF: {e}"


def read_image(path: str, question: str = "Was ist auf diesem Bild zu sehen?") -> str:
    """Analysiert ein Bild via Gemini Vision. Kann Screenshots, Diagramme, UI-Mockups beschreiben."""
    try:
        with open(path, "rb") as f:
            img_bytes = f.read()
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                    "gif": "image/gif", "webp": "image/webp"}
        mime = mime_map.get(ext, "image/png")

        from google import genai as _genai
        from google.genai import types as _types
        import __main__
        client_obj = getattr(__main__, "client", None)
        api_key = None
        if client_obj:
            api_key = client_obj.keys[client_obj.active_index] if client_obj.keys else client_obj.api_key
        if not api_key:
            from dotenv import dotenv_values
            env = dotenv_values(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
            api_key = env.get("GEMINI_API_KEY") or (env.get("GEMINI_KEY_POOL", "").split(",")[0].strip())
        if not api_key:
            return "FEHLER: Kein Gemini API-Key gefunden."

        vision_client = _genai.Client(api_key=api_key)
        response = vision_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[question, _types.Part.from_bytes(data=img_bytes, mime_type=mime)]
        )
        return _truncate(response.text or "(Keine Antwort)")
    except Exception as e:
        return f"FEHLER bei Bildanalyse: {e}"


def notebook_read(path: str) -> str:
    """Liest ein Jupyter Notebook (.ipynb) und gibt alle Zellen mit Outputs zurück."""
    try:
        import json as _json
        with open(path, "r", encoding="utf-8") as f:
            nb = _json.load(f)
        cells = nb.get("cells", [])
        parts = []
        for i, cell in enumerate(cells):
            cell_type = cell.get("cell_type", "unknown")
            source = "".join(cell.get("source", []))
            header = f"## Cell {i+1} [{cell_type}]"
            parts.append(f"{header}\n{source}")
            if cell_type == "code":
                outputs = cell.get("outputs", [])
                out_texts = []
                for o in outputs:
                    if "text" in o:
                        out_texts.append("".join(o["text"]))
                    elif "data" in o and "text/plain" in o["data"]:
                        out_texts.append("".join(o["data"]["text/plain"]))
                if out_texts:
                    parts.append("Output:\n" + "\n".join(out_texts))
        return _truncate("\n\n".join(parts)) if parts else "(Notebook leer)"
    except Exception as e:
        return f"FEHLER beim Lesen des Notebooks: {e}"


# --- REGISTRY & SCHEMAS ---

def _schema(props, required): return types.Schema(type=types.Type.OBJECT, properties=props, required=required)
def _str(d): return types.Schema(type=types.Type.STRING, description=d)
def _int(d): return types.Schema(type=types.Type.INTEGER, description=d)

_REG = {
    "read_file": {"f": read_file, "s": True, "d": "Liest Datei. Nutze start_line/end_line.", "p": {"path": "Pfad", "start_line": "Start (int)", "end_line": "Ende (int)"}, "r": ["path"]},
    "list_dir": {"f": list_dir, "s": True, "d": "Listet Verzeichnis auf.", "p": {"path": "Pfad"}, "r": []},
    "glob_files": {"f": glob_files, "s": True, "d": "Findet Dateien via Glob-Muster.", "p": {"pattern": "Muster", "path": "Startpfad"}, "r": ["pattern"]},
    "grep_search": {"f": grep_search, "s": True, "d": "Regex-Suche mit Kontextzeilen.", "p": {"pattern": "Regex", "path": "Pfad", "context": "Anzahl Zeilen (int)"}, "r": ["pattern"]},
    "replace": {"f": replace, "s": False, "d": "Surgical edit: ersetzt EINE Textstelle.", "p": {"path": "Pfad", "old_string": "Alt", "new_string": "Neu"}, "r": ["path", "old_string", "new_string"]},
    "write_file": {"f": write_file, "s": False, "d": "Schreibt Datei komplett neu.", "p": {"path": "Pfad", "content": "Inhalt"}, "r": ["path", "content"]},
    "run_shell": {"f": run_shell, "s": False, "d": "Fuehrt PowerShell-Befehl aus. Fuer lange Befehle mit Live-Output: stream=true setzen.", "p": {"command": "Befehl", "stream": "true fuer Live-Streaming des Outputs"}, "r": ["command"]},
    "web_fetch": {"f": web_fetch, "s": True, "d": "Extrahiert Text von einer URL.", "p": {"url": "URL"}, "r": ["url"]},
    "google_search": {"f": google_search, "s": True, "d": "Sucht im Internet.", "p": {"query": "Suchbegriff"}, "r": ["query"]},
    "update_topic": {"f": update_topic, "s": True, "d": "Aktualisiert Kapitel im UI.", "p": {"title": "Titel", "summary": "Inhalt", "strategic_intent": "Ziel"}, "r": ["title", "summary"]},
    "ask_user": {"f": ask_user, "s": False, "d": "Fragt Nutzer nach Feedback.", "p": {"question": "Frage"}, "r": ["question"]},
    "delegate_to_subagent": {"f": delegate_to_subagent, "s": False, "d": "Delegiert an Sub-Agenten.", "p": {"agent_name": "investigator|generalist|architect", "prompt": "Aufgabe"}, "r": ["agent_name", "prompt"]},
    "run_python": {"f": run_python, "s": True, "d": "Führt Python-Code aus. Für Berechnungen, Datenanalyse, schnelle Tests. Kein Filesystem-Zugriff nötig.", "p": {"code": "Python-Code als String"}, "r": ["code"]},
    "patch_file": {"f": patch_file, "s": False, "d": "Wendet unified-diff Patch auf Datei an. Besser als replace bei mehreren Änderungen.", "p": {"path": "Dateipfad", "patch": "unified-diff Patch"}, "r": ["path", "patch"]},
    "edit_many": {"f": edit_many, "s": False, "d": "Batch-Edit: Mehrere chirurgische Edits auf verschiedene Dateien in EINER Aktion. edits_json: JSON-Array von {path, old_string, new_string}. Atomar: zuerst alle validieren, dann alle anwenden.", "p": {"edits_json": "JSON-Array von {path, old_string, new_string} Objekten"}, "r": ["edits_json"]},
    "read_pdf": {"f": read_pdf, "s": True, "d": "Liest Text aus einer PDF-Datei. pages z.B. '1-5' oder '3'. Max 20 Seiten ohne pages.", "p": {"path": "Pfad zur PDF-Datei", "pages": "Seitenbereich z.B. '1-5'"}, "r": ["path"]},
    "read_image": {"f": read_image, "s": True, "d": "Analysiert Bild via Gemini Vision: Screenshots, Diagramme, UI-Mockups, Code-Fotos.", "p": {"path": "Pfad zur Bilddatei (jpg/png/gif/webp)", "question": "Was soll analysiert werden?"}, "r": ["path"]},
    "notebook_read": {"f": notebook_read, "s": True, "d": "Liest Jupyter Notebook (.ipynb): alle Zellen und Outputs.", "p": {"path": "Pfad zum .ipynb Notebook"}, "r": ["path"]},
    "read_many_files": {"f": read_many_files, "s": True, "d": "Liest mehrere Dateien via Glob-Pattern gleichzeitig und gibt alle Inhalte konkateniert zurück. Ideal für schnelle Codebase-Übersicht.", "p": {"include": "Liste von Glob-Patterns z.B. ['src/**/*.py', 'README.md']", "exclude": "Optionale Ausschluss-Patterns", "recursive": "Rekursiv suchen (bool, default true)"}, "r": ["include"]},
    "write_todos": {"f": write_todos, "s": True, "d": "Setzt die komplette Todo-Liste für die aktuelle Aufgabe. status: pending|in_progress|completed|cancelled|blocked. Max 1 in_progress.", "p": {"todos": "Liste von {description: str, status: str} Objekten"}, "r": ["todos"]},
    "get_todos": {"f": get_todos, "s": True, "d": "Zeigt die aktuelle Todo-Liste.", "p": {}, "r": []},
    "list_background_processes": {"f": list_background_processes, "s": True, "d": "Listet alle aktiven Hintergrundprozesse der Session.", "p": {}, "r": []},
    "read_background_output": {"f": read_background_output, "s": True, "d": "Liest den Output-Log eines Hintergrundprozesses.", "p": {"pid": "Prozess-ID (int)", "lines": "Anzahl letzter Zeilen (int, default 100)"}, "r": ["pid"]},
}

def get_tool_object():
    decls = []
    for name, i in _REG.items():
        props = {k: _int(v) if "(int)" in v else _str(v) for k, v in i["p"].items()}
        decls.append(types.FunctionDeclaration(name=name, description=i["d"], parameters=_schema(props, i["r"])))
    return types.Tool(function_declarations=decls)

def is_safe(name): return _REG.get(name, {}).get("s", False)

def dispatch(name, args):
    if name not in _REG: return f"Unbekannt: {name}"
    try:
        # Konvertiere string booleans ("true"/"false") zu echten booleans
        clean = {}
        for k, v in (args or {}).items():
            if isinstance(v, str) and v.lower() in ("true", "false"):
                clean[k] = v.lower() == "true"
            else:
                clean[k] = v
        return _REG[name]["f"](**clean)
    except Exception as e: return f"FEHLER: {e}"

def get_openai_tools():
    out = []
    for name, i in _REG.items():
        props = {k: {"type": "integer" if "(int)" in v else "string", "description": v} for k, v in i["p"].items()}
        out.append({"type": "function", "function": {
            "name": name, "description": i["d"],
            "parameters": {"type": "object", "properties": props, "required": i["r"]}
        }})
    return out
