import logging

class RedundancyManager:
    """Sorgt fuer Ausfallsicherheit durch dynamische Provider-Fallbacks."""
    def __init__(self, client):
        self.client = client
        self.logger = logging.getLogger("RedundancyManager")
        self.fallback_history = []

    def execute_with_fallback(self, fn, providers_list: list):
        """Führt eine übergebene Funktion fn aus. Fängt Exceptions ab,
        wechselt zum nächsten Provider in der Liste und versucht es erneut.
        """
        last_exception = None
        for provider in providers_list:
            try:
                self.logger.info(f"[RedundancyManager] Versuche Ausfuehrung mit Provider: {provider}")
                # Wechsle den Provider am Client
                ok, msg = self.client.set_provider(provider)
                if not ok:
                    self.logger.warning(f"[RedundancyManager] Konnte Provider {provider} nicht setzen: {msg}")
                    continue

                # Führe die Funktion aus
                result = fn()

                # Logge den Erfolg
                self.fallback_history.append({
                    "provider": provider,
                    "status": "success",
                    "error": None
                })
                return result
            except Exception as e:
                self.logger.error(f"[RedundancyManager] Fehler bei Provider {provider}: {e}")
                last_exception = e
                self.fallback_history.append({
                    "provider": provider,
                    "status": "fail",
                    "error": str(e)
                })
                continue

        raise Exception(f"Alle versuchten Provider {providers_list} sind fehlgeschlagen! Letzter Fehler: {last_exception}")

    def get_status(self):
        """Gibt den aktuellen Fallback-Status und Verlauf zurück."""
        return {
            "current_provider": self.client.provider,
            "history": self.fallback_history
        }
