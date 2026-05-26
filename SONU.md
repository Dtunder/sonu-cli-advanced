# Sonu CLI Project-Wide Memory

## 1. Architektur-Regeln
- Sonu CLI Advanced ist ein modularer, asynchroner CLI-Agent.
- Alle blockierenden Befehle werden ueber den `ProcessManager` in den Hintergrund ausgelagert.
- API-Keys werden transparent bei 429-Fehlern rotiert (vollstaendig lautlos).
- Silent Failover und exponential Backoff (2s, 4s, 8s) bei 503 und 429 API-Fehlern ueber alle Provider hinweg.
- Der Nutzer sieht keine API-Fehler oder Tracebacks im Terminal während dieser Ereignisse.
- Dynamisches Skill-System ermoeglicht on-the-fly Expertenprofile.
