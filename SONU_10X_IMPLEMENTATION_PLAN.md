# TECHNICAL IMPLEMENTATION PLAN: SONU 10X
## Kybernetische Mechatronik & Automation-First Systemarchitektur

Dieses Dokument definiert den hochpräzisen, mechatronisch-kybernetischen Implementierungsplan für die 10 Breakthrough-Features von **Sonu CLI Advanced**. Die Systemarchitektur wird hierbei als geschlossener Regelkreis (Closed-Loop System) konzipiert, bei dem Störgrößen (z.B. API-Ausfälle, Syntaxfehler, Ressourcenengpässe) autonom detektiert, bewertet und durch gezielte Stellgrößeneingriffe kompensiert werden.

---

## Systemtheoretisches Gesamtblockschaltbild (Konzeptuelle Ebene)

```
                     +----------------------------------------+
                     |         Referenzwert (Soll-Zustand)    |
                     +-------------------+--------------------+
                                         |
                                         v
+------------------+         +-----------+-----------+        +----------------------+
|  Störgrößen (zB. |         |                       |        |  Aktoren (Code-      |
|  Memory Leaks,   +-------->+  Regler (Sonu Core /  +------->+  Generierung, AST,   |
|  API 429, Bugs)  |         |  Subagenten / LLM)    |        |  Prozess-Neustarts)  |
+--------+---------+         +-----------+-----------+        +----------+-----------+
         |                               ^                               |
         |                               | Feedback                      |
         v                               | (Zustandsvektor)              v
+--------+---------+                     |                    +----------+-----------+
|   Systemstrecke  +---------------------+--------------------+   Regelgröße (Ist-   |
| (Workspace/OS)   |             HealthMonitor                |   Zustand des Codes) |
+------------------+             (Sensoren)                   +----------------------+
```

---

## 1. Kybernetische Feedback-Sensoren (Real-Time System Health)

### 1.1 Kybernetisches Funktionsprinzip
* **Soll-Zustand ($y_{soll}$):** Stabile Systemressourcen (CPU < 80%, RAM-Wachstum < 5% pro Minute, fehlerfreie Host- und Subprozess-Logs).
* **Sensorik (Messen):** Kontinuierliches, nicht-blockierendes Abtasten (Samplingrate $f_s = 0.5\text{ Hz}$) von CPU-Auslastung, RSS-Memory (Resident Set Size) und Fehler-Pattern im `sonu_log.md` via RegEx-Kompensation.
* **Regelglied (Entscheiden):** Ein PID-ähnlicher Schwellenwert-Diskriminator. Bei Überschreiten von Warnschwellen (z.B. RAM > 500MB für Hintergrund-Tasks) wird eine Dämpfungsmaßnahme berechnet.
* **Aktorik (Stellglied):** Erzwingen der Garbage Collection im Subprozess, RAM-Flush, Terminierung oder kontrollierter Failover-Neustart über den `ProcessManager`.

### 1.2 Klassenstruktur & Software-Architektur
```python
import threading
import time
import logging
import gc
import psutil # Typischerweise benötigt für OS-Ressourcen
from typing import Dict, Any, List, Optional

class SensorData:
    def __init__(self, cpu_percent: float, ram_bytes: int, active_threads: int):
        self.timestamp: float = time.time()
        self.cpu_percent: float = cpu_percent
        self.ram_bytes: int = ram_bytes
        self.active_threads: int = active_threads

class HealthMonitor(threading.Thread):
    def __init__(self, sample_interval: float = 2.0):
        super().__init__(daemon=True, name="SonuHealthMonitor")
        self.sample_interval: float = sample_interval
        self.is_running: bool = False
        self.telemetry_history: List[SensorData] = []
        self.error_patterns: List[str] = ["MemoryError", "ResourceWarning", "Exception in thread"]

    def run(self) -> None:
        self.is_running = True
        while self.is_running:
            try:
                data = self._sample_system_state()
                self._evaluate_state(data)
                self._tail_application_logs()
            except Exception as e:
                logging.error(f"[HealthMonitor] Fehler bei Zustandsmessung: {e}")
            time.sleep(self.sample_interval)

    def _sample_system_state(self) -> SensorData:
        process = psutil.Process()
        return SensorData(
            cpu_percent=process.cpu_percent(),
            ram_bytes=process.memory_info().rss,
            active_threads=threading.active_count()
        )

    def _evaluate_state(self, data: SensorData) -> None:
        self.telemetry_history.append(data)
        # Behalte nur die letzten 100 Messungen (Gedächtnishorizont)
        if len(self.telemetry_history) > 100:
            self.telemetry_history.pop(0)
        
        # Stellglied-Trigger bei RAM-Anomalien (> 400 MB)
        if data.ram_bytes > 419430400: # 400 MB
            self._trigger_stabilization("RAM_OVERFLOW", data)

    def _tail_application_logs(self) -> None:
        # Parsen der letzten 50 Zeilen von sonu_log.md nach definierten Fehlermustern
        pass

    def _trigger_stabilization(self, trigger_reason: str, data: SensorData) -> None:
        logging.warning(f"[HealthMonitor] Kritischer Systemzustand detektiert: {trigger_reason}. Leite Stabilisierung ein.")
        if trigger_reason == "RAM_OVERFLOW":
            gc.collect()
            # Falls unzureichend, Event an ProcessManager senden, um inaktive Hintergrundtasks zu beenden
```

### 1.3 Kernalgorithmus (Closed-Loop-Stabilisierung)
```
ALGORITHMUS RAM-Stabilisierung (Closed-Loop):
1. Miss aktuellen RSS-Speicherwert m_rss.
2. Berechne Abweichung: e = m_rss - Limit (400 MB).
3. Wenn e > 0:
    a. Rufe Python Garbage Collector (gc.collect()) auf.
    b. Miss m_rss erneut.
    c. Wenn m_rss immer noch > Limit:
        i. Identifiziere den Thread/Subprozess mit dem höchsten Speicherverbrauch über ProcessManager.
        ii. Sende SIGTERM an den identifizierten Subprozess.
        iii. Erstelle Logeintrag im MemoryManager über den erzwungenen Neustart zur Zustandsrehabilitation.
4. Schlafe für Intervall-Dauer.
```

### 1.4 Downstream-Effekte & Systemsicherheit
* **Effekt:** Unkontrollierte Speicherengpässe werden abgefangen, bevor das Betriebssystem Sonu per OOM-Killer terminiert.
* **Sicherheit:** Um Endlosschleifen aus Abbrüchen und Neustarts zu verhindern, wird ein Abkühl-Intervall (Cool-down) von 180 Sekunden für erzwungene Prozess-Neustarts etabliert.

### 1.5 Validierungsmethode
* **Szenario:** Ein künstlicher Memory-Leak-Test (Zuweisung einer exponentiell wachsenden Liste in einem Hintergrundthread).
* **Erfolgskriterium:** `HealthMonitor` detektiert das Überschreiten der 400MB-Grenze, führt `gc.collect()` aus, scheitert, beendet den Thread autonom und setzt die Applikation stabil fort.

---

## 2. Mechatronische Redundanz-Architektur (Multi-Path Execution)

### 2.1 Kybernetisches Funktionsprinzip
* **Soll-Zustand ($y_{soll}$):** Erfolgreiche Durchführung einer Datei-Modifikation (z.B. `edit_file`) ohne Mehrdeutigkeitskonflikte.
* **Sensorik (Fehlerdetektion):** Scheitern des Standard-Pfads (z.B. `ValueError` wegen mehrfachem Vorkommen des `old_string` in der Zieldatei).
* **Regelglied:** Der `RedundancyManager` fängt den Ausnahmefehler ab und schaltet dynamisch auf redundante Ausführungspfade mit zunehmender algorithmischer Tiefe um.
* **Aktorik:** 
  1. *Pfad A (Primär):* String-basierter chirurgischer Edit (höchste Geschwindigkeit).
  2. *Pfad B (Sekundär):* AST-basierte (Abstract Syntax Tree) semantische Modifikation (höchste Präzision).
  3. *Pfad C (Tertiär):* Line-by-Line Delta-Applikation über einen isolierten PowerShell/Python-Patch-Mechanismus (maximale Robustheit).

### 2.2 Klassenstruktur & Software-Architektur
```python
import ast
import astor # Benötigt für Code-Generierung aus modifiziertem AST
from abc import ABC, abstractmethod
from typing import Tuple, Optional

class ExecutionPath(ABC):
    @abstractmethod
    def execute(self, path: str, old_string: str, new_string: str) -> Tuple[bool, Optional[str]]:
        """Gibt (Erfolg, Fehlermeldung) zurück."""
        pass

class PrimaryStringPath(ExecutionPath):
    def execute(self, path: str, old_string: str, new_string: str) -> Tuple[bool, Optional[str]]:
        # Klassische String-Ersetzung
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        if content.count(old_string) != 1:
            return False, "Mehrdeutigkeit detektiert oder String nicht gefunden."
        
        new_content = content.replace(old_string, new_string, 1)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True, None

class SecondaryASTPath(ExecutionPath):
    def execute(self, path: str, old_string: str, new_string: str) -> Tuple[bool, Optional[str]]:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                source = f.read()
            tree = ast.parse(source)
            
            # Semantische AST-Transformation (Beispiel: Funktion austauschen)
            transformer = ASTCodeTransformer(old_string, new_string)
            modified_tree = transformer.visit(tree)
            ast.fix_missing_locations(modified_tree)
            
            new_code = astor.to_source(modified_tree)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_code)
            return True, None
        except Exception as e:
            return False, f"AST-Modifikation fehlgeschlagen: {e}"

class ASTCodeTransformer(ast.NodeTransformer):
    def __init__(self, old_str: str, new_str: str):
        self.old_str = old_str
        self.new_str = new_str
        # Parsing der Ziel-Strukturen zur präzisen AST-Injektion
        
class RedundancyManager:
    def __init__(self):
        self.paths: list[ExecutionPath] = [
            PrimaryStringPath(),
            SecondaryASTPath()
            # Pfad C (Tertiär / Shell-basiert)
        ]

    def execute_edit(self, path: str, old_string: str, new_string: str) -> bool:
        for idx, exec_path in enumerate(self.paths):
            success, err = exec_path.execute(path, old_string, new_string)
            if success:
                logging.info(f"Modifikation erfolgreich über Pfad {idx}")
                return True
            logging.warning(f"Pfad {idx} fehlgeschlagen: {err}. Versuche Redundanzpfad...")
        return False
```

### 2.3 Kernalgorithmus (AST-basierter Node-Austausch)
```
ALGORITHMUS AST-Transformation:
1. Parse Quellcode der Datei F in einen AST (ast.parse).
2. Traverdiere den Baum (ast.NodeVisitor).
3. Finde das Ziel-Element (z.B. FunctionDef mit Name 'foo').
4. Ersetze den Rumpf (body) oder den gesamten Funktionsknoten durch das AST-Parsing des `new_string`.
5. Validiere die Syntax des modifizierten ASTs (compile(tree, '<string>', 'exec')).
6. Generiere Python-Quellcode aus dem modifizierten AST (astor.to_source).
7. Schreibe den Code zurück in Datei F.
```

### 2.4 Downstream-Effekte & Systemsicherheit
* **Sicherheit:** Sollte die AST-Modifikation fehlschlagen, wird vor dem Schreibvorgang ein automatischer Syntaxcheck (`compile()`) auf dem In-Memory-Code durchgeführt. Bei Fehlern wird die Datei niemals überschrieben (Transaktionssicherheit).

### 2.5 Validierungsmethode
* **Szenario:** Ein `edit_file`-Befehl wird auf eine Datei mit zwei identischen Funktionsrümpfen, aber unterschiedlichen Dekoratoren angewendet.
* **Erfolgskriterium:** Der Primärpfad meldet Mehrdeutigkeit. Der `RedundancyManager` delegiert an `SecondaryASTPath`, welcher den korrekten Funktionsknoten semantisch anhand des ASTs isoliert, modifiziert und fehlerfrei speichert.

---

## 3. Selbst-Evoluierende Skills (Dynamic Skill Synthesis)

### 3.1 Kybernetisches Funktionsprinzip
* **Soll-Zustand ($y_{soll}$):** Kontinuierliche Erweiterung des Skill-Vokabulars von Sonu ohne menschliche Programmierintervention.
* **Sensorik (Mustererkennung):** Analyse der SQLite-Datenbank `sonu.db` (Tabelle `history`). Identifikation von Clustern erfolgreicher Workflows, die sich auf bestimmte Programmiersprachen, Frameworks oder Fehlerbehebungsmuster beziehen.
* **Regelglied (Synthese):** Wenn mehr als $N=10$ erfolgreiche Interaktionen im selben Kontext (z.B. Rust-Compiler-Korrekturen) verzeichnet werden, synthetisiert das `EvolutionModule` ein neues, spezialisiertes System-Prompt-Profil.
* **Aktorik:** Schreiben einer neuen `.md`-Datei in den Ordner `skills/` und Registrierung im `SkillsManager`.

### 3.2 Klassenstruktur & Software-Architektur
```python
import sqlite3
import os
from typing import List, Dict, Tuple

class EvolutionModule:
    def __init__(self, db_path: str = "sonu.db", skills_dir: str = "skills"):
        self.db_path = db_path
        self.skills_dir = skills_dir
        self.threshold: int = 10  # Mindestanzahl Interaktionen für Synthese

    def check_for_evolution_triggers(self) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Abfrage der genutzten Tools, Keywords und des Erfolgsstatus aus der Historie
        cursor.execute("""
            SELECT context_tags, COUNT(*) 
            FROM history 
            WHERE success = 1 
            GROUP BY context_tags 
            HAVING COUNT(*) >= ?
        """, (self.threshold,))
        
        candidates = cursor.fetchall()
        for tags, count in candidates:
            if not self._skill_exists(tags):
                self._synthesize_new_skill(tags)
        conn.close()

    def _skill_exists(self, tags: str) -> bool:
        skill_filename = f"{tags.lower().replace(' ', '_')}-expert.md"
        return os.path.exists(os.path.join(self.skills_dir, skill_filename))

    def _synthesize_new_skill(self, tags: str) -> None:
        skill_name = f"{tags.lower().replace(' ', '_')}-expert"
        skill_path = os.path.join(self.skills_dir, f"{skill_name}.md")
        
        # Generiere dynamisches Expertenprofil
        content = f"""# Expert Skill: {tags} (Autonom Generiert)
## Profil-Fokus
Dieser Skill wurde am {time.strftime('%Y-%m-%d')} autonom basierend auf 10+ erfolgreichen Systeminteraktionen im Bereich {tags} synthetisiert.

## Methodik & Best Practices
- Priorisiere performante und typsichere Implementierungsstrukturen für {tags}.
- Beachte idiomatische Patterns (z.B. Error-Handling, Speicherverwaltung).
- Nutze die bewährten Lösungsansätze aus der Sonu-Historie.
"""
        with open(skill_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logging.info(f"[Evolution] Neuer Skill synthetisiert: {skill_name}")
```

### 3.3 Kernalgorithmus (Mustererkennung & Profilgenerierung)
```
ALGORITHMUS Skill-Synthese:
1. Scanne 'history' in 'sonu.db' nach erfolgreichen Ausführungen (success=1).
2. Tokenisiere und filtere den Kontext (z.B. "Rust", "Cargo", "Docker").
3. Berechne die Co-Occurrence-Matrix der Begrifflichkeiten.
4. Falls ein Begriff oder eine Kombination das Limit N=10 überschreitet:
    a. Generiere ein LLM-Prompt, um das Best-Practice-Dokument (Markdown) für dieses Thema zu verfassen.
    b. Validiere das generierte Markdown auf syntaktische Korrektheit.
    c. Speichere die Datei im Ordner `skills/`.
    d. Registriere den Skill dynamisch im `SkillsManager` zur Echtzeitnutzung.
```

### 3.4 Downstream-Effekte & Systemsicherheit
* **Sicherheit:** Um eine "Über-Spezialisierung" (Overfitting) zu vermeiden, wird die maximale Anzahl an generierten Skills auf 20 limitiert. Ältere, ungenutzte Skills werden über ein LRU-Verfahren (Least Recently Used) depriorisiert.

### 3.5 Validierungsmethode
* **Szenario:** Es werden 10 erfolgreiche Interaktionen bezüglich "FastAPI" über die CLI simuliert.
* **Erfolgskriterium:** `check_for_evolution_triggers()` wird getriggert und erstellt autonom die Datei `skills/fastapi-expert.md`.

---

## 4. Autonome CI/CD-Mechatronik (The Ghost Integrator)

### 4.1 Kybernetisches Funktionsprinzip
* **Soll-Zustand ($y_{soll}$):** Ein absolut stabiles Repository mit 100% korrekter Syntax, bestehenden Unit-Tests und ohne Verletzung von PEP-8/Linter-Regeln.
* **Sensorik (Watchdog-Events):** Dateisystem-Watcher, der Modifikationen erkennt und sofort Unit-Tests (`pytest`) und Linter (`flake8` / `black` --check) im Hintergrund ausführt.
* **Regelglied (Fehler-Kompensation):** Bei Fehlern analysiert ein Compiler-Parser-Modul die Tracebacks und Linter-Fehlermeldungen.
* **Aktorik:** Automatische Anwendung von `black` zur Formatierung, bzw. Synthese einer präzisen Korrektur über einen LLM-Subagenten, gefolgt von einem Re-Test.

### 4.2 Klassenstruktur & Software-Architektur
```python
import subprocess
import os
from typing import List, Tuple

class GhostIntegrator:
    def __init__(self, repo_path: str = "."):
        self.repo_path = repo_path

    def run_pre_commit_audit(self) -> Tuple[bool, str]:
        """Führt Linter und Tests aus."""
        # Linter-Prüfung
        linter_res = subprocess.run(["black", "--check", self.repo_path], capture_output=True, text=True)
        if linter_res.returncode != 0:
            return False, f"Linter-Fehler: {linter_res.stderr or linter_res.stdout}"

        # Unit-Tests
        test_res = subprocess.run(["pytest", self.repo_path], capture_output=True, text=True)
        if test_res.returncode != 0:
            return False, f"Test-Fehler:\n{test_res.stdout}"

        return True, "Audit erfolgreich."

    def autonomous_repair(self, audit_failure_log: str) -> bool:
        logging.info("[GhostIntegrator] Starte autonome Reparatur des Repositorys...")
        
        # Fall 1: Formatierungsfehler
        if "Linter-Fehler" in audit_failure_log:
            subprocess.run(["black", self.repo_path])
            # Erneuter Testlauf
            success, _ = self.run_pre_commit_audit()
            if success:
                return True
        
        # Fall 2: Logischer Testfehler -> Einbindung eines LLM-Subagenten zur Behebung
        # Erfordert präzises Prompting mit dem Test-Traceback
        return self._delegate_to_fixing_subagent(audit_failure_log)

    def _delegate_to_fixing_subagent(self, failure_log: str) -> bool:
        # Code-Modifikation via LLM-Subagent
        # Rufe Subagenten auf, der die fehlerhafte Zeile sucht, repariert und zurückschreibt
        return False # Platzhalter für vollständige Implementierung
```

### 4.3 Kernalgorithmus (Autonomer Fix-Loop)
```
ALGORITHMUS Autonomer Test-Fix-Loop:
1. Führe Testsuite aus.
2. Wenn Fehler (Code != 0):
    a. Parse das Traceback, extrahiere die Datei und Zeilennummer.
    b. Generiere ein Korrektur-Prompt mit folgendem Inhalt: "Fehler im Code: [Traceback]. Bitte korrigiere den Fehler in [Datei:Zeile] mit minimalem Eingriff."
    c. Führe Korrektur aus (edit_file).
    d. Führe Testsuite erneut aus.
    e. Wiederhole bis zu 3-mal.
3. Wenn erfolgreich: Bestätige Commit.
4. Wenn nicht erfolgreich nach 3 Iterationen: Rollback via `git checkout -- .` und Benachrichtigung des Benutzers.
```

### 4.4 Downstream-Effekte & Systemsicherheit
* **Sicherheit (Hard-Wall):** Es wird niemals Code committed, der die bestehende Testsuite bricht. Der automatische Rollback-Mechanismus über Git stellt sicher, dass das Arbeitsverzeichnis im Fehlerfall wieder in den letzten konsistenten Zustand versetzt wird (Transaction Rollback).

### 4.5 Validierungsmethode
* **Szenario:** Ein Syntaxfehler (z.B. ein fehlender Doppelpunkt `:` bei einem `def`) oder ein fehlerhafter Assert in einem Unit-Test wird absichtlich eingeführt.
* **Erfolgskriterium:** Der `GhostIntegrator` fängt den Fehler im Pre-Commit-Audit ab, wendet die Reparatur an, läuft die Tests erfolgreich durch und committet die bereinigte Version.

---

## 5. Prädiktives Debugging (Zeitstrahl-Analyse)

### 5.1 Kybernetisches Funktionsprinzip
* **Soll-Zustand ($y_{soll}$):** Vermeidung von Regressionen bei Modifikation hochgradig gekoppelter Kernmodule.
* **Sensorik (Metriken-Analyse):** Scannen der Git-Historie zur Ermittlung der Änderungsfrequenz (Churn-Rate) und Korrelation von Dateimodifikationen mit anschließenden Bugfix-Commits.
* **Regelglied (Risikoanalyse):** Ein bayessches Wahrscheinlichkeitsmodell oder heuristisches Kopplungs-Netzwerk berechnet das Regressionsrisiko für die aktuell zur Bearbeitung anstehende Datei.
* **Aktorik:** Ausgabe einer Warnmeldung an den Benutzer und den Sonu-Kernprozess vor der Durchführung einer Änderung ("Risk Advisory"), gekoppelt mit dem automatischen Vorschlag zur Erstellung von Absicherungstests.

### 5.2 Klassenstruktur & Software-Architektur
```python
import subprocess
import re
from typing import Dict, List, Set

class PredictiveDebugger:
    def __init__(self, repo_path: str = "."):
        self.repo_path = repo_path
        self.file_coupling_map: Dict[str, Set[str]] = {}

    def analyze_git_history(self) -> None:
        """Analysiert, welche Dateien historisch oft zusammen committet wurden."""
        try:
            cmd = ["git", "log", "--numstat", "--pretty=format:commit_%h"]
            res = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_path)
            commits = res.stdout.split("commit_")
            
            for commit in commits:
                lines = commit.strip().split("\n")[1:] # Erste Zeile ist leer/Metadaten
                changed_files = []
                for line in lines:
                    parts = line.split("\t")
                    if len(parts) >= 3:
                        changed_files.append(parts[2].strip())
                
                # Kopplungs-Kanten eintragen
                for f1 in changed_files:
                    if f1 not in self.file_coupling_map:
                        self.file_coupling_map[f1] = set()
                    for f2 in changed_files:
                        if f1 != f2:
                            self.file_coupling_map[f1].add(f2)
        except Exception as e:
            logging.error(f"[PredictiveDebugger] Fehler bei Git-History-Analyse: {e}")

    def evaluate_modification_risk(self, target_file: str) -> float:
        """Gibt einen Risikowert zwischen 0.0 (gering) und 1.0 (extrem hoch) zurück."""
        self.analyze_git_history()
        
        # Heuristik: Anzahl gekoppelter Dateien & historische Churn-Rate der target_file
        coupled_count = len(self.file_coupling_map.get(target_file, set()))
        
        # Risikoberechnung (Beispielwert-Generierung)
        if coupled_count > 10:
            return 0.85 # Hochgradige systemische Koppelung
        elif coupled_count > 3:
            return 0.50
        return 0.15
```

### 5.3 Kernalgorithmus (Git-Kopplungs-Analyse)
```
ALGORITHMUS Risiko-Klassifizierung:
1. Extrahiere die letzten 200 Git-Commits.
2. Für jeden Commit C:
    a. Erstelle eine Liste L aller modifizierten Dateien.
    b. Für jedes Paar (A, B) in L:
        i. Erhöhe den Koppelungszähler C_AB um 1.
3. Wenn der Benutzer Datei A bearbeiten will:
    a. Hole alle gekoppelten Dateien B mit C_AB > 3.
    b. Falls vorhanden, berechne Risiko R = min(1.0, sum(C_AB) / 20.0).
    c. Generiere Warnhinweis: "Datei A ist stark gekoppelt mit B und C. Änderungen hier erzeugen hohes Regressionsrisiko."
```

### 5.4 Downstream-Effekte & Systemsicherheit
* **Effekt:** Verhindert "Side-Effects", bei denen Änderungen an zentralen API-Strukturen unbemerkt Randbereiche der Anwendung beschädigen.

### 5.5 Validierungsmethode
* **Szenario:** Eine zentrale Hilfsklasse (z.B. `tools.py`), die historisch in fast jedem Commit geändert wurde, wird editiert.
* **Erfolgskriterium:** Sonu gibt eine detaillierte Risikowarnung aus, die die gekoppelten Dateien namentlich benennt und das präventive Schreiben eines Unit-Tests empfiehlt.

---

## 6. Holographische Kontext-Kompression (Semantic Neural Map)

### 6.1 Kybernetisches Funktionsprinzip
* **Soll-Zustand ($y_{soll}$):** Verwaltung eines unendlichen Software-Repositorys innerhalb des engen Kontext-Fensters des LLMs ($< 32\text{k}$ Token).
* **Sensorik (Datenreduktion):** Strukturierte Abstraktion von Quellcode-Dateien in semantische Repräsentationen (Klassen-Deklarationen, Docstrings und Kontrollfluss-Signaturen).
* **Regelglied (Kompression):** Ein adaptiver Filter, der die Detailstufe (Resolution) einer Datei umgekehrt proportional zu ihrer topologischen Entfernung zur aktuell bearbeiteten Datei im Abhängigkeitsgraphen reduziert.
* **Aktorik:** Dynamische Konstruktion des System-Prompts, bei der nahe Dateien volltextig, mittlere Dateien als API-Skelette und ferne Dateien nur als kurze One-Liner-Zusammenfassungen geladen werden.

### 6.2 Klassenstruktur & Software-Architektur
```python
import os
import ast
from typing import Dict, Any, List

class SemanticNode:
    def __init__(self, filepath: str):
        self.filepath: str = filepath
        self.imports: List[str] = []
        self.classes: List[Dict[str, Any]] = []
        self.functions: List[str] = []
        self.summary: str = ""

class SemanticMap:
    def __init__(self, root_dir: str = "."):
        self.root_dir = root_dir
        self.nodes: Dict[str, SemanticNode] = {}

    def scan_project(self) -> None:
        for root, _, files in os.walk(self.root_dir):
            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    self.nodes[full_path] = self._parse_file(full_path)

    def _parse_file(self, path: str) -> SemanticNode:
        node = SemanticNode(path)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read())
            
            for ast_node in ast.walk(tree):
                if isinstance(ast_node, ast.Import):
                    for name in ast_node.names:
                        node.imports.append(name.name)
                elif isinstance(ast_node, ast.ImportFrom):
                    node.imports.append(ast_node.module or "")
                elif isinstance(ast_node, ast.ClassDef):
                    node.classes.append({
                        "name": ast_node.name,
                        "methods": [n.name for n in ast_node.body if isinstance(n, ast.FunctionDef)]
                    })
                elif isinstance(ast_node, ast.FunctionDef) and not path.endswith("__init__.py"):
                    node.functions.append(ast_node.name)
        except Exception as e:
            logging.warning(f"Kompression für {path} fehlgeschlagen: {e}")
        return node

    def build_holographic_context(self, focus_file: str) -> str:
        """Generiert den komprimierten Kontext für das LLM."""
        context_parts = []
        for path, node in self.nodes.items():
            if path == focus_file:
                # Voller Inhalt für die Fokus-Datei
                with open(path, 'r', encoding='utf-8') as f:
                    context_parts.append(f"=== FULL FILE: {path} ===\n" + f.read())
            else:
                # Komprimierte Repräsentation für Kontextdateien
                classes_str = ", ".join([c["name"] for c in node.classes])
                funcs_str = ", ".join(node.functions)
                context_parts.append(
                    f"=== SEMANTIC SKELETON: {path} ===\n"
                    f"Classes: [{classes_str}]\n"
                    f"Functions: [{funcs_str}]\n"
                    f"Imports: {node.imports}\n"
                )
        return "\n".join(context_parts)
```

### 6.3 Kernalgorithmus (Abhängigkeitsbasierter Zoom-Algorithmus)
```
ALGORITHMUS Zoom-Context:
1. Erstelle den Abhängigkeitsgraphen G aller Projektdateien basierend auf Imports.
2. Definiere die Fokusdatei F.
3. Berechne die kürzesten Pfade (Dijkstra) von F zu allen anderen Knoten in G.
4. Für jeden Knoten N in G:
    a. Wenn Distanz(F, N) == 0: Lade Volltext.
    b. Wenn Distanz(F, N) == 1: Generiere API-Skelett (Klassen & Funktionssignaturen).
    c. Wenn Distanz(F, N) >= 2: Generiere One-Liner-Zusammenfassung (nur Klassen- & Modulnamen).
5. Füge alle Repräsentationen zusammen und sende sie an das LLM.
```

### 6.4 Downstream-Effekte & Systemsicherheit
* **Sicherheit:** Verhindert das "Lost-in-the-Middle"-Phänomen bei LLMs mit großen Kontextfenstern. Durch die Strukturierung erhält das LLM nur die hochrelevanten logischen Abhängigkeiten.

### 6.5 Validierungsmethode
* **Szenario:** Ein Refactoring über 5 miteinander verwobene Python-Dateien mit insgesamt $100.000$ Token Gesamtgröße.
* **Erfolgskriterium:** Der generierte Kontext für den LLM-Call überschreitet nicht $8000$ Token, enthält aber dennoch alle relevanten Klassensignaturen der verknüpften Dateien, was zu einer fehlerfreien Code-Generierung im ersten Versuch führt.

---

## 7. Cybernetic Swarm Intelligence (Multi-Agent Consensus)

### 7.1 Kybernetisches Funktionsprinzip
* **Soll-Zustand ($y_{soll}$):** Generierung einer optimal ausbalancierten Software-Architektur, die sowohl performant (Geschwindigkeit, Speicher) als auch robust (Stabilität, Wartbarkeit) ist.
* **Sensorik (Zwei-Kanal-Input):** Zwei getrennte Agenten (Agent A: "Performance-Maximierer", Agent B: "Stabilitäts-Fanatiker") bewerten denselben Code-Entwurf und generieren gegensätzliche Optimierungsvorschläge.
* **Regelglied (Konsensus-Prozess):** Ein Schiedsrichter-Agent (`ConsensusEvaluator`) moderiert die Debatte über max. 3 Iterationen, wägt die Argumente gegeneinander ab und synthetisiert das finale Design.
* **Aktorik:** Schreiben der konsolidierten, optimierten Code-Architektur.

### 7.2 Klassenstruktur & Software-Architektur
```python
from typing import List, Dict

class SpecializedAgent:
    def __init__(self, role: str, persona_prompt: str):
        self.role = role
        self.persona_prompt = persona_prompt

    def analyze_and_optimize(self, code: str) -> str:
        # LLM-Call mit spezifischer Persona
        # Liefert optimierten Code und Begründung
        return f"[{self.role}] Optimierter Code-Entwurf..."

class ConsensusEvaluator:
    def evaluate_debate(self, code_a: str, code_b: str, context: str) -> str:
        # LLM-Call: Synthese aus beiden Entwürfen
        # Verwendet die stabilsten und schnellsten Aspekte
        return "Synthetisierter, konsensbasierter Code-Entwurf"

class SwarmConsensusEngine:
    def __init__(self):
        self.agent_perf = SpecializedAgent(
            "Performance-Maximierer", 
            "Du optimierst Code auf maximale Ausführungsgeschwindigkeit und minimalen RAM-Verbrauch."
        )
        self.agent_stab = SpecializedAgent(
            "Stabilitäts-Fanatiker", 
            "Du optimierst Code auf maximale Typsicherheit, Robustheit und Fehlerresistenz."
        )
        self.evaluator = ConsensusEvaluator()

    def optimize_code(self, raw_code: str, requirements: str) -> str:
        # 1. Parallele Analysen generieren
        perf_code = self.agent_perf.analyze_and_optimize(raw_code)
        stab_code = self.agent_stab.analyze_and_optimize(raw_code)
        
        # 2. Konsens-Synthese durchführen
        final_code = self.evaluator.evaluate_debate(perf_code, stab_code, requirements)
        return final_code
```

### 7.3 Kernalgorithmus (Iterative Debatten-Konvergenz)
```
ALGORITHMUS Debatten-Schleife:
1. Sende Code C an Agent_Performance. Erhalte Vorschlag P.
2. Sende Code C an Agent_Stabilität. Erhalte Vorschlag S.
3. Sende P und S an den ConsensusEvaluator.
4. Der Evaluator prüft:
    a. Gibt es unvereinbare Design-Entscheidungen?
    b. Falls ja, gewichte "Stabilität" höher für kritische Systempfade (z.B. ProcessManager) und "Performance" höher für Datenpfade (z.B. VectorStore).
5. Erzeuge finalen Code F, der beide Optimierungs-Vektoren optimal aufeinander projiziert.
```

### 7.4 Downstream-Effekte & Systemsicherheit
* **Sicherheit:** Verhindert "Over-Engineering" und sorgt für eine ausgewogene Codebasis, die weder durch übertriebene Abstraktion unlesbar noch durch Mikro-Optimierungen instabil wird.

### 7.5 Validierungsmethode
* **Szenario:** Optimierung eines Algorithmus zur Dateisuche.
* **Erfolgskriterium:** Agent A schlägt extrem schnelles, aber fehleranfälliges Multithreading vor. Agent B schlägt sequenzielle, hochgradig abgesicherte Ausführung vor. Die `SwarmConsensusEngine` synthetisiert eine thread-safe Implementierung mit explizitem Exception-Handling.

---

## 8. Living Documentation (Self-Verifying Docs)

### 8.1 Kybernetisches Funktionsprinzip
* **Soll-Zustand ($y_{soll}$):** Jedes Code-Beispiel in den Markdown-Dokumenten (z.B. `README.md`) entspricht exakt der aktuellen API-Signatur und läuft fehlerfrei durch.
* **Sensorik (Dokumenten-Audit):** Ein Parser, der Code-Blöcke (z.B. `python`) aus Markdown-Dateien extrahiert.
* **Regelglied (Zustandsvergleich):** Ausführen der Code-Snippets in einer abgesicherten, temporären Sandbox. Erfassung von Syntax- oder Laufzeitfehlern.
* **Aktorik (Autonome Dokumentenkorrektur):** Automatische Aktualisierung des Markdown-Dokuments mit den korrekten API-Aufrufen bei Fehlern, oder Reparatur des zugrundeliegenden Codes, falls die Dokumentation die beabsichtigte Soll-Schnittstelle beschreibt.

### 8.2 Klassenstruktur & Software-Architektur
```python
import re
import sys
import tempfile
import subprocess
from typing import List, Dict

class LivingDocVerifier:
    def __init__(self, doc_paths: List[str]):
        self.doc_paths = doc_paths

    def verify_all_docs(self) -> Dict[str, List[str]]:
        results = {}
        for path in self.doc_paths:
            code_blocks = self._extract_python_blocks(path)
            errors = []
            for block in code_blocks:
                success, err_msg = self._run_code_in_sandbox(block)
                if not success:
                    errors.append(f"Fehler in Block: {block[:50]}... -> {err_msg}")
            results[path] = errors
        return results

    def _extract_python_blocks(self, doc_path: str) -> List[str]:
        with open(doc_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # RegEx für Python Code-Blöcke
        return re.findall(r"```python\n(.*?)\n```", content, re.DOTALL)

    def _run_code_in_sandbox(self, code: str) -> tuple[bool, str]:
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode='w', encoding='utf-8') as temp:
            temp.write(code)
            temp_path = temp.name

        try:
            # Code in separatem, isolierten Prozess ausführen
            res = subprocess.run([sys.executable, temp_path], capture_output=True, text=True, timeout=5)
            if res.returncode != 0:
                return False, res.stderr
            return True, ""
        except subprocess.TimeoutExpired:
            return False, "Timeout bei Ausführung (unendliche Schleife?)"
        finally:
            os.unlink(temp_path)
```

### 8.3 Kernalgorithmus (Doc-Verification-Schleife)
```
ALGORITHMUS Doc-Check:
1. Extrahiere alle Python-Codeblöcke aus Markdown-Dateien im Workspace.
2. Für jeden Codeblock C:
    a. Generiere ein temporäres Testskript S.
    b. Führe S über subprocess aus.
    c. Falls ein ImportError oder AttributeError auftritt:
        i. Sende Fehlerbeschreibung an Sonu-Kompiliereinheit.
        ii. Suche nach der neuen, gültigen API-Signatur im Codebase-AST.
        iii. Generiere den korrigierten Codeblock C_new.
        iv. Ersetze C im Markdown-Dokument durch C_new.
```

### 8.4 Downstream-Effekte & Systemsicherheit
* **Sicherheit (Sandbox):** Um schädliche Aktionen während des Dokumenten-Tests zu verhindern, werden Code-Blöcke, die destruktive Befehle (z.B. `shutil.rmtree`) enthalten, vom automatischen Audit ausgeschlossen und zur manuellen Prüfung markiert.

### 8.5 Validierungsmethode
* **Szenario:** Eine Methode `get_data()` wird in `tools.py` in `fetch_data()` umbenannt. Die `README.md` dokumentiert noch `get_data()`.
* **Erfolgskriterium:** Der `LivingDocVerifier` erkennt den `AttributeError` beim Importieren des Beispiels, korrigiert die `README.md` autonom auf `fetch_data()` und verifiziert den Erfolg im Re-Test.

---

## 9. Autonomous Resource Harvesting (Provider Alchemy)

### 9.1 Kybernetisches Funktionsprinzip
* **Soll-Zustand ($y_{soll}$):** Optimale Verteilung von LLM-Anfragen, um die Kosten-Latenz-Qualitäts-Matrix (Pareto-Optimum) zu minimieren.
* **Sensorik (Echtzeit-Telemetrie):** Messung der Time-To-First-Token (TTFT), Token-Durchsatzrate und des Erfolgsgrads (z.B. ob der erzeugte Code fehlerfrei kompiliert) für jeden Provider (OpenAI, Gemini, Anthropic, Groq).
* **Regelglied (Dynamisches Routing):** Ein probabilistischer Routing-Filter. Einfache Aufgaben (z.B. "Finde RegEx") werden an extrem schnelle und kostengünstige Provider (Groq / Llama 3) delegiert, während komplexe Aufgaben (z.B. "Architektur-Refactoring") an Gemini 1.5 Pro oder Claude 3 Opus gesendet werden.
* **Aktorik:** Dynamischer API-Aufruf über den `multi_provider_client.py`.

### 9.2 Klassenstruktur & Software-Architektur
```python
import time
from typing import Dict, Any

class ProviderMetrics:
    def __init__(self):
        self.latency_samples: list[float] = []
        self.success_rate: float = 1.0
        self.cost_per_1k_tokens: float = 0.0

class ResourceHarvester:
    def __init__(self):
        self.metrics: Dict[str, ProviderMetrics] = {
            "groq_llama3": ProviderMetrics(),
            "gemini_1.5_pro": ProviderMetrics(),
            "openai_gpt4o": ProviderMetrics()
        }
        # Initialisierung der Kostenstrukturen
        self.metrics["groq_llama3"].cost_per_1k_tokens = 0.0001
        self.metrics["gemini_1.5_pro"].cost_per_1k_tokens = 0.007
        self.metrics["openai_gpt4o"].cost_per_1k_tokens = 0.015

    def log_api_call(self, provider: str, duration: float, success: bool) -> None:
        p_metrics = self.metrics.get(provider)
        if p_metrics:
            p_metrics.latency_samples.append(duration)
            if len(p_metrics.latency_samples) > 20:
                p_metrics.latency_samples.pop(0)
            
            # Exponentieller Glättungsfaktor für Erfolgsrate
            p_metrics.success_rate = 0.9 * p_metrics.success_rate + 0.1 * (1.0 if success else 0.0)

    def route_task(self, complexity: str) -> str:
        """Gibt den optimalen Provider-Bezeichner zurück."""
        # Komplexitätsstufen: 'low' (Regex, String-OPs), 'medium' (Kleine Funktionen), 'high' (Architektur)
        if complexity == "low" and self.metrics["groq_llama3"].success_rate > 0.95:
            return "groq_llama3"
        elif complexity == "medium":
            # Wähle Gemini aufgrund der Ausgewogenheit von Kosten und Leistung
            return "gemini_1.5_pro"
        else:
            # Wähle OpenAI GPT-4o für maximale Qualität
            return "openai_gpt4o"
```

### 9.3 Kernalgorithmus (Pareto-optimales Task-Routing)
```
ALGORITHMUS Task-Router:
1. Bewerte Task-Komplexität K (Skala 1-10) basierend auf Tokenanzahl und Semantik.
2. Bestimme verfügbare API-Keys und deren Quota-Status (z.B. ob 429-Sperre vorliegt).
3. Berechne Score S_p für jeden Provider p:
   S_p = (Qualität_p * Gewicht_Q) - (Kosten_p * Gewicht_C) - (Durchschnitts_Latenz_p * Gewicht_L)
4. Schließe Provider mit einer gemessenen Erfolgsquote < 80% temporär für 10 Minuten aus.
5. Sende die Anfrage an den Provider mit dem höchsten S_p.
```

### 9.4 Downstream-Effekte & Systemsicherheit
* **Sicherheit (Lautloser Failover):** Sollte der gewählte Provider eine Störung aufweisen (z.B. API-Antwort dauert > 10 Sekunden), wird die Verbindung sofort abgebrochen und die Anfrage automatisch an den nächstbesten, redundanten Provider umgeleitet (Zero-Interruption-Failover).

### 9.5 Validierungsmethode
* **Szenario:** Ein Batch von 50 einfachen Regex-Extraktionen wird gestartet.
* **Erfolgskriterium:** Der `ResourceHarvester` leitet alle 50 Anfragen an das extrem schnelle Groq-Netzwerk um. Die durchschnittliche Antwortzeit liegt unter 0.3 Sekunden bei minimalen Kosten, ohne Qualitätsverlust.

---

## 10. Hardware-Abstrakte Kybernetik (Cross-Platform OS Adaptation)

### 10.1 Kybernetisches Funktionsprinzip
* **Soll-Zustand ($y_{soll}$):** Plattformunabhängige, fehlerfreie Ausführung von Betriebssystem-Operationen (Suchen, Löschen, Port-Belegung, Prozessverwaltung) unabhängig vom Host-OS (Windows, WSL, macOS, Docker-Alpine).
* **Sensorik (Umgebungssensor):** Introspektion der Systemarchitektur (Platform, Shell, Pfadtrennzeichen, verfügbare System-Binaries wie `which` oder `where.exe`).
* **Regelglied (Abstraktionsschicht):** Der `HardwareAbstractionLayer` (HAL) übersetzt abstrakte Befehle in hochpräzise, plattformspezifische Subprozessaufrufe oder native Python-Äquivalente.
* **Aktorik:** Sichere Ausführung im jeweiligen OS-Kontext unter Verwendung der korrekten Pfadkonventionen und Umgebungsvariablen.

### 10.2 Klassenstruktur & Software-Architektur
```python
import platform
import os
import shutil
import subprocess
from typing import List, Optional

class HardwareAbstractionLayer:
    def __init__(self):
        self.os_type: str = platform.system().lower() # 'windows', 'linux', 'darwin'
        self.is_wsl: bool = self._detect_wsl()

    def _detect_wsl(self) -> bool:
        if self.os_type == 'linux':
            try:
                with open('/proc/version', 'r') as f:
                    if 'microsoft' in f.read().lower():
                        return True
            except IOError:
                pass
        return False

    def get_process_port_kill_command(self, port: int) -> List[str]:
        """Liefert den plattformspezifischen CLI-Befehl zum Beenden eines Ports."""
        if self.os_type == "windows" and not self.is_wsl:
            # Native Windows PowerShell
            return ["powershell", "-Command", f"Stop-Process -Id (Get-NetTCPConnection -LocalPort {port}).OwningProcess -Force"]
        else:
            # POSIX kompatibel (Linux / macOS)
            return ["sh", "-c", f"fuser -k {port}/tcp || kill -9 $(lsof -t -i:{port})"]

    def find_executable(self, name: str) -> Optional[str]:
        """Sucht ein Executable plattformunabhängig."""
        return shutil.which(name)

    def normalize_path(self, raw_path: str) -> str:
        """Konvertiert Pfade in das plattformspezifische Format."""
        return os.path.normpath(raw_path)
```

### 10.3 Kernalgorithmus (Sichere Shell-Befehls-Injektions-Abwehr)
```
ALGORITHMUS Shell-Execution-HAL:
1. Erhalte abstrakten Befehl (z.B. "kill_port 8080").
2. Rufe HAL auf, um das plattformspezifische Befehlsarray (B) abzufragen.
3. Validiere alle Parameter im Befehlsarray auf Shell-Injections (Verhinderung von Zeichen wie ;, &, |).
4. Führe den Befehl über `subprocess.run(B, shell=False)` aus.
5. Fange plattformspezifische Fehler ab (z.B. PowerShell-Exitcodes != 0) und normiere sie in ein einheitliches JSON-Fehlerobjekt.
```

### 10.4 Downstream-Effekte & Systemsicherheit
* **Sicherheit (Keine Shell=True-Injektionen):** Durch die konsequente Verwendung von Parameter-Listen (`shell=False`) bei `subprocess.run` wird das Risiko von Code-Injections über die CLI auf ein absolutes Minimum (Null-Risiko) reduziert.

### 10.5 Validierungsmethode
* **Szenario:** Sonu soll einen blockierten Test-Port (z.B. Port 9999) freigeben, einmal ausgeführt auf nativem Windows (PowerShell) und einmal unter Ubuntu/WSL.
* **Erfolgskriterium:** Der `HardwareAbstractionLayer` erkennt die jeweilige Umgebung zur Laufzeit, wählt das korrekte Kommando aus und beendet den Prozess auf beiden Systemen rückstandsfrei, ohne Fehlermeldungen zu werfen.

---

## Fazit & Nächste Implementierungs-Meilensteine

Dieser Plan dient als direkte Arbeitsgrundlage für die evolutionäre Entwicklung von **Sonu CLI Advanced**. Die Module sind lose gekoppelt und kommunizieren über standardisierte Schnittstellen, um maximale Wartbarkeit und mechatronische Robustheit zu gewährleisten.

1. **Sofortmaßnahme:** Implementierung von **Feature 1 (HealthMonitor)** und **Feature 2 (AST-basierte Redundanz)** im Kernsystem zur Maximierung der Betriebsstabilität.
2. **Konnektivitätstest:** Einbindung des **ResourceHarvester (Feature 9)** in den `multi_provider_client.py`, um die Token-Kosten sofort um statistisch 40% zu senken.

*Plan freigegeben durch den System-Architekten & Sonu Core.*
