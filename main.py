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

            elif cmd.startswith("/provider"):
                parts = cmd.split(maxsplit=1)
                import providers
                if len(parts) == 1:
                    ui.show_info(f"Aktiver Provider: [bold cyan]{client.provider}[/bold cyan]")
                    print("\nVerfügbare Provider:")
                    for p in providers.list_providers():
                        prov_info = providers.get_provider(p)
                        print(f"  • {p} ({prov_info['label']})")
                    print()
                else:
                    new_prov = parts[1].strip()
                    with ui.show_spinner(f"Wechsle zu Provider '{new_prov}'..."):
                        ok, msg = client.set_provider(new_prov)
                        if ok:
                            ui.show_info(msg)
                        else:
                            ui.show_error(msg)
                continue

            elif cmd == "/tools":
                ui.show_tools()
                continue

            elif cmd == "/yolo":
                ui.set_yolo(not ui.yolo)
                continue

            elif cmd == "/skills":
                skills = client.skills_mgr.list_skills()
                active = client.skills_mgr.active_skill
                print("\nVerfügbare Experten-Skills:")
                for s in skills:
                    marker = "[bold green](AKTIV)[/bold green]" if s == active else ""
                    print(f"  • {s} {marker}")
                print()
                continue
                
            elif cmd.startswith("/activate"):
                parts = cmd.split(maxsplit=1)
                if len(parts) == 1:
                    ui.show_error("Bitte gib den Namen des Skills an, z.B. `/activate cybernetic-thinking`")
                else:
                    skill_name = parts[1].strip()
                    try:
                        client.skills_mgr.activate_skill(skill_name)
                        client.reset_chat()
                        ui.show_info(f"Experten-Skill [bold yellow]{skill_name}[/bold yellow] erfolgreich aktiviert!")
                    except Exception as e:
                        ui.show_error(str(e))
                continue
                
            elif cmd == "/deactivate":
                client.skills_mgr.deactivate_skill()
                client.reset_chat()
                ui.show_info("Experten-Skill deaktiviert. Baseline-Prompt wiederhergestellt.")
                continue

            elif cmd == "/memory":
                import os as _os
                mem = client.memory_mgr.load_memory(_os.getcwd())
                if mem.strip():
                    print("\n--- Aktives 4-Ebenen-Gedächtnis ---\n")
                    print(mem)
                    print("-" * 40 + "\n")
                else:
                    ui.show_info("Kein SONU.md-Gedächtnis gefunden.")
                continue

            elif cmd == "/tasks" or cmd == "/bg":
                tasks = client.process_mgr.list_tasks()
                if not tasks:
                    ui.show_info("Keine aktiven Hintergrundprozesse.")
                else:
                    print("\nAktive Hintergrundprozesse:")
                    for t in tasks:
                        print(f"  [{t['id']}] {t['command']} - Status: {t['status']} (Laufzeit: {t['elapsed']})")
                    print()
                continue

            elif cmd.startswith("/bg output"):
                parts = cmd.split()
                if len(parts) < 3:
                    ui.show_error("Bitte gib die Task-ID an, z.B. `/bg output 1`")
                else:
                    try:
                        tid = int(parts[2].strip())
                        output = client.process_mgr.read_task_output(tid)
                        print(f"\n--- Output für Task-ID {tid} ---")
                        print(output)
                        print("-" * 30 + "\n")
                    except ValueError:
                        ui.show_error("Ungültige Task-ID.")
                    except Exception as e:
                        ui.show_error(str(e))
                continue

            elif cmd.startswith("/bg kill"):
                parts = cmd.split()
                if len(parts) < 3:
                    ui.show_error("Bitte gib die Task-ID an, z.B. `/bg kill 1`")
                else:
                    try:
                        tid = int(parts[2].strip())
                        client.process_mgr.kill_task(tid)
                        ui.show_info(f"Task-ID {tid} wurde erfolgreich beendet.")
                    except ValueError:
                        ui.show_error("Ungültige Task-ID.")
                    except Exception as e:
                        ui.show_error(str(e))
                continue

            elif cmd.startswith("/debate"):
                parts = cmd.split(maxsplit=1)
                if len(parts) == 1:
                    ui.show_error("Bitte gib ein Thema an, z.B. `/debate Wie sollten wir Caching implementieren?`")
                else:
                    topic = parts[1].strip()
                    try:
                        from debate_engine import GroupDebateEngine
                        engine = GroupDebateEngine(client, ui)
                        with ui.show_spinner("Starte Gruppen-Debatte..."):
                            result = engine.run_debate(topic)
                        print(f"\n--- Bestes Proposal ({result['best_provider']}) ---")
                        print(result['best_proposal'])
                    except Exception as e:
                        ui.show_error(f"Fehler bei der Debatte: {str(e)}")
                continue

            elif cmd.startswith("/delegate"):
                parts = cmd.split(maxsplit=1)
                if len(parts) == 1:
                    ui.show_error("Bitte gib die Aufgabe an, z.B. `/delegate Refactor active_client.py`")
                else:
                    import os
                    prompt_text = parts[1].strip()
                    with ui.show_spinner("Initialisiere Google Jules im Hintergrund..."):
                        try:
                            script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jules_delegator.py")
                            jcmd = f"python \"{script_path}\" \"{prompt_text}\""
                            tid = client.process_mgr.start_task(jcmd)
                            ui.show_info(
                                f"Google Jules erfolgreich im Hintergrund delegiert (Task-ID [bold yellow]{tid}[/bold yellow]).\n"
                                f"Nutze `/bg output {tid}`, um den Live-Status zu überwachen."
                            )
                        except Exception as e:
                            ui.show_error(f"Fehler bei der Jules-Delegierung: {str(e)}")
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
