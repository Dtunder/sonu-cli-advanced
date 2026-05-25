import os

class SkillsManager:
    def __init__(self, skills_dir=None):
        if skills_dir is None:
            skills_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills")
        self.skills_dir = skills_dir
        self.active_skill = None
        self._ensure_skills_dir()

    def _ensure_skills_dir(self):
        os.makedirs(self.skills_dir, exist_ok=True)
        # Standard-Profile erstellen, falls sie nicht vorhanden sind
        self._create_default_skill(
            "cybernetic-thinking",
            "Du denkst und analysierst Probleme strikt systemtheoretisch im mechatronischen Denkrahmen:\n"
            "1. Systemzustand messen (aktuelles Fehlverhalten).\n"
            "2. Soll-Zustand definieren (gewuenschtes Zielverhalten).\n"
            "3. Abweichung (Gap) ermitteln (warum ist es noch nicht dort).\n"
            "4. Minimale, hochpraezise Aktionen ableiten (keine Raten, absolute Robustheit).\n"
            "5. Downstream-Effekte einkalkulieren (was bricht an anderen Schnittstellen).\n"
            "6. Validierungsmethode etablieren (wie beweisen wir den Erfolg).\n"
            "Antworte praezise, logisch, und strukturiert auf C1/C2 Deutsch."
        )
        self._create_default_skill(
            "system-architect",
            "Du bist leitender Systemarchitekt.\n"
            "Du entwirfst modularer Strukturen, definierst klare API-Schnittstellen und Vertraege "
            "zwischen Komponenten. Du legst extremen Wert auf Observability, Logging, Fehlerkapselung "
            "und minimierten Overhead."
        )

    def _create_default_skill(self, name, instruction):
        path = os.path.join(self.skills_dir, f"{name}.md")
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# Skill: {name}\n\n{instruction}\n")

    def list_skills(self):
        skills = []
        if os.path.exists(self.skills_dir):
            for name in os.listdir(self.skills_dir):
                if name.endswith(".md"):
                    skills.append(name[:-3])
        return skills

    def activate_skill(self, name):
        skills = self.list_skills()
        if name not in skills:
            raise ValueError(f"Skill '{name}' existiert nicht.")
        path = os.path.join(self.skills_dir, f"{name}.md")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.active_skill = name
        return content

    def deactivate_skill(self):
        self.active_skill = None
