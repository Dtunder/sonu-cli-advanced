# Sonu CLI Project-Wide Memory

## 1. Architektur-Regeln
- Sonu CLI Advanced ist ein modularer, asynchroner CLI-Agent.
- Alle blockierenden Befehle werden ueber den `ProcessManager` in den Hintergrund ausgelagert.
- API-Keys werden transparent bei 429-Fehlern rotiert.
- Dynamisches Skill-System ermoeglicht on-the-fly Expertenprofile.
