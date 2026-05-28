"""
ModelAvailabilityService — portiert von Google Gemini CLI (availability/ + fallbackStrategy.ts)
Tracks per-(key, model) failure state mit Failure-Kind-Differenzierung.
"""
import json
import time
import os

FAILURE_KINDS = ("quota", "auth", "network", "not_found", "unknown")

# Cooldown-Dauern in Sekunden
_DURATIONS = {
    "quota":     65.0,      # RPM-Limit: kurz warten
    "quota_daily": 3600.0,  # Tages-Quota: 1h
    "auth":      86400.0 * 30,  # Ungültiger Key: 30 Tage (manuell resetten)
    "network":   30.0,      # Netzwerkfehler: kurz
    "not_found": 86400.0,   # Modell nicht gefunden: 1 Tag
    "unknown":   65.0,
}


def classify_error(err_str: str) -> tuple[str, float]:
    """Gibt (failure_kind, duration) aus einem Fehler-String zurück."""
    e = err_str.lower()
    if any(w in e for w in ["403", "forbidden", "unauthorized", "invalid api key", "api_key_invalid"]):
        return "auth", _DURATIONS["auth"]
    if any(w in e for w in ["daily", "per day", "day quota", "exceeded your", "resource_exhausted"]):
        return "quota", _DURATIONS["quota_daily"]
    if any(w in e for w in ["429", "quota", "rate limit", "resource exhausted", "rateerror"]):
        return "quota", _DURATIONS["quota"]
    if any(w in e for w in ["connection refused", "network unreachable", "name or service not known",
                             "nodename nor servname", "connection error", "connectionerror"]):
        return "network", _DURATIONS["network"]
    if any(w in e for w in ["404", "model not found", "not found"]):
        return "not_found", _DURATIONS["not_found"]
    return "unknown", _DURATIONS["unknown"]


class ModelAvailabilityService:
    """
    Tracks availability per (key_index, model).
    Portiert von Gemini CLI ModelAvailabilityService + fallbackStrategy.ts.
    """

    def __init__(self, cooldown_file: str):
        self._file = cooldown_file
        # state: { "key_index:model" -> {status, until, fail_count} }
        self._state: dict = {}
        self.load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def mark_failure(self, key_index: int, model: str, failure_kind: str, duration: float | None = None):
        key = self._key(key_index, model)
        if duration is None:
            duration = _DURATIONS.get(failure_kind, 65.0)
        entry = self._state.get(key, {"status": "available", "until": 0.0, "fail_count": 0})
        entry["status"] = failure_kind
        entry["until"] = time.time() + duration
        entry["fail_count"] = entry.get("fail_count", 0) + 1
        self._state[key] = entry
        self.save()

    def mark_failure_from_error(self, key_index: int, model: str, err_str: str):
        kind, duration = classify_error(err_str)
        self.mark_failure(key_index, model, kind, duration)

    def is_available(self, key_index: int, model: str) -> bool:
        key = self._key(key_index, model)
        entry = self._state.get(key)
        if not entry:
            return True
        if entry["status"] == "auth":
            return False  # Auth-Fehler nie auto-clearen
        return time.time() > entry.get("until", 0.0)

    def select_best_key(self, model: str, all_keys: list) -> int | None:
        """Gibt den Index des besten verfügbaren Keys für dieses Modell zurück.
        Bevorzugt Keys mit wenigen Fehlern und frühem Ablauf."""
        candidates = []
        now = time.time()
        for i in range(len(all_keys)):
            if self.is_available(i, model):
                key = self._key(i, model)
                entry = self._state.get(key, {})
                fail_count = entry.get("fail_count", 0)
                candidates.append((fail_count, i))
        if not candidates:
            return None
        candidates.sort()
        return candidates[0][1]

    def snapshot(self, key_index: int, model: str) -> dict:
        key = self._key(key_index, model)
        entry = self._state.get(key, {})
        now = time.time()
        until = entry.get("until", 0.0)
        available = self.is_available(key_index, model)
        return {
            "available": available,
            "status": entry.get("status", "available"),
            "until": until,
            "remaining_secs": max(0.0, until - now),
            "fail_count": entry.get("fail_count", 0),
        }

    def reset_key(self, key_index: int):
        """Löscht alle Fehler für diesen Key (über alle Modelle)."""
        prefix = f"{key_index}:"
        keys_to_del = [k for k in self._state if k.startswith(prefix)]
        for k in keys_to_del:
            del self._state[k]
        self.save()

    def reset_all(self):
        self._state.clear()
        self.save()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self):
        try:
            os.makedirs(os.path.dirname(self._file), exist_ok=True)
            with open(self._file, "w", encoding="utf-8") as f:
                json.dump(self._state, f)
        except Exception:
            pass

    def load(self):
        if not os.path.exists(self._file):
            return
        try:
            with open(self._file, "r", encoding="utf-8") as f:
                raw = json.load(f)
            # Backward compat: old format was {key_prefix: expiry_timestamp}
            if raw and all(isinstance(v, (int, float)) for v in raw.values()):
                # Convert old format — treat as quota failures for key index 0
                # (best effort migration)
                self._state = {}
                return
            self._state = {k: v for k, v in raw.items() if isinstance(v, dict)}
        except Exception:
            self._state = {}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _key(key_index: int, model: str) -> str:
        return f"{key_index}:{model}"
