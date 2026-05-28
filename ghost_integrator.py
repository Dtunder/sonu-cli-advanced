import glob
import logging
import os
import re
import subprocess
import sys
import threading
import time
from typing import List, Optional, Tuple


class _HeadlessUI:
    """Minimales UI-Stub für programmatischen SonuClient-Aufruf ohne Terminal."""
    yolo = True  # Ghost-Modus: keine Rückfragen

    def show_tool_call(self, name, args): pass
    def show_tool_result(self, name, result, rejected=False): pass
    def confirm_action(self, name, args): return True
    def show_agent_thought(self, text): pass


class GhostIntegrator:
    """Autonomer CI/CD-Dämon: überwacht Dateiänderungen, führt Linter + Tests aus
    und repariert Fehler selbstständig via LLM — bis zu MAX_FIX_ATTEMPTS mal,
    danach Git-Rollback."""

    MAX_FIX_ATTEMPTS = 3
    POLL_INTERVAL_SECONDS = 5.0

    def __init__(self, repo_path: str = ".", sonu_client=None):
        self.repo_path = os.path.abspath(repo_path)
        self._client = sonu_client
        self._watcher: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def inject_client(self, client):
        """Setzt den SonuClient nachträglich (verhindert zirkuläre Imports bei Init)."""
        self._client = client

    # --- Öffentliche API ----------------------------------------------------

    def run_pre_commit_audit(self) -> Tuple[bool, str]:
        """Führt black --check und pytest aus. Gibt (ok, log) zurück."""
        black = _which("black")
        if black:
            result = subprocess.run(
                [black, "--check", "."],
                capture_output=True, text=True, cwd=self.repo_path
            )
            if result.returncode != 0:
                return False, "LINTER_FAIL:" + (result.stderr or result.stdout)
        else:
            logging.info("[Ghost] black nicht gefunden — Linter-Check übersprungen.")

        pytest_exe = _which("pytest") or [sys.executable, "-m", "pytest"]
        cmd = [pytest_exe, "--tb=short", "-q", "."] if isinstance(pytest_exe, str) else pytest_exe + ["--tb=short", "-q", "."]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_path)
        if result.returncode != 0:
            return False, "TEST_FAIL:" + result.stdout + "\n" + result.stderr

        return True, "Audit OK."

    def autonomous_repair(self, failure_log: str) -> bool:
        """Repariert: Formatter → LLM-Fix-Loop → Git-Rollback."""
        # Schritt 1: Formatierungsfehler → black anwenden
        if failure_log.startswith("LINTER_FAIL:"):
            black = _which("black")
            if black:
                logging.info("[Ghost] Wende black-Formatierung an.")
                subprocess.run([black, "."], cwd=self.repo_path, capture_output=True)
            ok, log = self.run_pre_commit_audit()
            if ok:
                logging.info("[Ghost] Formatierung erfolgreich repariert.")
                return True
            failure_log = log  # weiter mit verbleibenden Fehlern

        # Schritt 2: Logische Testfehler → LLM-Fix-Loop (max. 3×)
        for attempt in range(1, self.MAX_FIX_ATTEMPTS + 1):
            logging.info("[Ghost] LLM-Fix-Versuch %d/%d", attempt, self.MAX_FIX_ATTEMPTS)
            if not self._llm_fix(failure_log):
                logging.warning("[Ghost] LLM-Fix konnte nicht ausgeführt werden.")
                break
            ok, new_log = self.run_pre_commit_audit()
            if ok:
                logging.info("[Ghost] Tests grün nach Versuch %d.", attempt)
                return True
            failure_log = new_log

        # Schritt 3: Alle Versuche erschöpft → Rollback
        logging.error("[Ghost] Reparatur nach %d Versuchen fehlgeschlagen. Git-Rollback.", self.MAX_FIX_ATTEMPTS)
        self._git_rollback()
        return False

    # --- Datei-Watcher ------------------------------------------------------

    def start_watcher(self):
        """Startet Hintergrund-Thread, der .py-Änderungen überwacht."""
        if self._watcher and self._watcher.is_alive():
            logging.info("[Ghost] Watcher läuft bereits.")
            return
        self._stop.clear()
        self._watcher = threading.Thread(
            target=self._watch_loop, daemon=True, name="GhostWatcher"
        )
        self._watcher.start()
        logging.info("[Ghost] Datei-Watcher gestartet (repo=%s, poll=%.0fs).",
                     self.repo_path, self.POLL_INTERVAL_SECONDS)

    def stop_watcher(self):
        self._stop.set()
        logging.info("[Ghost] Watcher wird gestoppt.")

    def is_watching(self) -> bool:
        return bool(self._watcher and self._watcher.is_alive())

    def _watch_loop(self):
        mtimes: dict = {}
        while not self._stop.is_set():
            changed = False
            for fp in glob.glob(os.path.join(self.repo_path, "**", "*.py"), recursive=True):
                if "__pycache__" in fp:
                    continue
                try:
                    mt = os.path.getmtime(fp)
                except OSError:
                    continue
                if fp not in mtimes:
                    mtimes[fp] = mt
                elif mtimes[fp] != mt:
                    mtimes[fp] = mt
                    changed = True
                    logging.info("[Ghost] Änderung erkannt: %s", os.path.relpath(fp, self.repo_path))

            if changed:
                logging.info("[Ghost] Starte Audit nach Dateiänderung.")
                ok, log = self.run_pre_commit_audit()
                if not ok:
                    logging.warning("[Ghost] Audit fehlgeschlagen — starte autonome Reparatur.")
                    self.autonomous_repair(log)

            self._stop.wait(self.POLL_INTERVAL_SECONDS)

    # --- LLM-Fix internals --------------------------------------------------

    def _llm_fix(self, failure_log: str) -> bool:
        if not self._client:
            logging.warning("[Ghost] Kein SonuClient verfügbar — LLM-Fix übersprungen.")
            return False

        target_file, line_no, error_msg = _parse_traceback(failure_log)

        if target_file:
            abs_path = os.path.join(self.repo_path, target_file)
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                content = "(Datei nicht lesbar)"

            prompt = (
                f"GHOST_INTEGRATOR_FIX:\n"
                f"Datei: {target_file} (Zeile ~{line_no})\n"
                f"Fehler: {error_msg}\n\n"
                f"Dateiinhalt:\n```python\n{content[:3000]}\n```\n\n"
                "Korrigiere den Fehler chirurgisch mit edit_file. "
                "Minimaler Eingriff, keine anderen Änderungen."
            )
        else:
            prompt = (
                f"GHOST_INTEGRATOR_FIX:\n"
                f"Testfehler:\n{failure_log[:1500]}\n\n"
                "Analysiere und korrigiere chirurgisch. Minimaler Eingriff."
            )

        try:
            self._client.run_agent_turn(prompt, _HeadlessUI())
            return True
        except Exception as exc:
            logging.error("[Ghost] LLM-Aufruf fehlgeschlagen: %s", exc)
            return False

    def _git_rollback(self):
        try:
            res = subprocess.run(
                ["git", "checkout", "--", "."],
                cwd=self.repo_path, capture_output=True, text=True
            )
            if res.returncode == 0:
                logging.warning("[Ghost] Git-Rollback erfolgreich ausgeführt.")
            else:
                logging.error("[Ghost] Git-Rollback fehlgeschlagen: %s", res.stderr)
        except Exception as exc:
            logging.error("[Ghost] Git-Rollback-Exception: %s", exc)


# --- Hilfsfunktionen --------------------------------------------------------

def _parse_traceback(log: str) -> Tuple[Optional[str], int, str]:
    """Extrahiert (Dateipfad, Zeile, Fehlermeldung) aus pytest-Kurzausgabe."""
    # Suche: "path/to/file.py:42" oder "FAILED path/to/file.py::test_name"
    m = re.search(r'([\w/\\.\-]+\.py)[:\s](\d+)', log)
    if m:
        path = m.group(1).replace("\\", "/")
        line = int(m.group(2))
        err_m = re.search(
            r'(AssertionError|TypeError|ValueError|AttributeError|NameError|SyntaxError|Exception)[^\n]*',
            log,
        )
        error = err_m.group(0) if err_m else log[-500:]
        return path, line, error
    return None, 0, log[-1000:]


def _which(name: str) -> Optional[str]:
    import shutil
    return shutil.which(name)
