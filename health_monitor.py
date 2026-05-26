import threading
import time
import logging
import gc
import psutil
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
        if len(self.telemetry_history) > 100:
            self.telemetry_history.pop(0)

        if data.ram_bytes > 419430400: # 400 MB
            self._trigger_stabilization("RAM_OVERFLOW", data)

    def _tail_application_logs(self) -> None:
        pass

    def _trigger_stabilization(self, trigger_reason: str, data: SensorData) -> None:
        logging.warning(f"[HealthMonitor] Kritischer Systemzustand detektiert: {trigger_reason}. Leite Stabilisierung ein.")
        if trigger_reason == "RAM_OVERFLOW":
            gc.collect()
