import os
import datetime


class MemoryManager:
    def __init__(self, project_root=None):
        if project_root is None:
            project_root = os.path.dirname(os.path.abspath(__file__))
        self.project_root = project_root

        self.global_path = os.path.expanduser("~/.sonu/global_profile.md")
        self.private_path = os.path.join(self.project_root, ".sonu", "private_machine.md")
        self.project_path = os.path.join(self.project_root, "SONU.md")

        self._ensure_defaults()

    def _ensure_defaults(self):
        os.makedirs(os.path.dirname(self.global_path), exist_ok=True)
        if not os.path.exists(self.global_path):
            with open(self.global_path, "w", encoding="utf-8") as f:
                f.write(
                    "# Global User Profile: Shubham Jayswal\n\n"
                    "- **Rolle:** Mechatronics student, NRW Germany. GitHub: Dtunder.\n"
                    "- **Stil:** Automation-first. Cybernetic thinker. Direkt, kein Smalltalk.\n"
                    "- **Projekte:** CRYPTO_HFT, QuantumCFO, Bewerbung_Tools, Oekolopoly, DeepMindMap, Sonu CLI.\n"
                    "- **Sprache:** Deutsch bevorzugt. C1/C2.\n"
                    "- **Shell:** PowerShell (Windows 11).\n"
                )

        os.makedirs(os.path.dirname(self.private_path), exist_ok=True)
        if not os.path.exists(self.private_path):
            with open(self.private_path, "w", encoding="utf-8") as f:
                f.write(
                    "# Local Machine Setup\n\n"
                    "- **OS:** Windows 11 (PowerShell standard shell).\n"
                    "- **Workspace:** C:\\Users\\user\\sonu-cli-advanced\n"
                    "- **API Key Pool:** 15 Gemini Keys in .env.\n"
                )

        if not os.path.exists(self.project_path):
            with open(self.project_path, "w", encoding="utf-8") as f:
                f.write(
                    "# Sonu CLI — Project Memory\n\n"
                    "## Architektur\n"
                    "- Modularer autonomer Agent mit 4-Level-Gedächtnis, Swarm-Consensus, MoA.\n"
                    "- Provider: Gemini (primär, 15 Keys), Groq, OpenRouter, xAI, Ollama.\n"
                    "- Tools: read_file, grep_search, replace, write_file, run_shell, run_python, web_fetch, google_search.\n"
                )

    def load_memory(self, current_working_dir=None) -> str:
        """Lädt alle 4 Ebenen als konsolidierten Kontext-String."""
        context = []

        for level, label, path in [
            (1, "GLOBAL", self.global_path),
            (2, "MACHINE", self.private_path),
            (3, "PROJECT", self.project_path),
        ]:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read(4096)  # max 4KB pro Ebene
                    context.append(f"=== L{level}: {label} ===\n{content}\n")
                except Exception:
                    pass

        if current_working_dir:
            module_file = os.path.join(current_working_dir, "SONU.md")
            if (os.path.exists(module_file)
                    and os.path.abspath(module_file) != os.path.abspath(self.project_path)):
                try:
                    with open(module_file, "r", encoding="utf-8") as f:
                        content = f.read(2048)
                    module_name = os.path.basename(current_working_dir)
                    context.append(f"=== L4: MODULE ({module_name}) ===\n{content}\n")
                except Exception:
                    pass

        return "\n".join(context)

    def save_session_learnings(self, session_turns: list, topic: str = ""):
        """Schreibt nach einer Session einen kompakten Update ins globale Profil.
        Erfasst: was wurde gemacht, welche Projekte berührt, neue Erkenntnisse."""
        if not session_turns or len(session_turns) < 2:
            return

        try:
            # Extrahiere die ersten Nutzer-Nachrichten als Kontext
            user_msgs = [t.get("user", "") for t in session_turns if t.get("user")][:5]
            summary_hint = " | ".join(m[:80] for m in user_msgs)

            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            entry = (
                f"\n## Session {timestamp}\n"
                f"- Turns: {len(session_turns)}\n"
                f"- Topic: {topic or summary_hint or 'Interactive'}\n"
            )

            # Projekte die erwähnt wurden
            projects = []
            full_text = " ".join(user_msgs).lower()
            for p in ["sonu", "hft", "oekolopoly", "quantumcfo", "deepmindmap", "bewerbung"]:
                if p in full_text:
                    projects.append(p)
            if projects:
                entry += f"- Projekte: {', '.join(projects)}\n"

            with open(self.global_path, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass

    def update_global(self, key: str, value: str):
        """Fügt oder aktualisiert einen Key-Value Eintrag im globalen Profil."""
        try:
            with open(self.global_path, "r", encoding="utf-8") as f:
                content = f.read()

            marker = f"- **{key}:**"
            new_line = f"- **{key}:** {value}\n"
            if marker in content:
                import re
                content = re.sub(rf"- \*\*{re.escape(key)}\*\*:.*\n", new_line, content)
            else:
                content += f"\n{new_line}"

            with open(self.global_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception:
            pass
