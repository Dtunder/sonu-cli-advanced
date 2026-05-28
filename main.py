import sys
import time
import logging
from difflib import get_close_matches
from rich import box

# UTF-8 erzwingen, damit Emojis/Unicode auch bei Umleitung (>) nicht crashen.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Root-Logger auf WARNING setzen, um Konsolen-Spam von HealthMonitor/HTTPX zu unterdrücken
logging.basicConfig(level=logging.WARNING, force=True)
# Verbose HTTP- und API-Logs von Drittanbieter-Bibliotheken unterdrücken
for logger_name in ("httpx", "httpcore", "urllib3", "google", "openai"):
    logging.getLogger(logger_name).setLevel(logging.WARNING)

from terminal_ui import TerminalUI

def save_session_to_sonu_md(session_turns):
    if not session_turns:
        return
    import os
    import datetime
    try:
        topic = session_turns[0].get("user", "Interactive Session")[:60]
        turns_count = len(session_turns)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        note = f"\n\n## Session Updates — {timestamp}\n- **Primary Topic:** {topic}\n- **Turns:** {turns_count}\n- **Status:** Completed cleanly\n"

        if os.path.exists("SONU.md"):
            with open("SONU.md", "a", encoding="utf-8") as f:
                f.write(note)
    except Exception:
        pass

ui = None

COMMAND_ALIASES = {
    "/?": "/help",
    "/h": "/help",
    "/q": "/exit",
    "/quit": "/exit",
    "/bye": "/exit",
    "/cls": "/clear",
}

KNOWN_SLASH_COMMANDS = [
    "/help",
    "/docs",
    "/models",
    "/model",
    "/history",
    "/provider",
    "/tools",
    "/yolo",
    "/skills",
    "/activate",
    "/deactivate",
    "/memory",
    "/tasks",
    "/bg",
    "/debate",
    "/delegate",
    "/selfimprove",
    "/health",
    "/keys",
    "/rotator",
    "/predict",
    "/redundancy",
    "/ghost",
    "/distill",
    "/generate-problems",
    "/batch",
    "/loop",
    "/watchdog",
    "/map",
    "/recall",
    "/refactor",
    "/style",
    "/jules-batch",
    "/swarm",
    "/cost",
    "/checkpoint",
    "/status",
    "/router",
    "/clear",
    "/exit",
]


def normalize_command(raw_input: str) -> str:
    cmd = raw_input.strip()
    if not cmd:
        return cmd

    head, sep, tail = cmd.partition(" ")
    alias = COMMAND_ALIASES.get(head.lower())
    if alias:
        return f"{alias}{sep}{tail}" if sep else alias
    return cmd


def suggest_command(cmd: str):
    slash_name = cmd.split()[0].lower()
    return get_close_matches(slash_name, KNOWN_SLASH_COMMANDS, n=3, cutoff=0.55)

def main():
    global ui
    ui = TerminalUI()
    from sonu_client import SonuClient, QuotaExhaustedException

    # --- DOCTOR MODE ---
    if any(arg in ("--doctor", "-d") for arg in sys.argv):
        ui.show_info("[bold blue]Sonu CLI Diagnostic Tool (Doctor Mode)[/bold blue]")
        import os
        import subprocess
        from rich.table import Table

        table = Table(title="System Health Check")
        table.add_column("Component", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Details", style="magenta")

        # 1. Python Check
        v = sys.version_info
        table.add_row("Python Version", "[green]✓[/green]", f"{v.major}.{v.minor}.{v.micro}")

        # 2. Imports Check
        imports = ["google.genai", "prompt_toolkit", "dotenv", "rich", "openai"]
        missing = []
        for imp in imports:
            try:
                __import__(imp)
            except ImportError:
                missing.append(imp)

        if not missing:
            table.add_row("Crucial Imports", "[green]✓[/green]", "All present")
        else:
            table.add_row("Crucial Imports", "[red]✗[/red]", f"Missing: {', '.join(missing)}")

        # 3. Env File Check
        env_exists = os.path.exists(".env")
        if env_exists:
            from dotenv import dotenv_values
            env_vars = dotenv_values(".env")
            has_key = "GEMINI_API_KEY" in env_vars or "GEMINI_KEY_POOL" in env_vars
            table.add_row(".env File", "[green]✓[/green]", "Found & accessible")
            table.add_row("Gemini Keys", "[green]✓[/green]" if has_key else "[red]✗[/red]", "Keys present" if has_key else "No keys found")
        else:
            table.add_row(".env File", "[red]✗[/red]", "File missing")

        # 4. Git Check
        try:
            subprocess.run(["git", "--version"], capture_output=True, check=True)
            table.add_row("Git Repository", "[green]✓[/green]", "Git installed")
        except Exception:
            table.add_row("Git Repository", "[red]✗[/red]", "Git missing")

        ui.console.print(table)

        # 5. Client Test
        try:
            with ui.show_spinner("Testing genai.Client initialization..."):
                c = SonuClient()
                if c.client:
                    ui.show_info("[bold green]✓ Client initialized successfully.[/bold green]")
                else:
                    ui.show_info("[bold yellow]! Client initialized without Gemini key.[/bold yellow]")
        except Exception as e:
            ui.show_error(f"Client test failed: {e}")
            sys.exit(1)

        sys.exit(0)

    # Instanz-ID via Startargument: --instance 3 (oder -i 3 / --instance-id 3)
    instance_id = None
    for i, arg in enumerate(sys.argv):
        if arg in ("--instance", "-i", "--instance-id") and i + 1 < len(sys.argv):
            instance_id = sys.argv[i + 1]
            import os
            os.environ["SONU_INSTANCE_ID"] = instance_id
            break

    # Headless Task-Mode via Startargument: --task "aufgabe" (oder -t/-p/--prompt "aufgabe")
    task_description = None
    for i, arg in enumerate(sys.argv):
        if arg in ("--task", "-t", "-p", "--prompt") and i + 1 < len(sys.argv):
            task_description = sys.argv[i + 1]
            break

    if not task_description:
        ui.show_welcome()

    # YOLO-Mode via Startargument: .\sonu.bat --yolo  (oder -y)
    if task_description or any(arg in ("--yolo", "-y") for arg in sys.argv[1:]):
        ui.set_yolo(True)

    # Harness init (layered settings + permissions + hooks)
    try:
        import harness as _harness
        import os as _os
        _harness.init(base_dir=_os.getcwd())
        # Apply harness settings to UI if yolo is set in settings
        if _harness.settings().get("yolo"):
            ui.set_yolo(True)
        # Start scheduler daemon
        from harness.scheduler import start_daemon as _start_sched
        _start_sched()
    except Exception as _he:
        pass  # harness failure must never block startup

    try:
        # Standardmodell
        client = SonuClient()
        if not task_description:
            pool = client.key_pool
            healthy = sum(1 for i in range(pool.count()) if pool.is_available(i))
            ui.console.print(f"[dim]{client.model_name}  ·  {healthy}/{pool.count()} keys[/dim]")
            ui.console.print()
    except Exception as e:
        ui.show_error(f"Fehler bei der Initialisierung: {str(e)}")
        sys.exit(1)

    from storage import StorageManager
    storage = StorageManager()
    session_turns = []

    if task_description:
        try:
            response = client.run_agent_turn(task_description, ui)
            ui.display_response(response)
            sys.exit(0)
        except Exception as e:
            ui.show_error(f"Fehler bei der autonomen Ausführung: {str(e)}")
            sys.exit(1)

    # Lazy import for prompt_toolkit
    from prompt_toolkit import prompt
    from prompt_toolkit.formatted_text import FormattedText

    def _make_prompt():
        """Dynamischer Prompt: zeigt Modell + aktiven Key."""
        model_short = client.model_name.replace("gemini-", "").replace("-flash", "f").replace("-lite", "l")
        pool = client.key_pool
        n = pool.active_index() + 1
        total = pool.count()
        return FormattedText([
            ("class:model", f" {model_short}"),
            ("class:sep", " ·"),
            ("class:key", f" k{n}/{total}"),
            ("class:sep", " › "),
            ("", ""),
        ])

    from prompt_toolkit.styles import Style
    _prompt_style = Style.from_dict({
        "model": "ansibrightcyan",
        "sep": "ansigray",
        "key": "ansigreen",
    })

    while True:
        try:
            # Eingabe über prompt_toolkit mit Fallback auf standard input()
            try:
                user_input = prompt(_make_prompt, style=_prompt_style)
            except Exception:
                user_input = input("› ")

            # Entferne führende/folgende Leerzeichen
            cmd = normalize_command(user_input)

            if not cmd:
                continue

            # Überprüfung auf Slash-Befehle oder klassische Exit-Befehle
            if cmd.lower() in ["exit", "quit", "beenden", "/exit"]:
                save_session_to_sonu_md(session_turns)
                client.save_session(session_turns)
                print("Auf Wiedersehen!")
                break

            # @search(query) Syntax: inline Web-Suche vor dem Turn
            import re as _re
            _search_hits = _re.findall(r'@search\(([^)]+)\)', cmd)
            if _search_hits:
                import tools as _tools
                search_results = []
                for q in _search_hits:
                    r = _tools.google_search(q.strip())
                    search_results.append(f"@search({q}):\n{r}")
                    cmd = cmd.replace(f"@search({q})", f"[Suchergebnis für '{q}' weiter unten]", 1)
                cmd = cmd + "\n\n--- Suchergebnisse ---\n" + "\n\n".join(search_results)

            # Plan mode: intercept approval/rejection before processing
            if client.plan_mode.active and not cmd.startswith("/"):
                if client.plan_mode.is_approval(cmd):
                    pending = client.plan_mode.exit()
                    client._config_cache = None
                    ui.show_info("[bold green]Plan genehmigt.[/bold green] Führe jetzt aus...")
                    if pending:
                        cmd = pending
                    # fall through to normal processing with tools enabled
                elif client.plan_mode.is_rejection(cmd):
                    client.plan_mode.exit()
                    client._config_cache = None
                    ui.show_info("Plan [bold red]abgebrochen[/bold red].")
                    continue

            if not cmd.startswith("/"):
                # Prepend IDE selection context if fresh
                try:
                    from vscode_bridge.selection_reader import SelectionReader as _SR
                    _sel_ctx = _SR().format_for_prompt()
                    if _sel_ctx:
                        cmd = _sel_ctx + "\n" + cmd
                except Exception:
                    pass
                ui.start_thinking(f"Denke nach...")
                
            if cmd == "/help":
                ui.stop_thinking()
                ui.show_help()
                continue

            elif cmd == "/clear":
                ui.stop_thinking()
                ui.console.clear()
                from jit_context import reset_session_cache
                reset_session_cache()
                ui.show_info("Terminalansicht geleert.")
                continue

            elif cmd == "/status":
                ui.stop_thinking()
                tasks = client.process_mgr.list_tasks()
                running_tasks = sum(1 for t in tasks if t["status"] == "running")
                ui.show_status_snapshot(
                    provider="gemini",
                    model=client.model_name,
                    yolo=ui.yolo,
                    active_skill=client.skills_mgr.active_skill,
                    running_tasks=running_tasks,
                    interaction_count=storage.interaction_count,
                )
                continue

            elif cmd == "/docs":
                ui.stop_thinking()
                with ui.show_spinner("Generiere COMMANDS.md Dokumentation..."):
                    try:
                        md = client.living_docs.generate_help_md()
                        ui.show_info("Dokumentation [bold cyan]COMMANDS.md[/bold cyan] erfolgreich generiert!")
                    except Exception as e:
                        ui.show_error(f"Fehler bei der Dokumentationserstellung: {str(e)}")
                continue
                
            elif cmd == "/models":
                ui.stop_thinking()
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
                ui.stop_thinking()
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
                ui.stop_thinking()
                path = storage.get_log_path()
                count = storage.interaction_count
                ui.show_info(
                    f"Log-Datei: [cyan]{path}[/cyan]\n"
                    f"  Anzahl bisheriger Interaktionen: [bold green]{count}[/bold green]"
                )
                continue

            elif cmd.startswith("/provider"):
                ui.stop_thinking()
                parts = cmd.split(maxsplit=1)
                import providers
                if len(parts) == 1:
                    ui.show_info(f"Aktiver Provider: [bold cyan]gemini[/bold cyan] | Modell: {client.model_name}")
                else:
                    new_model = parts[1].strip()
                    client.set_model(new_model)
                    ui.show_info(f"Modell gewechselt zu: [bold]{new_model}[/bold]")
                continue

            elif cmd == "/tools":
                ui.stop_thinking()
                ui.show_tools()
                continue

            elif cmd == "/yolo":
                ui.stop_thinking()
                ui.set_yolo(not ui.yolo)
                continue

            elif cmd == "/skills":
                ui.stop_thinking()
                skills = client.skills_mgr.list_skills()
                active = client.skills_mgr.active_skill
                print("\nVerfügbare Experten-Skills:")
                for s in skills:
                    marker = "[bold green](AKTIV)[/bold green]" if s == active else ""
                    print(f"  • {s} {marker}")
                print()
                continue
                
            elif cmd.startswith("/activate"):
                ui.stop_thinking()
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
                ui.stop_thinking()
                client.skills_mgr.deactivate_skill()
                client.reset_chat()
                ui.show_info("Experten-Skill deaktiviert. Baseline-Prompt wiederhergestellt.")
                continue

            elif cmd == "/memory":
                ui.stop_thinking()
                import os as _os
                mem = client.memory_mgr.load_memory(_os.getcwd())
                if mem.strip():
                    print("\n--- Aktives 4-Ebenen-Gedächtnis ---\n")
                    print(mem)
                    print("-" * 40 + "\n")
                else:
                    ui.show_info("Kein SONU.md-Gedächtnis gefunden.")
                continue

            elif cmd.startswith("/xmemory") or cmd.startswith("/xmem"):
                ui.stop_thinking()
                from cross_project_memory import load_index, save_memory, delete_memory, search_memories
                parts = cmd.split(maxsplit=2)
                subcmd = parts[1] if len(parts) > 1 else "list"
                if subcmd == "list":
                    print("\n" + load_index())
                elif subcmd == "search" and len(parts) > 2:
                    print(search_memories(parts[2]))
                elif subcmd == "delete" and len(parts) > 2:
                    print(delete_memory(parts[2]))
                elif subcmd == "save":
                    # /xmemory save <type> <name> | <description> | <body>
                    if len(parts) > 2:
                        fields = parts[2].split("|")
                        if len(fields) >= 3:
                            mtype, mname, mdesc = fields[0].strip(), fields[1].strip(), fields[2].strip()
                            mbody = fields[3].strip() if len(fields) > 3 else mdesc
                            print(save_memory(mname, mdesc, mtype, mbody))
                        else:
                            ui.show_error("Format: /xmemory save <type> | <name> | <description> | <body>")
                    else:
                        ui.show_error("Format: /xmemory save <type> | <name> | <description> | <body>")
                else:
                    ui.show_info("[bold]Cross-Project Memory Befehle:[/bold]\n"
                                 "  /xmemory list\n"
                                 "  /xmemory search <query>\n"
                                 "  /xmemory save user | <name> | <description> | <body>\n"
                                 "  /xmemory delete <name>")
                continue

            elif cmd.startswith("/todo"):
                ui.stop_thinking()
                parts = cmd.split(maxsplit=2)
                subcmd = parts[1] if len(parts) > 1 else "list"
                if subcmd == "list":
                    print("\n" + client.todo_mgr.format_for_display() + "\n")
                elif subcmd == "add" and len(parts) > 2:
                    t = client.todo_mgr.add(parts[2])
                    ui.show_info(f"Task [{t['id']}] hinzugefügt: {t['content']}")
                    client._config_cache = None  # rebuild prompt
                elif subcmd in ("done", "complete") and len(parts) > 2:
                    print(client.todo_mgr.update(int(parts[2]), "completed"))
                    client._config_cache = None
                elif subcmd == "progress" and len(parts) > 2:
                    print(client.todo_mgr.update(int(parts[2]), "in_progress"))
                    client._config_cache = None
                elif subcmd in ("remove", "delete") and len(parts) > 2:
                    print(client.todo_mgr.remove(int(parts[2])))
                    client._config_cache = None
                elif subcmd == "clear":
                    n = client.todo_mgr.clear_completed()
                    ui.show_info(f"{n} abgeschlossene Tasks gelöscht.")
                else:
                    ui.show_info("[bold]Todo Befehle:[/bold]\n"
                                 "  /todo list\n"
                                 "  /todo add <aufgabe>\n"
                                 "  /todo done <id>\n"
                                 "  /todo progress <id>\n"
                                 "  /todo remove <id>\n"
                                 "  /todo clear")
                continue

            elif cmd.startswith("/schedule") or cmd.startswith("/cron"):
                ui.stop_thinking()
                from harness.scheduler import add_job, remove_job, load_jobs, toggle_job, notify
                parts = cmd.split(maxsplit=3)
                subcmd = parts[1] if len(parts) > 1 else "list"
                if subcmd == "list":
                    jobs = load_jobs()
                    if not jobs:
                        ui.show_info("Keine geplanten Jobs.")
                    else:
                        print("\nGeplante Jobs:")
                        for j in jobs:
                            status = "[green]ON[/green]" if j.get("enabled") else "[red]OFF[/red]"
                            last = j.get("last_run", "nie")[:19] if j.get("last_run") else "nie"
                            print(f"  [{j['id']}] {j['name']} | cron: {j['cron']} | last: {last} | {status}")
                            print(f"       prompt: {j['prompt'][:80]}")
                        print()
                elif subcmd == "add" and len(parts) >= 4:
                    # /schedule add "name" "0 8 * * *" "prompt text"
                    name_part = parts[1] if len(parts) > 1 else "job"
                    # Re-parse: /schedule add <name> <cron> <prompt>
                    rest = cmd[len("/schedule add "):].strip() if cmd.startswith("/schedule") else cmd[len("/cron add "):].strip()
                    fields = rest.split("|")
                    if len(fields) >= 3:
                        jname, jcron, jprompt = fields[0].strip(), fields[1].strip(), fields[2].strip()
                        j = add_job(jname, jcron, jprompt)
                        ui.show_info(f"Job [{j['id']}] '{jname}' erstellt. Cron: {jcron}")
                    else:
                        ui.show_error("Format: /schedule add <name> | <cron> | <prompt>\nBeispiel: /schedule add nightly | 0 2 * * * | Optimiere alle Logs")
                elif subcmd == "remove" and len(parts) > 2:
                    ok = remove_job(int(parts[2]))
                    print("OK: Gelöscht." if ok else "FEHLER: Job nicht gefunden.")
                elif subcmd in ("enable", "disable") and len(parts) > 2:
                    ok = toggle_job(int(parts[2]), subcmd == "enable")
                    print(f"OK: Job {parts[2]} {'aktiviert' if subcmd == 'enable' else 'deaktiviert'}." if ok else "FEHLER: Job nicht gefunden.")
                elif subcmd == "test":
                    notify("Sonu Benachrichtigung", "Test-Benachrichtigung erfolgreich!")
                    ui.show_info("Test-Benachrichtigung gesendet.")
                else:
                    ui.show_info("[bold]Schedule Befehle:[/bold]\n"
                                 "  /schedule list\n"
                                 "  /schedule add <name> | <cron> | <prompt>\n"
                                 "  /schedule remove <id>\n"
                                 "  /schedule enable <id>\n"
                                 "  /schedule disable <id>\n"
                                 "  /schedule test\n"
                                 "\nCron-Spezialwerte: @hourly @daily @weekly @reboot")
                continue

            elif cmd.startswith("/plan"):
                ui.stop_thinking()
                parts = cmd.split(maxsplit=1)
                if len(parts) == 1 or parts[1].strip() == "":
                    # Toggle plan mode
                    if client.plan_mode.active:
                        client.plan_mode.exit()
                        client._config_cache = None
                        ui.show_info("Plan Mode [bold red]deaktiviert[/bold red]. Tools sind wieder aktiv.")
                    else:
                        client.plan_mode.enter()
                        client._config_cache = None
                        ui.show_info("Plan Mode [bold yellow]aktiviert[/bold yellow]. Sonu produziert nur Pläne — tippe 'ja' zum Genehmigen.")
                elif parts[1].strip().lower() in ("off", "exit", "deactivate", "aus"):
                    client.plan_mode.exit()
                    client._config_cache = None
                    ui.show_info("Plan Mode deaktiviert.")
                else:
                    # /plan <aufgabe> — enter plan mode with pre-loaded prompt
                    client.plan_mode.enter(parts[1].strip())
                    client._config_cache = None
                    ui.show_info(f"Plan Mode aktiviert für: [cyan]{parts[1].strip()}[/cyan]")
                continue

            elif cmd == "/tasks" or cmd == "/bg":
                ui.stop_thinking()
                tasks = client.process_mgr.list_tasks()
                if not tasks:
                    ui.show_info("Keine aktiven Hintergrundprozesse.")
                else:
                    print("\nAktive Hintergrundprozesse:")
                    for t in tasks:
                        print(f"  [{t['id']}] {t['command']} - Status: {t['status']} (Laufzeit: {t['elapsed']})")
                    print()
                continue

            elif cmd.startswith("/bg watch"):
                parts = cmd.split()
                if len(parts) < 3:
                    ui.show_error("Bitte gib die Task-ID an, z.B. `/bg watch 1`")
                else:
                    try:
                        tid = int(parts[2].strip())
                        ui.show_info(f"[dim]Live-Output für Task-ID {tid} (Ctrl+C zum Stoppen)...[/dim]")
                        try:
                            for chunk in client.process_mgr.watch_task_output(tid):
                                print(chunk, end="", flush=True)
                            print()
                            ui.show_info(f"[dim]Task-ID {tid} beendet.[/dim]")
                        except KeyboardInterrupt:
                            print("\n")
                            ui.show_info("[dim]Live-Beobachtung abgebrochen.[/dim]")
                    except ValueError:
                        ui.show_error("Ungültige Task-ID.")
                    except Exception as e:
                        ui.show_error(str(e))
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

            elif cmd.startswith("/selfimprove"):
                parts = cmd.split()
                minutes = 60
                if len(parts) > 1:
                    try:
                        minutes = int(parts[1].strip())
                    except ValueError:
                        ui.show_error("Ungültige Zeit. Beispiel: /selfimprove 60")
                        continue
                import os as _os
                script = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "self_improve.py")
                bg_cmd = f"python \"{script}\" {minutes}"
                try:
                    tid = client.process_mgr.start_task(bg_cmd)
                    ui.show_info(
                        f"🔁 Selbstverbesserungs-Loop gestartet (Task-ID [bold yellow]{tid}[/bold yellow]) — {minutes} Minuten via Groq.\n"
                        f"Live beobachten: [yellow]/bg watch {tid}[/yellow]   "
                        f"Log: [yellow]/bg output {tid}[/yellow]   "
                        f"Stoppen: [yellow]/bg kill {tid}[/yellow]"
                    )
                except Exception as e:
                    ui.show_error(f"Fehler beim Starten: {str(e)}")
                continue

            elif cmd == "/health":
                pool = client.key_pool
                healthy = sum(1 for i in range(pool.count()) if pool.is_available(i))
                ui.show_info(f"Keys: {healthy}/{pool.count()} verfuegbar | Modell: {client.model_name}")
                continue

            elif cmd.startswith("/keys"):
                parts = cmd.split()
                pool = client.key_pool
                if len(parts) > 1 and parts[1].strip() == "reset":
                    pool.reset_all()
                    ui.show_info("Alle Key-Cooldowns wurden erfolgreich zurückgesetzt.")
                    continue

                lines = pool.status_lines()
                healthy = sum(1 for i in range(pool.count()) if pool.is_available(i))
                ui.show_info(f"[bold]Key Pool [{healthy}/{pool.count()} verfuegbar][/bold]\n" + "\n".join(lines))
                continue

            elif cmd.startswith("/rotator"):
                parts = cmd.split(maxsplit=1)
                subcmd = parts[1].strip() if len(parts) > 1 else "status"
                if subcmd == "status":
                    cooldowns = client._load_shared_cooldowns()
                    if not cooldowns:
                        ui.show_info("Key-Rotator: Alle Keys sind [bold green]gesund[/bold green].")
                    else:
                        ui.console.print("\n[bold yellow]Erschöpfte Keys im Cooldown (global):[/bold yellow]")
                        for key, expiry in cooldowns.items():
                            remain = int(expiry - time.time())
                            ui.console.print(f"  • {key[:12]}... - Noch [bold red]{remain}s[/bold red]")
                        ui.console.print("")
                elif subcmd == "start":
                    tasks = client.process_mgr.list_tasks()
                    if any("rotator_daemon.py" in t["command"] and t["status"] == "running" for t in tasks):
                        ui.show_info("Rotator-Daemon läuft bereits.")
                    else:
                        daemon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rotator_daemon.py")
                        client.process_mgr.start_task(f'python "{daemon_path}"')
                        ui.show_info("Rotator-Daemon [bold green]gestartet[/bold green].")
                elif subcmd == "stop":
                    tasks = client.process_mgr.list_tasks()
                    found = False
                    for t in tasks:
                        if "rotator_daemon.py" in t["command"]:
                            client.process_mgr.kill_task(t["id"])
                            found = True
                    if found:
                        ui.show_info("Rotator-Daemon [bold red]gestoppt[/bold red].")
                    else:
                        ui.show_error("Kein laufender Rotator-Daemon gefunden.")
                else:
                    ui.show_info("Verwendung: /rotator [status|start|stop]")
                continue

            elif cmd == "/predict":
                warnings = client.predictive.analyze()
                if warnings:
                    ui.show_error("Predictive Debugger hat potenzielle Probleme gefunden:")
                    for warning in warnings:
                        print(f"  - {warning}")
                else:
                    ui.show_info("Predictive Debugger: Keine auffälligen Fehlermuster in den aktuellen Logs gefunden.")
                continue

            elif cmd == "/redundancy":
                status = client.redundancy_mgr.get_status()
                ui.show_info(
                    f"Redundancy-Fallback Status:\n"
                    f"  Aktiver Provider: [bold cyan]{status['current_provider']}[/bold cyan]\n"
                    f"  Historie: {status['history'] if status['history'] else 'Keine Vorfaelle'}"
                )
                continue

            elif cmd.startswith("/ghost"):
                parts = cmd.split(maxsplit=1)
                subcmd = parts[1].strip() if len(parts) > 1 else "help"
                if subcmd == "audit":
                    with ui.show_spinner("Ghost-Integrator: Linter + Tests..."):
                        ok, log = client.ghost.run_pre_commit_audit()
                    if ok:
                        ui.show_info("[bold green]Audit OK[/bold green] — alle Tests grün, Formatierung sauber.")
                    else:
                        ui.show_error(f"Audit fehlgeschlagen:\n{log[:800]}")
                elif subcmd == "fix":
                    with ui.show_spinner("Ghost-Integrator: Autonome Reparatur..."):
                        ok, log = client.ghost.run_pre_commit_audit()
                    if ok:
                        ui.show_info("Nichts zu reparieren — Audit bereits grün.")
                    else:
                        fixed = client.ghost.autonomous_repair(log)
                        if fixed:
                            ui.show_info("[bold green]Reparatur erfolgreich.[/bold green]")
                        else:
                            ui.show_error("Reparatur fehlgeschlagen — Git-Rollback wurde ausgeführt.")
                elif subcmd == "watch":
                    client.ghost.start_watcher()
                    ui.show_info("Ghost-Watcher [bold green]gestartet[/bold green] — überwacht .py-Änderungen.")
                elif subcmd == "stop":
                    client.ghost.stop_watcher()
                    ui.show_info("Ghost-Watcher [bold yellow]gestoppt[/bold yellow].")
                elif subcmd == "status":
                    watching = client.ghost.is_watching()
                    state = "[bold green]aktiv[/bold green]" if watching else "[bold red]inaktiv[/bold red]"
                    ui.show_info(f"Ghost-Watcher: {state}")
                else:
                    ui.show_info(
                        "Ghost-Integrator Befehle:\n"
                        "  [bold]/ghost audit[/bold]  — Linter + Tests manuell ausführen\n"
                        "  [bold]/ghost fix[/bold]    — Audit + autonome Reparatur bei Fehlern\n"
                        "  [bold]/ghost watch[/bold]  — Datei-Watcher starten (auto-audit bei Änderungen)\n"
                        "  [bold]/ghost stop[/bold]   — Watcher stoppen\n"
                        "  [bold]/ghost status[/bold] — Watcher-Status anzeigen"
                    )
                continue

            elif cmd.startswith("/distill"):
                parts = cmd.split(maxsplit=1)
                if len(parts) == 1:
                    ui.show_error("Bitte gib einen Namen fuer das Skill an, z.B. `/distill react-debugger`")
                else:
                    skill_name = parts[1].strip()
                    with ui.show_spinner(f"Distilliere Workflow in Skill '{skill_name}'..."):
                        try:
                            # Lese die letzten ~10.000 Zeichen aus dem Log
                            log_path = storage.get_log_path()
                            log_content = ""
                            if __import__("os").path.exists(log_path):
                                with open(log_path, "r", encoding="utf-8") as f:
                                    f.seek(max(0, __import__("os").path.getsize(log_path) - 10000))
                                    log_content = f.read()

                            distill_prompt = (
                                "Analysiere die folgenden letzten Interaktionen aus dem Log. "
                                "Extrahiere die logischen Denkschritte, eingesetzten Tools und erfolgreichen Muster in ein praezises, "
                                "wiederverwendbares Experten-Skill-Profil (Markdown-Format, imperatives Deutsch, Fokus auf Best Practices). "
                                "Antworte NUR mit den reinen Instruktionen fuer das Skill-Profil, kein Vorgeplaenkel.\n\n"
                                f"LOGS:\n{log_content}"
                            )
                            
                            # Wir nutzen den aktiven Provider statenlos
                            if client.provider == "gemini":
                                resp = client.client.models.generate_content(
                                    model=client.model_name,
                                    contents=distill_prompt
                                )
                                skill_instruction = resp.text
                            else:
                                skill_instruction = "(Skill-Distillation nur mit Gemini verfuegbar)"

                            # Skill speichern
                            path = client.skills_mgr.save_skill(skill_name, skill_instruction)
                            ui.show_info(f"Skill erfolgreich destilliert und unter [cyan]{path}[/cyan] gespeichert!\nDu kannst es jetzt mit `/activate {skill_name}` nutzen.")
                        except Exception as e:
                            ui.show_error(f"Fehler bei der Skill-Distillation: {str(e)}")
                continue

            elif cmd.startswith("/generate-problems"):
                parts = cmd.split(maxsplit=1)
                output_file = parts[1].strip() if len(parts) > 1 else "problems.json"
                with ui.show_spinner(f"Generiere 100 Forschungsprobleme → {output_file}..."):
                    try:
                        from generate_100_problems import generate as _gen_problems
                        problems = _gen_problems()
                        ui.show_info(
                            f"[bold cyan]{len(problems)} Probleme[/bold cyan] gespeichert in [cyan]{output_file}[/cyan].\n"
                            f"Starte Batch-Recherche mit [yellow]/batch {output_file}[/yellow]."
                        )
                    except Exception as e:
                        ui.show_error(f"Fehler beim Generieren: {str(e)}")
                continue

            elif cmd.startswith("/batch"):
                parts = cmd.split(maxsplit=1)
                problems_file = parts[1].strip() if len(parts) > 1 else "problems.json"
                import os as _os
                _script = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "batch_researcher.py")
                _bcmd = f"python \"{_script}\" \"{problems_file}\""
                try:
                    tid = client.process_mgr.start_task(_bcmd)
                    ui.show_info(
                        f"Batch-Researcher gestartet (Task-ID [bold yellow]{tid}[/bold yellow]).\n"
                        f"Ergebnisse landen in [cyan]recherche_ergebnisse/[/cyan] — live verfolgen mit [yellow]/bg output {tid}[/yellow]."
                    )
                except Exception as e:
                    ui.show_error(f"Fehler beim Starten: {str(e)}")
                continue
            elif cmd.startswith("/loop"):
                parts = cmd.split()
                duration = 60
                if len(parts) > 1:
                    try:
                        duration = int(parts[1].strip())
                    except ValueError:
                        pass
                import os as _os
                _lscript = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "self_improve.py")
                _lcmd = f"python \"{_lscript}\" {duration}"
                try:
                    tid = client.process_mgr.start_task(_lcmd)
                    ui.show_info(
                        f"Sonu Auto-Evolution Loop gestartet für [bold yellow]{duration} Minuten[/bold yellow] (Task-ID [bold yellow]{tid}[/bold yellow]).\n"
                        f"Sonu nutzt exklusiv deinen Groq API Key zur token-schonenden Selbstoptimierung.\n"
                        f"Verfolge den Fortschritt live mit: [yellow]/bg output {tid}[/yellow] oder [yellow]/bg watch {tid}[/yellow]"
                    )
                except Exception as e:
                    ui.show_error(f"Fehler beim Starten der Selbstverbesserungsschleife: {str(e)}")
                continue

            elif cmd.startswith("/watchdog"):
                parts = cmd.split(maxsplit=1)
                if len(parts) == 1:
                    ui.show_error("Bitte Skript angeben, z.B. [yellow]/watchdog batch_researcher.py[/yellow]")
                else:
                    import os as _os
                    _target = parts[1].strip()
                    _wscript = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "sonu_watchdog.py")
                    _wcmd = f"python \"{_wscript}\" \"{_target}\""
                    try:
                        tid = client.process_mgr.start_task(_wcmd)
                        ui.show_info(
                            f"Sonu Watchdog aktiv für [cyan]{_target}[/cyan] (Task-ID [bold yellow]{tid}[/bold yellow]).\n"
                            f"Absturz → Sonu analysiert & fixt automatisch. Status: [yellow]/bg output {tid}[/yellow]."
                        )
                    except Exception as e:
                        ui.show_error(f"Watchdog-Start fehlgeschlagen: {str(e)}")
                continue

            elif cmd.startswith("/map"):
                parts = cmd.split(maxsplit=1)
                import os as _os
                from semantic_navigator import SemanticNavigator
                nav = SemanticNavigator()
                if len(parts) == 1:
                    target = _os.getcwd()
                    result = nav.map_directory(target)
                else:
                    arg = parts[1].strip()
                    if arg.startswith("find "):
                        symbol = arg[5:].strip()
                        matches = nav.find_symbol(symbol, _os.getcwd())
                        result = "\n".join(matches) if matches else f"Symbol '{symbol}' nicht gefunden."
                    elif _os.path.isdir(arg):
                        result = nav.map_directory(arg)
                    else:
                        result = nav.map_file(arg)
                print(f"\n{result}\n")
                continue

            elif cmd.startswith("/recall"):
                parts = cmd.split(maxsplit=1)
                from temporal_memory import TemporalMemory
                temporal = TemporalMemory()
                if len(parts) == 1:
                    sessions = temporal.list_sessions(8)
                    if not sessions:
                        ui.show_info("Keine gespeicherten Sessions gefunden.")
                    else:
                        print("\nLetzte Sessions:")
                        for s in sessions:
                            print(f"  [{s['id']}]  {s['timestamp']}  ({s['turns']} Turns)  {s['topic']}")
                        print()
                else:
                    arg = parts[1].strip()
                    if arg.startswith("search "):
                        query = arg[7:].strip()
                        results = temporal.search_sessions(query)
                        if not results:
                            ui.show_info(f"Keine Sessions für '{query}' gefunden.")
                        else:
                            print(f"\nTreffer für '{query}':")
                            for r in results:
                                print(f"  [{r['id']}]  {r['timestamp']}  {r['topic']}")
                            print()
                    else:
                        try:
                            data = temporal.load_session(arg)
                            print(f"\n--- Session {arg} ({data.get('topic','')}) ---")
                            for turn in data.get("turns", [])[:20]:
                                print(f"\nDu: {turn.get('user','')}")
                                resp = turn.get('sonu','')
                                print(f"Sonu: {resp[:300]}{'...' if len(resp) > 300 else ''}")
                            print()
                        except Exception as e:
                            ui.show_error(str(e))
                continue

            elif cmd.startswith("/refactor"):
                parts = cmd.split(maxsplit=2)
                import os as _os
                from refactor_pipeline import RefactorPipeline
                pipeline = RefactorPipeline()
                if len(parts) == 1:
                    ui.show_error("Bitte Pfad angeben: [yellow]/refactor <datei.py>[/yellow] oder [yellow]/refactor smells <datei.py>[/yellow]")
                elif parts[1].strip() == "smells" and len(parts) > 2:
                    path = parts[2].strip()
                    smells = pipeline.detect_smells(path)
                    print(f"\nCode-Smells in {_os.path.basename(path)}:")
                    for s in smells:
                        print(f"  • {s}")
                    print()
                else:
                    path = parts[1].strip()
                    with ui.show_spinner(f"Analysiere {_os.path.basename(path)} und generiere Refactoring-Vorschläge..."):
                        result = pipeline.suggest_refactoring(path, client)
                    ui.display_response(result)
                continue

            elif cmd.startswith("/style"):
                parts = cmd.split(maxsplit=1)
                if len(parts) == 1:
                    styles = client.personality.list_styles()
                    active = client.personality.active_style
                    print("\nVerfügbare Kommunikationsstile:")
                    for name, desc in styles.items():
                        marker = " [AKTIV]" if name == active else ""
                        print(f"  • {name}{marker}: {desc}")
                    print()
                else:
                    style_name = parts[1].strip()
                    msg = client.personality.set_style(style_name)
                    if "Unbekannter" in msg:
                        ui.show_error(msg)
                    else:
                        client._rebuild_preserving_history()
                        ui.show_info(f"[bold cyan]{msg}[/bold cyan] System-Prompt wurde neu aufgebaut.")
                continue

            elif cmd == "/jules-batch":
                import os as _os
                _jb_script = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "delegate_7_tasks.py")
                _jb_cmd = f"python \"{_jb_script}\""
                try:
                    tid = client.process_mgr.start_task(_jb_cmd)
                    ui.show_info(
                        f"Jules Ultra-Batch gestartet (Task-ID [bold yellow]{tid}[/bold yellow]).\n"
                        f"7 Aufgaben werden an Jules delegiert — Logs in [cyan]logs/jules_task_*.log[/cyan].\n"
                        f"Status: [yellow]/bg output {tid}[/yellow]"
                    )
                except Exception as e:
                    ui.show_error(f"Jules-Batch fehlgeschlagen: {str(e)}")
                continue

            elif cmd.startswith("/checkpoint"):
                ui.stop_thinking()
                import os as _os, json as _json, datetime as _dt
                _ckpt_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "logs", "checkpoints")
                _os.makedirs(_ckpt_dir, exist_ok=True)
                parts = cmd.split(maxsplit=2)
                subcmd = parts[1].strip() if len(parts) > 1 else "list"

                if subcmd == "save":
                    name = parts[2].strip() if len(parts) > 2 else _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
                    try:
                        history = client.get_history()
                        snapshot = {
                            "name": name,
                            "timestamp": _dt.datetime.now().isoformat(),
                            "provider": "gemini",
                            "model": client.model_name,
                            "turns": session_turns,
                            "history_len": len(history),
                        }
                        path = _os.path.join(_ckpt_dir, f"{name}.json")
                        with open(path, "w", encoding="utf-8") as f:
                            _json.dump(snapshot, f, ensure_ascii=False, indent=2, default=str)
                        ui.show_info(f"Checkpoint gespeichert: [cyan]{name}[/cyan]  ({len(session_turns)} Turns)")
                    except Exception as e:
                        ui.show_error(f"Checkpoint-Fehler: {e}")

                elif subcmd == "load":
                    name = parts[2].strip() if len(parts) > 2 else ""
                    if not name:
                        ui.show_error("Bitte Namen angeben: /checkpoint load <name>")
                    else:
                        path = _os.path.join(_ckpt_dir, f"{name}.json")
                        if not _os.path.exists(path):
                            path = _os.path.join(_ckpt_dir, name)
                        try:
                            with open(path, "r", encoding="utf-8") as f:
                                snap = _json.load(f)
                            session_turns.clear()
                            session_turns.extend(snap.get("turns", []))
                            model = snap.get("model", client.model_name)
                            client.set_model(model)
                            client.reset_chat()
                            ui.show_info(
                                f"Checkpoint [cyan]{snap['name']}[/cyan] geladen  "
                                f"({len(session_turns)} Turns · {snap.get('timestamp','?')[:16]})"
                            )
                        except Exception as e:
                            ui.show_error(f"Laden fehlgeschlagen: {e}")

                else:  # list
                    files = sorted(_os.listdir(_ckpt_dir), reverse=True)[:10]
                    if not files:
                        ui.show_info("Keine Checkpoints gefunden. Erstelle mit: /checkpoint save [name]")
                    else:
                        print("\nCheckpoints:")
                        for fn in files:
                            if fn.endswith(".json"):
                                try:
                                    with open(_os.path.join(_ckpt_dir, fn), "r") as f:
                                        d = _json.load(f)
                                    print(f"  [cyan]{d['name']}[/cyan]  {d.get('timestamp','')[:16]}  {d.get('turns_count', len(d.get('turns',[])))  } Turns")
                                except Exception:
                                    print(f"  {fn}")
                        print()
                continue

            elif cmd.startswith("/cost"):
                ui.stop_thinking()
                parts = cmd.split(maxsplit=1)
                since = None
                if len(parts) > 1 and parts[1].strip() == "session":
                    import datetime as _dt
                    since = _dt.datetime.now().strftime("%Y-%m-%dT00:00:00")
                rows = storage.get_session_stats(since_iso=since)
                if not rows:
                    ui.show_info("Keine Token-Daten vorhanden.")
                else:
                    from rich.table import Table
                    label = "Heute" if since else "Gesamt"
                    tbl = Table(title=f"Token-Kosten ({label})", border_style="cyan", box=box.SIMPLE_HEAD)
                    tbl.add_column("Provider", style="cyan")
                    tbl.add_column("Modell", style="dim")
                    tbl.add_column("Requests", justify="right")
                    tbl.add_column("Input Tok", justify="right")
                    tbl.add_column("Output Tok", justify="right")
                    tbl.add_column("Ø Latenz", justify="right", style="dim")
                    tbl.add_column("Kosten $", justify="right", style="green")
                    total_cost = 0.0
                    for prov, model, pt, ct, cost, lat, cnt in rows:
                        total_cost += cost or 0
                        tbl.add_row(
                            prov, model, str(cnt),
                            f"{pt:,}", f"{ct:,}",
                            f"{lat:.0f}ms",
                            f"${cost:.6f}"
                        )
                    ui.console.print(tbl)
                    ui.console.print(f"  [bold]Total:[/bold] [green]${total_cost:.6f}[/green]")
                continue

            elif cmd.startswith("/router"):
                ui.stop_thinking()
                pool = client.key_pool
                healthy = sum(1 for i in range(pool.count()) if pool.is_available(i))
                ui.show_info(f"Modell: [bold]{client.model_name}[/bold] | Keys: {healthy}/{pool.count()} verfuegbar")
                continue

            elif cmd.startswith("/swarm"):
                parts = cmd.split(maxsplit=1)
                if len(parts) == 1:
                    ui.show_error("Bitte gib ein Thema an, z.B. `/swarm Wie implementiere ich einen LRU-Cache?`")
                else:
                    topic = parts[1].strip()
                    with ui.show_spinner("Swarm läuft — befrage alle Provider parallel..."):
                        result = client.swarm.run(topic)
                    if not result["best"]:
                        ui.show_error(f"Alle Provider fehlgeschlagen: {result.get('errors', {})}")
                    else:
                        scores_str = "  ".join(
                            f"[cyan]{p}[/cyan]: {s:.0f}" for p, s in
                            sorted(result["scores"].items(), key=lambda x: -x[1])
                        )
                        ui.show_info(f"Gewinner: [bold green]{result['winner']}[/bold green]   Scores: {scores_str}")
                        ui.display_response(result["best"])
                continue

            elif cmd.startswith("/"):
                ui.stop_thinking()
                suggestions = suggest_command(cmd)
                if suggestions:
                    ui.show_error(
                        "Unbekannter Befehl. Meintest du vielleicht: "
                        + ", ".join(f"[yellow]{item}[/yellow]" for item in suggestions)
                        + " ?"
                    )
                else:
                    ui.show_error("Unbekannter Befehl. Nutze [yellow]/help[/yellow] für die Befehlsübersicht.")
                continue

            # Agentischer Turn
            ui.start_thinking()
            try:
                response = client.run_agent_turn(cmd, ui)
            except QuotaExhaustedException as qe:
                response = None
                ui.show_error(f"Alle {qe.key_count} Keys erschoepft fuer '{qe.model_name}'. Warte ~1h oder fuege neue Keys hinzu.")
            finally:
                ui.stop_thinking()

            # Finale Antwort als Markdown rendern (mit VSCode file:line links).
            if response:
                try:
                    import os as _os2
                    from vscode_bridge.linker import linkify_response as _linkify
                    response = _linkify(response, _os2.getcwd())
                except Exception:
                    pass
                ui.display_response(response)

            # Fire on_response hooks
            try:
                import harness as _h2
                _h2.hooks().on_response(response or "")
            except Exception:
                pass

            # Logge die Interaktion
            storage.log_interaction(cmd, response or "(keine Textantwort)")
            session_turns.append({"user": cmd, "sonu": response or ""})
        except KeyboardInterrupt:
            # Erlaubt dem Benutzer, mit Ctrl+C eine angefangene Eingabe abzubrechen
            print("\nEingabe abgebrochen.")
            continue
        except EOFError:
            save_session_to_sonu_md(session_turns)
            if session_turns:
                try:
                    from temporal_memory import TemporalMemory
                    TemporalMemory().save_session(session_turns, topic=session_turns[0].get("user", "")[:80])
                except Exception:
                    pass
            print("\nAuf Wiedersehen!")
            break
        except Exception as e:
            ui.show_error(f"Ein Fehler ist aufgetreten: {str(e)}")

if __name__ == "__main__":
    main()
