import gc
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional

try:
    import psutil
    _PSUTIL_OK = True
except ImportError:
    _PSUTIL_OK = False


@dataclass
class SensorData:
    timestamp: float
    cpu_percent: float
    ram_bytes: int
    active_threads: int


class HealthMonitor(threading.Thread):
    RAM_LIMIT_BYTES = 400 * 1024 * 1024  # 400 MB
    COOLDOWN_SECONDS = 180
    MAX_HISTORY = 100
    _LOG_PATTERNS = [
        re.compile(r, re.IGNORECASE)
        for r in [
            r"MemoryError",
            r"ResourceWarning",
            r"Exception in thread",
            r"Traceback \(most recent call last\)",
            r"\bCRITICAL:\b",
            r" - CRITICAL - ",
        ]
    ]

    def __init__(
        self,
        sample_interval: float = 2.0,
        log_path: Optional[str] = None,
        process_manager=None,
        memory_manager=None,
    ):
        super().__init__(daemon=True, name="SonuHealthMonitor")
        self.sample_interval = sample_interval
        self._stop = threading.Event()
        self.telemetry_history: List[SensorData] = []
        self._last_stabilization: float = 0.0
        self.log_path = log_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "sonu_log.md"
        )
        self.process_manager = process_manager
        self.memory_manager = memory_manager

    def stop(self):
        self._stop.set()

    def run(self):
        if not _PSUTIL_OK:
            logging.warning("[HealthMonitor] psutil nicht installiert — nur Log-Überwachung aktiv.")
        logging.info("[HealthMonitor] Gestartet. Interval=%.1fs RAM-Limit=%dMB",
                     self.sample_interval, self.RAM_LIMIT_BYTES // 1024 // 1024)
        while not self._stop.is_set():
            try:
                data = self._sample()
                if data:
                    self._evaluate(data)
                self._scan_logs()
            except Exception as exc:
                logging.error("[HealthMonitor] Sampling-Fehler: %s", exc)
            self._stop.wait(self.sample_interval)

    # --- Sampling -----------------------------------------------------------

    def _sample(self) -> Optional[SensorData]:
        if not _PSUTIL_OK:
            return None
        try:
            proc = psutil.Process()
            return SensorData(
                timestamp=time.time(),
                cpu_percent=proc.cpu_percent(interval=None),
                ram_bytes=proc.memory_info().rss,
                active_threads=threading.active_count(),
            )
        except Exception as exc:
            logging.debug("[HealthMonitor] psutil-Fehler: %s", exc)
            return None

    # --- Auswertung ---------------------------------------------------------

    def _evaluate(self, data: SensorData):
        self.telemetry_history.append(data)
        if len(self.telemetry_history) > self.MAX_HISTORY:
            self.telemetry_history.pop(0)
        if data.ram_bytes > self.RAM_LIMIT_BYTES:
            self._stabilize("RAM_OVERFLOW", data)

    def _stabilize(self, reason: str, data: SensorData):
        now = time.time()
        if now - self._last_stabilization < self.COOLDOWN_SECONDS:
            return  # Cooldown aktiv

        ram_mb = data.ram_bytes // 1024 // 1024
        logging.warning("[HealthMonitor] Kritisch: %s — RAM=%dMB. Starte Closed-Loop-Stabilisierung.", reason, ram_mb)

        if reason == "RAM_OVERFLOW":
            collected = gc.collect()
            logging.info("[HealthMonitor] gc.collect() -> %d Objekte freigegeben.", collected)

            after = self._sample()
            if after and after.ram_bytes > self.RAM_LIMIT_BYTES:
                logging.warning("[HealthMonitor] RAM immer noch >400MB nach GC. Beende ältesten Hintergrundtask.")
                self._kill_oldest_task()

        self._last_stabilization = now

    def _kill_oldest_task(self):
        if not self.process_manager:
            logging.warning("[HealthMonitor] Kein ProcessManager — kann Task nicht beenden.")
            return
        try:
            tasks = self.process_manager.list_tasks()
            running = [t for t in tasks if "Running" in str(t.get("status", ""))]
            if not running:
                logging.info("[HealthMonitor] Keine laufenden Tasks gefunden.")
                return
            target = running[0]
            self.process_manager.kill_task(target["id"])
            logging.warning("[HealthMonitor] Task %d ('%s...') beendet.", target["id"], target["command"][:50])
        except Exception as exc:
            logging.error("[HealthMonitor] Task-Kill fehlgeschlagen: %s", exc)

    # --- Log-Scan -----------------------------------------------------------

    def _scan_logs(self):
        if not os.path.exists(self.log_path):
            return
        try:
            sz = os.path.getsize(self.log_path)
            read_sz = min(sz, 4096)
            with open(self.log_path, "rb") as f:
                if sz > 4096:
                    f.seek(sz - 4096)
                content_bytes = f.read()
            content = content_bytes.decode("utf-8", errors="replace")
            lines = content.splitlines()
            for line in lines[-20:]:
                if "HealthMonitor" in line:
                    continue
                for pat in self._LOG_PATTERNS:
                    if pat.search(line):
                        logging.warning("[HealthMonitor] Fehlermuster in Log: %s", line.rstrip())
                        break
        except Exception as exc:
            logging.debug("[HealthMonitor] Log-Lese-Fehler: %s", exc)

    # --- Statusabfrage ------------------------------------------------------

    def latest(self) -> Optional[SensorData]:
        return self.telemetry_history[-1] if self.telemetry_history else None

    def status_line(self) -> str:
        d = self.latest()
        if not d:
            return "HealthMonitor: keine Daten (psutil fehlt?)"
        age = time.time() - d.timestamp
        ram_mb = d.ram_bytes // 1024 // 1024
        limit_mb = self.RAM_LIMIT_BYTES // 1024 // 1024
        bar = "OK" if d.ram_bytes <= self.RAM_LIMIT_BYTES else "KRITISCH"
        return (
            f"HealthMonitor | CPU: {d.cpu_percent:.1f}% | "
            f"RAM: {ram_mb}MB/{limit_mb}MB [{bar}] | "
            f"Threads: {d.active_threads} | Messung vor {age:.0f}s"
        )
