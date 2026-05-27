import os
from sonu_client import SonuClient
from terminal_ui import TerminalUI
import tools

ui = TerminalUI()
ui.set_yolo(True)
client = SonuClient()

# Ensure we use an available provider like openrouter
ok, msg = client.set_provider("openrouter")
print(msg)

if ok:
    print("\n--- TEST: Headless Sub-Agent Delegation ---")
    print("Delegiere Aufgabe an Sub-Agenten: 'Was sind die Hauptverantwortlichkeiten der SonuClient Klasse?'")
    result = tools.delegate_to_subagent("Was sind die Hauptverantwortlichkeiten der SonuClient Klasse? Finde die Datei sonu_client.py und lies sie.", "openrouter")
    print("\n--- ERGEBNIS VOM SUB-AGENTEN ---")
    print(result)
