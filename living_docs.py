import os
import re

class LivingDocs:
    def __init__(self, main_py_path="main.py", ui_py_path="terminal_ui.py"):
        self.main_py_path = main_py_path
        self.ui_py_path = ui_py_path

    def generate_help_md(self) -> str:
        # 1. Parse terminal_ui.py for existing descriptions
        help_mapping = {}
        if os.path.exists(self.ui_py_path):
            with open(self.ui_py_path, "r", encoding="utf-8") as f:
                ui_content = f.read()

            # Match table.add_row("/cmd", "description")
            # We handle simple commands and those with placeholders
            ui_matches = re.findall(r'table\.add_row\(["\']([^"\']+)["\'],\s*["\']([^"\']+)["\']\)', ui_content)
            for cmd_raw, desc in ui_matches:
                # Clean up command if it has placeholders like /activate <name>
                cmd_clean = cmd_raw.split()[0] if " " in cmd_raw else cmd_raw
                # Also handle "/tasks / /bg"
                if " / " in cmd_raw:
                    parts = cmd_raw.split(" / ")
                    for p in parts:
                        help_mapping[p.strip()] = desc
                else:
                    help_mapping[cmd_clean] = desc

        # 2. Parse main.py for actual implemented commands
        commands = []
        if os.path.exists(self.main_py_path):
            with open(self.main_py_path, "r", encoding="utf-8") as f:
                main_lines = f.readlines()

            # Flexible search for slash commands in elif blocks
            for i, line in enumerate(main_lines):
                if "elif cmd" in line and "/" in line:
                    # Find all slash commands in the line
                    cmd_matches = re.findall(r'["\'](/\w+[^"\']*)["\']', line)
                    for cmd_name in cmd_matches:
                        # Skip things that are clearly not commands (e.g. file paths if any)
                        if len(cmd_name) > 30: continue

                        # Try to find description in mapping
                        description = help_mapping.get(cmd_name)

                        # Fallback 1: check mapping for base command if cmd_name has args in UI (like /activate <name>)
                        if not description:
                            for k, v in help_mapping.items():
                                if k.startswith(cmd_name):
                                    description = v
                                    break

                        # Fallback 2: check comments in main.py
                        if not description:
                            if "#" in line:
                                description = line.split("#", 1)[1].strip()
                            elif i > 0:
                                prev_line = main_lines[i-1].strip()
                                if prev_line.startswith("#"):
                                    description = prev_line.lstrip("#").strip()

                        # Fallback 3: look at the block below
                        if not description:
                            for j in range(1, 4):
                                if i + j < len(main_lines):
                                    next_line = main_lines[i+j]
                                    str_match = re.search(r'["\']([^"\']{10,})["\']', next_line)
                                    if str_match:
                                        # Clean up rich tags
                                        clean_desc = re.sub(r'\[/?\w+[^\]]*\]', '', str_match.group(1)).strip()
                                        description = clean_desc
                                        break

                        if not description:
                            description = "Keine Beschreibung verfügbar."

                        if (cmd_name, description) not in commands:
                            commands.append((cmd_name, description))

        # 3. Generate Markdown
        md_content = "# Sonu CLI Commands\n\n"
        md_content += "Diese Datei wurde automatisch generiert.\n\n"
        md_content += "| Befehl | Beschreibung |\n"
        md_content += "| :--- | :--- |\n"

        # Add special case for /exit which is usually an 'if' or 'exit' command
        if "/exit" not in [c[0] for c in commands]:
            commands.insert(0, ("/exit", help_mapping.get("/exit", "Beendet das CLI sicher.")))

        for cmd, desc in commands:
            md_content += f"| `{cmd}` | {desc} |\n"

        # 4. Write to file
        with open("COMMANDS.md", "w", encoding="utf-8") as f:
            f.write(md_content)

        return md_content
