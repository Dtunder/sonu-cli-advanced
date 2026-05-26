import sys
import subprocess
import os
import time

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Stelle sicher, dass sonu-cli importierbar ist
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sonu_client import SonuClient
from terminal_ui import TerminalUI

def run_watchdog(target_script):
    ui = TerminalUI()
    ui.set_yolo(True)  # Watchdog agiert 100% autonom ohne RUECKFRAGEN!

    # Initialize headless Sonu
    ui.show_info("[bold cyan]🤖 Sonu-20X Cybernetic Watchdog initialisiert.[/bold cyan]")
    try:
        client = SonuClient()
    except Exception as e:
        ui.show_error(f"Konnte SonuClient nicht starten: {e}")
        return

    max_retries = 3
    attempt = 1

    while attempt <= max_retries:
        ui.show_info(f"\n[bold yellow]▶ Starte Ausfuehrung von '{target_script}' (Versuch {attempt}/{max_retries})[/bold yellow]")
        
        start_time = time.time()
        process = subprocess.Popen(
            [sys.executable, target_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate()
        elapsed = time.time() - start_time

        if process.returncode == 0:
            ui.show_info(f"[bold green]✓ '{target_script}' erfolgreich beendet in {elapsed:.2f}s![/bold green]")
            if stdout:
                print(stdout)
            break
        else:
            ui.show_error(f"[bold red]✗ Absturz nach {elapsed:.2f}s (Return Code {process.returncode})[/bold red]")
            print(stderr)
            
            ui.show_info("[bold magenta]🧠 Analysiere Crash und delegiere Fix an Sonu...[/bold magenta]")
            
            prompt = (
                f"Dein Cybernetic Watchdog hat festgestellt, dass das Skript `{target_script}` abgestuerzt ist.\n"
                f"Hier ist der Stderr Traceback:\n```\n{stderr}\n```\n\n"
                f"Nutze deine Tools (`read_file`, `edit_file`, `run_shell`), um den Fehler zu finden und den Code zu reparieren. "
                f"Keine Erklaerungen, fix es einfach chirurgisch."
            )
            
            try:
                # Run the agent turn headlessly
                client.run_agent_turn(prompt, ui, max_steps=10)
                ui.show_info("[bold green]✓ Sonu hat den Fix angewendet. Starte Skript neu...[/bold green]")
                time.sleep(2)
                attempt += 1
            except Exception as e:
                ui.show_error(f"Sonu konnte den Fehler nicht fixen: {e}")
                break

    if attempt > max_retries:
        ui.show_error(f"Watchdog hat nach {max_retries} Versuchen aufgegeben. Das System stabilisiert sich nicht.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python sonu_watchdog.py <script_to_run.py>")
        sys.exit(1)
        
    script = sys.argv[1]
    if not os.path.exists(script):
        print(f"Error: {script} not found.")
        sys.exit(1)
        
    run_watchdog(script)
