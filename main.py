import sys

# UTF-8 erzwingen, damit Emojis/Unicode auch bei Umleitung (>) nicht crashen.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from prompt_toolkit import prompt
from sonu_client import SonuClient
from storage import StorageManager
from terminal_ui import TerminalUI

def main():
    ui = TerminalUI()
    ui.show_welcome()

    # YOLO-Mode via Startargument: .\sonu.bat --yolo  (oder -y)
    if any(arg in ("--yolo", "-y") for arg in sys.argv[1:]):
        ui.set_yolo(True)

    try:
        # Standardmodell
        client = SonuClient(model_name="gemini-3.5-flash")
        ui.show_info(f"Sonu Client erfolgreich geladen. Aktives Modell: [bold cyan]{client.model_name}[/bold cyan]")
    except Exception as e:
        ui.show_error(f"Fehler bei der Initialisierung: {str(e)}")
        sys.exit(1)

    storage = StorageManager()

    while True:
        try:
            # Eingabe über prompt_toolkit
            user_input = prompt("\nDu: ")
            
            # Entferne führende/folgende Leerzeichen
            cmd = user_input.strip()
            
            if not cmd:
                continue

            # Überprüfung auf Slash-Befehle oder klassische Exit-Befehle
            if cmd.lower() in ["exit", "quit", "beenden", "/exit"]:
                print("Auf Wiedersehen!")
                break
                
            elif cmd == "/help":
                ui.show_help()
                continue
                
            elif cmd == "/models":
                with ui.show_spinner("Lade verfügbare Modelle..."):
                    try:
                        models = client.list_available_models()
                    except Exception as e:
                        ui.show_error(str(e))
                        continue
                print("\nVerfügbare Sonu Modelle:")
                for m in models:
                    print(f"  • {m}")
                print()
                continue
                
            elif cmd.startswith("/model"):
                parts = cmd.split(maxsplit=1)
                if len(parts) == 1:
                    ui.show_info(f"Aktives Modell: [bold cyan]{client.model_name}[/bold cyan]")
                else:
                    new_model = parts[1].strip()
                    with ui.show_spinner(f"Wechsle zu Modell '{new_model}'..."):
                        try:
                            client.set_model(new_model)
                            ui.show_info(f"Erfolgreich zu Modell [bold cyan]{new_model}[/bold cyan] gewechselt!")
                        except Exception as e:
                            ui.show_error(f"Modellwechsel fehlgeschlagen: {str(e)}")
                continue
                
            elif cmd == "/history":
                path = storage.get_log_path()
                count = storage.interaction_count
                ui.show_info(
                    f"Log-Datei: [cyan]{path}[/cyan]\n"
                    f"  Anzahl bisheriger Interaktionen in dieser Session: [bold green]{count}[/bold green]"
                )
                continue

            elif cmd == "/tools":
                ui.show_tools()
                continue

            elif cmd == "/yolo":
                ui.set_yolo(not ui.yolo)
                continue

            # Agentischer Turn: das Modell darf selbststaendig Werkzeuge nutzen.
            # (Kein Spinner-Wrap: Bestaetigungs-Prompts wuerden mit der Live-Anzeige kollidieren.)
            response = client.run_agent_turn(cmd, ui)

            # Finale Antwort als Markdown rendern.
            if response:
                ui.display_response(response)

            # Logge die Interaktion
            storage.log_interaction(cmd, response or "(keine Textantwort)")

        except KeyboardInterrupt:
            # Erlaubt dem Benutzer, mit Ctrl+C eine angefangene Eingabe abzubrechen
            print("\nEingabe abgebrochen.")
            continue
        except EOFError:
            # Erlaubt das Beenden mit Ctrl+D
            print("\nAuf Wiedersehen!")
            break
        except Exception as e:
            ui.show_error(f"Ein Fehler ist aufgetreten: {str(e)}")

if __name__ == "__main__":
    main()
