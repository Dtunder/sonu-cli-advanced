import threading
import time
import logging
import gc
import psutil
from typing import List

logger = logging.getLogger(__name__)


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
        # Fallback thresholds
        self.memory_limit = 419430400  # 400 MB

    def run(self) -> None:
        self.is_running = True
        logger.info("[HealthMonitor] Gestartet.")
        while self.is_running:
            try:
                data = self._sample_system_state()
                self._evaluate_state(data)
            except Exception as e:
                logger.error(f"[HealthMonitor] Fehler bei Zustandsmessung: {e}")
            time.sleep(self.sample_interval)

    def _sample_system_state(self) -> SensorData:
        process = psutil.Process()
        return SensorData(
            cpu_percent=process.cpu_percent(),
            ram_bytes=process.memory_info().rss,
            active_threads=threading.active_count(),
        )

    def _evaluate_state(self, data: SensorData) -> None:
        self.telemetry_history.append(data)
        # Behalte nur die letzten 100 Messungen (Gedächtnishorizont)
        if len(self.telemetry_history) > 100:
            self.telemetry_history.pop(0)

        # Stellglied-Trigger bei RAM-Anomalien (> 400 MB)
        if data.ram_bytes > self.memory_limit:
            self._trigger_stabilization("RAM_OVERFLOW", data)

    def _trigger_stabilization(self, trigger_reason: str, data: SensorData) -> None:
        logger.warning(
            f"[HealthMonitor] Kritischer Systemzustand detektiert: {trigger_reason}. Leite Stabilisierung ein. (RAM: {data.ram_bytes/1024/1024:.2f} MB)"
        )
        if trigger_reason == "RAM_OVERFLOW":
            gc.collect()

    def stop(self):
        self.is_running = False
