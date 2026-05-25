import os

class MemoryManager:
    def __init__(self, project_root=None):
        if project_root is None:
            project_root = os.path.dirname(os.path.abspath(__file__))
        self.project_root = project_root
        
        # Pfade fuer die 4 Gedaechtnisebenen
        self.global_path = os.path.expanduser("~/.sonu/global_profile.md")
        self.private_path = os.path.join(self.project_root, ".sonu", "private_machine.md")
        self.project_path = os.path.join(self.project_root, "SONU.md")
        
        self._ensure_directories_and_defaults()

    def _ensure_directories_and_defaults(self):
        # Globales Profil (~/.sonu/global_profile.md) sicherstellen
        os.makedirs(os.path.dirname(self.global_path), exist_ok=True)
        if not os.path.exists(self.global_path):
            with open(self.global_path, "w", encoding="utf-8") as f:
                f.write(
                    "# Global User Profile: Shubham Jayswal\n\n"
                    "- **Rolle:** Mechatronics student, NRW Germany. GitHub: Dtunder.\n"
                    "- **Stil:** Automation-first. Cybernetic thinker. Never manual workarounds - always scripts.\n"
                    "- **Projekte:** CRYPTO_HFT, QuantumCFO, Bewerbung_Tools, Oekolopoly, DeepMindMap.\n"
                )
                
        # Lokales Maschinenprofil (.sonu/private_machine.md) sicherstellen
        os.makedirs(os.path.dirname(self.private_path), exist_ok=True)
        if not os.path.exists(self.private_path):
            with open(self.private_path, "w", encoding="utf-8") as f:
                f.write(
                    "# Local Machine Setup\n\n"
                    "- **OS:** Windows (PowerShell standard shell).\n"
                    "- **Workspace:** C:\\Users\\user\\sonu-cli-advanced\n"
                    "- **API Key Pool:** 5 Keys configured inside .env.\n"
                )

        # Projektweites SONU.md sicherstellen
        if not os.path.exists(self.project_path):
            with open(self.project_path, "w", encoding="utf-8") as f:
                f.write(
                    "# Sonu CLI Project-Wide Memory\n\n"
                    "## 1. Architektur-Regeln\n"
                    "- Sonu CLI Advanced ist ein modularer, asynchroner CLI-Agent.\n"
                    "- Alle blockierenden Befehle werden ueber den `ProcessManager` in den Hintergrund ausgelagert.\n"
                    "- API-Keys werden transparent bei 429-Fehlern rotiert.\n"
                    "- Dynamisches Skill-System ermoeglicht on-the-fly Expertenprofile.\n"
                )

    def load_memory(self, current_working_dir=None):
        """Laedt und konsolidiert alle 4 Ebenen des Gedaechtnis-Kontextes."""
        context = []
        
        # Level 1: Global Memory
        if os.path.exists(self.global_path):
            try:
                with open(self.global_path, "r", encoding="utf-8") as f:
                    context.append(f"=== LEVEL 1: GLOBAL MEMORY ===\n{f.read()}\n")
            except Exception:
                pass
                
        # Level 2: Private Machine Setup
        if os.path.exists(self.private_path):
            try:
                with open(self.private_path, "r", encoding="utf-8") as f:
                    context.append(f"=== LEVEL 2: PRIVATE MACHINE MEMORY ===\n{f.read()}\n")
            except Exception:
                pass
                
        # Level 3: Project Context (SONU.md)
        if os.path.exists(self.project_path):
            try:
                with open(self.project_path, "r", encoding="utf-8") as f:
                    context.append(f"=== LEVEL 3: PROJECT MEMORY ===\n{f.read()}\n")
            except Exception:
                pass
                
        # Level 4: Modulspezifische Regeln (untergeordnetes SONU.md)
        if current_working_dir:
            module_file = os.path.join(current_working_dir, "SONU.md")
            if os.path.exists(module_file) and os.path.abspath(module_file) != os.path.abspath(self.project_path):
                try:
                    with open(module_file, "r", encoding="utf-8") as f:
                        context.append(f"=== LEVEL 4: MODULE MEMORY ({os.path.basename(current_working_dir)}) ===\n{f.read()}\n")
                except Exception:
                    pass
                    
        return "\n".join(context)
