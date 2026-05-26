import sqlite3
import os
import time
import logging
from typing import List, Dict, Tuple

class EvolutionModule:
    def __init__(self, db_path: str = "sonu.db", skills_dir: str = "skills"):
        self.db_path = db_path
        self.skills_dir = skills_dir
        self.threshold: int = 10  # Mindestanzahl Interaktionen für Synthese

    def check_for_evolution_triggers(self) -> None:
        if not os.path.exists(self.db_path):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Überprüfen, ob die Tabelle history existiert
            cursor.execute("SELECT count(name) FROM sqlite_master WHERE type='table' AND name='history'")
            if cursor.fetchone()[0] == 0:
                conn.close()
                return

            # Abfrage der genutzten Tools, Keywords und des Erfolgsstatus aus der Historie
            cursor.execute("""
                SELECT context_tags, COUNT(*)
                FROM history
                WHERE success = 1 AND context_tags IS NOT NULL AND context_tags != ''
                GROUP BY context_tags
                HAVING COUNT(*) >= ?
            """, (self.threshold,))

            candidates = cursor.fetchall()
            for tags, count in candidates:
                if not self._skill_exists(tags):
                    self._synthesize_new_skill(tags)
            conn.close()
        except Exception as e:
            logging.error(f"[EvolutionModule] Fehler beim Prüfen der Evolution-Trigger: {e}")

    def _skill_exists(self, tags: str) -> bool:
        skill_filename = f"{tags.lower().replace(' ', '_')}-expert.md"
        return os.path.exists(os.path.join(self.skills_dir, skill_filename))

    def _synthesize_new_skill(self, tags: str) -> None:
        skill_name = f"{tags.lower().replace(' ', '_')}-expert"
        skill_path = os.path.join(self.skills_dir, f"{skill_name}.md")

        # Generiere dynamisches Expertenprofil
        content = f"""# Expert Skill: {tags} (Autonom Generiert)
## Role Description
Dieser Skill wurde am {time.strftime('%Y-%m-%d')} autonom basierend auf 10+ erfolgreichen Systeminteraktionen im Bereich {tags} synthetisiert.

## Hauptaufgaben
- Priorisiere performante und typsichere Implementierungsstrukturen für {tags}.
- Beachte idiomatische Patterns (z.B. Error-Handling, Speicherverwaltung).

## Vorteile
- Nutze die bewährten Lösungsansätze aus der Sonu-Historie.
- Mathematische Konzepte werden mit Standard-LaTeX formatiert, z.B. $\\int f(x) dx$.

## Spezifische Anwendungsfälle
- Automatische Erkennung und Synthese von Mustern im Bereich {tags}.
"""
        os.makedirs(self.skills_dir, exist_ok=True)
        with open(skill_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logging.info(f"[Evolution] Neuer Skill synthetisiert: {skill_name}")
