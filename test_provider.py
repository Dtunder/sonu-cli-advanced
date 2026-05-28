import os
import sys

# Wir mocken den key, damit das script durchläuft auch wenn der key ungueltig ist
os.environ["GROQ_API_KEY"] = "gsk_dummy_key_for_testing_123"

from sonu_client import SonuClient
from terminal_ui import TerminalUI

ui = TerminalUI()
ui.set_yolo(True)
client = SonuClient()

print("Wechsle Provider...")
ok, msg = client.set_provider("groq")
print(f"Result: {ok}, {msg}")

if ok:
    print("\nTeste run_agent_turn (Erwartet Fehler falls Key falsch, aber wir sehen ob der flow an sich passt)...")
    try:
        response = client.run_agent_turn("Liste die Dateien hier auf", ui, max_steps=3)
        print(f"Antwort: {response}")
    except Exception as e:
        print(f"Fehler: {e}")
