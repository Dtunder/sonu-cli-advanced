import os
import sys

# UTF-8 erzwingen, damit Emojis/Unicode auch bei Umleitung (>) nicht crashen.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import json
import time
from typing import List, Dict

# Stelle sicher, dass das Verzeichnis importierbar ist
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sonu_client import SonuClient
from terminal_ui import TerminalUI

class BatchResearcher:
    def __init__(self, problems_file: str = "problems.json", output_dir: str = "recherche_ergebnisse"):
        self.problems_file = problems_file
        self.output_dir = output_dir
        self.ui = TerminalUI()
        self.ui.set_yolo(True)  # Läuft vollkommen autonom im Hintergrund
        
        # Stelle sicher, dass das Ausgabe-Verzeichnis existiert
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Lade SonuClient mit Key-Rotation
        try:
            self.client = SonuClient()
        except Exception as e:
            self.ui.show_error(f"Fehler bei der Sonu-Initialisierung: {e}")
            sys.exit(1)

    def load_problems(self) -> List[Dict[str, str]]:
        """Lädt die Aufgabenliste aus einer JSON-Datei. Erstellt eine Standardliste, falls nicht vorhanden."""
        if not os.path.exists(self.problems_file):
            default_problems = [
                {"id": "1", "topic": "PID Tuning", "query": "Erkläre die mechatronischen Einstellregeln für einen PID-Regler nach Ziegler-Nichols (Sprungantwort-Methode)."},
                {"id": "2", "topic": "Memory Leak in Python", "query": "Wie findet man Speicherlecks in Python-Anwendungen, die mit Threading arbeiten? Nenne Tools und Codebeispiele."},
                {"id": "3", "topic": "HFT Orderbook Parsing", "query": "Was sind die performantesten Strategien zum Parsen eines L3-Orderbooks im Hochfrequenzhandel (C++ vs. Rust)?"}
            ]
            with open(self.problems_file, "w", encoding="utf-8") as f:
                json.dump(default_problems, f, indent=4, ensure_ascii=False)
            return default_problems
            
        try:
            with open(self.problems_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            self.ui.show_error(f"Fehler beim Laden von {self.problems_file}: {e}")
            return []

    def run(self):
        problems = self.load_problems()
        if not problems:
            self.ui.show_error("Keine Probleme zur Recherche gefunden.")
            return

        self.ui.show_info(f"🚀 [bold cyan]Batch-Researcher initialisiert.[/bold cyan] Starte Analyse von {len(problems)} Problemen...")
        
        gesamt_bericht_path = os.path.join(self.output_dir, "GESAMT_BERICHT.md")
        with open(gesamt_bericht_path, "w", encoding="utf-8") as f:
            f.write(f"# Globaler Recherche-Gesamtbericht\n")
            f.write(f"Generiert am: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"| ID | Thema | Status | Ergebnis-Link |\n")
            f.write(f"| :--- | :--- | :--- | :--- |\n")

        for idx, item in enumerate(problems, 1):
            p_id = item.get("id", str(idx))
            topic = item.get("topic", f"Problem {p_id}")
            query = item.get("query", "")
            
            self.ui.show_info(f"\n[bold yellow][{idx}/{len(problems)}] Starte Recherche für: '{topic}'[/bold yellow]")
            
            start_time = time.time()
            response = None
            status = "Erfolgreich"
            
            try:
                # Nutzt Sonu's Key-Rotation und Multi-Provider-Fallbacks
                response = self.client.run_agent_turn(
                    f"Führe eine tiefgehende wissenschaftliche Recherche zu folgendem Thema durch. "
                    f"Erstelle einen C1/C2-Bericht mit Formeln, mechatronischer Logik und Quellcode-Beispielen:\n\n{query}",
                    self.ui
                )
            except Exception as e:
                status = "Fehlgeschlagen"
                response = f"Fehler bei der Recherche: {e}"
                self.ui.show_error(f"Recherche fehlgeschlagen für {topic}: {e}")

            elapsed = time.time() - start_time
            
            # Speicher Einzelergebnis
            filename = f"problem_{p_id}_{topic.lower().replace(' ', '_')}.md"
            # Bereinige Filename von ungültigen Zeichen
            filename = "".join(c for c in filename if c.isalnum() or c in ("_", ".", "-"))
            file_path = os.path.join(self.output_dir, filename)
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"# Recherchebericht: {topic}\n")
                f.write(f"**ID:** {p_id} | **Status:** {status} | **Dauer:** {elapsed:.2f}s\n\n")
                f.write(f"## Anfrage\n>{query}\n\n")
                f.write(f"## Ergebnis\n\n{response}\n")

            # Eintrag in den Gesamtbericht
            with open(gesamt_bericht_path, "a", encoding="utf-8") as f:
                f.write(f"| {p_id} | {topic} | {status} | [{filename}](file:///{file_path.replace(os.sep, '/')}) |\n")

            self.ui.show_info(f"[bold green]✓ Fertig in {elapsed:.2f}s! Bericht gespeichert unter: {filename}[/bold green]")
            time.sleep(2)  # Kurze Pause zur Dämpfung der API-Last

        self.ui.show_info(f"\n[bold green]🎉 Batch-Recherche abgeschlossen! Gesamtbericht erstellt unter: GESAMT_BERICHT.md[/bold green]")

if __name__ == "__main__":
    problems_json = "problems.json"
    if len(sys.argv) > 1:
        problems_json = sys.argv[1]
        
    researcher = BatchResearcher(problems_file=problems_json)
    researcher.run()
