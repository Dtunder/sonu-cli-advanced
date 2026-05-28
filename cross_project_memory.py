"""Cross-project typed memory — stored at ~/.sonu/memory/.

Memory types (matching Claude Code's model):
  user      — who the user is, their expertise, preferences
  feedback  — corrections and confirmed approaches
  project   — ongoing work, goals, deadlines
  reference — pointers to external systems

Each memory is a .md file with YAML-like frontmatter:
  ---
  name: short-kebab-slug
  description: one-line hook
  type: user|feedback|project|reference
  ---
  Body content here.

MEMORY.md is a flat index file (one line per entry).
"""

import os
import re
from pathlib import Path
from datetime import datetime


MEMORY_DIR = Path.home() / ".sonu" / "memory"
MEMORY_INDEX = MEMORY_DIR / "MEMORY.md"
VALID_TYPES = {"user", "feedback", "project", "reference"}


def _ensure_dir():
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Returns (meta_dict, body_text)."""
    meta = {}
    body = text
    m = re.match(r"^---\n(.*?)\n---\n?(.*)", text, re.DOTALL)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip()
        body = m.group(2).strip()
    return meta, body


def save_memory(name: str, description: str, memory_type: str, body: str) -> str:
    """Save or overwrite a memory file and update the index."""
    if memory_type not in VALID_TYPES:
        return f"FEHLER: Ungültiger Typ '{memory_type}'. Erlaubt: {VALID_TYPES}"
    _ensure_dir()
    slug = re.sub(r"[^a-z0-9\-]", "", name.lower().replace(" ", "-"))
    if not slug:
        return "FEHLER: Ungültiger Name."
    filename = f"{memory_type}_{slug}.md"
    path = MEMORY_DIR / filename
    content = f"---\nname: {slug}\ndescription: {description}\ntype: {memory_type}\nupdated: {datetime.now().strftime('%Y-%m-%d')}\n---\n\n{body.strip()}\n"
    path.write_text(content, encoding="utf-8")
    _update_index(filename, description)
    return f"OK: Memory gespeichert → {path}"


def _update_index(filename: str, description: str):
    _ensure_dir()
    title = filename.replace(".md", "").replace("_", " ").title()
    new_line = f"- [{title}]({filename}) — {description}"
    existing = []
    if MEMORY_INDEX.exists():
        existing = MEMORY_INDEX.read_text(encoding="utf-8").splitlines()
    # Remove old entry for same file
    existing = [l for l in existing if f"({filename})" not in l]
    if not existing or existing[0] != "# Memory Index":
        existing = ["# Memory Index"] + [l for l in existing if l != "# Memory Index"]
    existing.append(new_line)
    MEMORY_INDEX.write_text("\n".join(existing) + "\n", encoding="utf-8")


def load_all_memories(memory_type: str = None) -> str:
    """Load all memories (optionally filtered by type) as a formatted string."""
    _ensure_dir()
    if not MEMORY_DIR.exists():
        return ""
    parts = []
    for path in sorted(MEMORY_DIR.glob("*.md")):
        if path.name == "MEMORY.md":
            continue
        try:
            text = path.read_text(encoding="utf-8")
            meta, body = _parse_frontmatter(text)
            if memory_type and meta.get("type") != memory_type:
                continue
            mtype = meta.get("type", "?")
            mname = meta.get("name", path.stem)
            parts.append(f"[{mtype}:{mname}] {body[:500]}")
        except Exception:
            continue
    return "\n\n".join(parts)


def load_index() -> str:
    """Return the MEMORY.md index content."""
    if MEMORY_INDEX.exists():
        return MEMORY_INDEX.read_text(encoding="utf-8")
    return "# Memory Index\n(leer)\n"


def delete_memory(name: str) -> str:
    """Delete a memory by slug name."""
    _ensure_dir()
    slug = re.sub(r"[^a-z0-9\-]", "", name.lower().replace(" ", "-"))
    deleted = []
    for path in MEMORY_DIR.glob(f"*_{slug}.md"):
        path.unlink()
        deleted.append(path.name)
    if deleted:
        # Rebuild index
        existing = MEMORY_INDEX.read_text(encoding="utf-8").splitlines() if MEMORY_INDEX.exists() else []
        for fname in deleted:
            existing = [l for l in existing if f"({fname})" not in l]
        MEMORY_INDEX.write_text("\n".join(existing) + "\n", encoding="utf-8")
        return f"OK: Gelöscht: {', '.join(deleted)}"
    return f"FEHLER: Kein Memory mit Name '{name}' gefunden."


def search_memories(query: str) -> str:
    """Simple keyword search across all memory bodies."""
    _ensure_dir()
    query_lower = query.lower()
    results = []
    for path in sorted(MEMORY_DIR.glob("*.md")):
        if path.name == "MEMORY.md":
            continue
        try:
            text = path.read_text(encoding="utf-8")
            if query_lower in text.lower():
                meta, body = _parse_frontmatter(text)
                results.append(f"[{meta.get('type','?')}:{meta.get('name', path.stem)}] {body[:300]}")
        except Exception:
            continue
    return "\n\n".join(results) if results else "Keine Treffer."
