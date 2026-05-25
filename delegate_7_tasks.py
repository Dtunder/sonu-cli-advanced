import os
import sys
import subprocess
import time

# terminal encoding
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

class MockConsole:
    def print(self, msg, *args, **kwargs):
        print(msg)

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    console = Console()
except ImportError:
    console = MockConsole()

TASKS = [
    {
        "id": 1,
        "name": "SQLite Token Pricing & Cost Tracker",
        "description": "SQLite-basierte Erfassung von Token-Mengen, Kosten in USD und Latenzen ueber alle 9 Keys.",
        "prompt": "Task 1 for Dtunder/sonu-cli-advanced: Implement a persistent SQLite-based token usage and cost tracker in storage.py. Create a new table 'token_logs' with columns: timestamp, provider, model, prompt_tokens, completion_tokens, latency_ms, estimated_cost_usd. Add a log_token_usage method in storage.py and hook it into sonu_client.py and openai_agent.py at the end of every completion/agent turn."
    },
    {
        "id": 2,
        "name": "Context Compression & Semantic Pruning",
        "description": "Dynamisches Verlaufs-Pruning und semantische Token-Komprimierung zur Vermeidung von Quotas.",
        "prompt": "Task 2 for Dtunder/sonu-cli-advanced: Create a new file context_compressor.py and integrate it into openai_agent.py and sonu_client.py. If the conversation history (system prompt + user/assistant/tool messages) exceeds 70% of the active model's token limit, dynamically compress the oldest 30% of user/assistant messages into a single summarized 'system memory' message, leaving the overall system instruction intact."
    },
    {
        "id": 3,
        "name": "Local-Cloud Hybrid Orchestrator",
        "description": "Kernfunktionen von agent_orchestrator.py zur asynchronen Ausfuehrung lokaler Subprozesse.",
        "prompt": "Task 3 for Dtunder/sonu-cli-advanced: Create a new file agent_orchestrator.py. Implement a class 'LocalCloudOrchestrator' that allows Sonu to spawn parallel local Python subprocesses to execute diagnostics, run tests, or search directories concurrently, and aggregate their results asynchronously while letting Google Jules handle heavy cloud coding tasks."
    },
    {
        "id": 4,
        "name": "Astro-Cybernetic Brain Skill",
        "description": "Erstelle ein Experten-Skill-Profil 'astro-cybernetic', das PID/LQR Zustandsraummodelle integriert.",
        "prompt": "Task 4 for Dtunder/sonu-cli-advanced: Create a new mechatronic expert skill file skills/astro-cybernetic.md. Detail C1-level mechatronic state-space control loop guidelines (LQR, PID feedback) paired with astrological planetary transit formulas (calculating optimal agent decision intervals based on Mercury transits) for cybernetic thinking."
    },
    {
        "id": 5,
        "name": "Git Branching & Automated Pull Request Orchestration",
        "description": "Vollautomatischer Git-Manager zur Kapselung von Code-Aenderungen in Branches mit standardisierten Auto-PRs.",
        "prompt": "Task 5 for Dtunder/sonu-cli-advanced: Implement Git branching and automated Pull Request orchestration in tools.py. Add new tools: 'create_git_branch(branch_name)', 'commit_git_changes(message)', and 'create_github_pull_request(title, body)'. Utilize standard subprocess calls or git commands, ensuring proper error handling and clean markdown PR templates."
    },
    {
        "id": 6,
        "name": "Consensual Multi-Model Group Debate Engine",
        "description": "Gruppen-Debatten-Feature (/debate <prompt>), bei dem Gemini, Groq und OpenRouter abstimmen.",
        "prompt": "Task 6 for Dtunder/sonu-cli-advanced: Create a new file debate_engine.py. Implement a class 'GroupDebateEngine' that queries Gemini, Groq, and OpenRouter in parallel using threading. The engine should submit a prompt, retrieve proposed solutions, have each model critique the other solutions, and calculate a consensus matrix score to select the best option."
    },
    {
        "id": 7,
        "name": "Offline Ollama / Local Model Router",
        "description": "Lokales Mocking- und Fallback-Interface zu Ollama/Llama.cpp fuer den Offline-Betrieb.",
        "prompt": "Task 7 for Dtunder/sonu-cli-advanced: Add a local offline model router in providers.py and sonu_client.py. If no internet connection is detected, or if all API keys in .env return connection errors, dynamically fall back to a locally running Ollama API server (defaulting to model 'llama3') at http://localhost:11434/v1."
    }
]

def main():
    if hasattr(console, "print") and not isinstance(console, MockConsole):
        console.print(Panel.fit("[bold cyan]🚀 SONU CLI ADVANCED — JULES ULTRA-EDITION LAUNCHER 🚀[/bold cyan]\n[dim]Starte 7 parallele High-Impact-Aufgaben fuer das Repository Dtunder/sonu-cli-advanced...[/dim]", style="blue"))
        
        table = Table(title="Übersicht der 7 High-End-Aufgaben für Jules", title_style="bold yellow", show_header=True, header_style="bold magenta")
        table.add_column("ID", justify="center", style="cyan")
        table.add_column("Task-Name", style="bold green")
        table.add_column("Mechatronische Beschreibung", style="white")
        
        for t in TASKS:
            table.add_row(str(t["id"]), t["name"], t["description"])
            
        console.print(table)
    else:
        print("=== SONU CLI ADVANCED — JULES ULTRA-EDITION LAUNCHER ===")
        for t in TASKS:
            print(f"[{t['id']}] {t['name']}: {t['description']}")
            
    print("\n[INFO] Bereite Start der 7 Jules-Remote-Sitzungen vor...")
    time.sleep(2)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    delegator_path = os.path.join(script_dir, "jules_delegator.py")
    
    if not os.path.exists(delegator_path):
        print(f"[ERROR] jules_delegator.py nicht gefunden unter {delegator_path}!")
        sys.exit(1)
        
    launched_tasks = []
    
    for t in TASKS:
        print(f"\n-------------------------------------------------------------")
        print(f"[STARTING] Task {t['id']}: {t['name']}")
        print(f"-------------------------------------------------------------")
        
        cmd = [sys.executable, delegator_path, t["prompt"]]
        try:
            log_dir = os.path.join(script_dir, "logs")
            os.makedirs(log_dir, exist_ok=True)
            log_file_path = os.path.join(log_dir, f"jules_task_{t['id']}.log")
            
            log_file = open(log_file_path, "w", encoding="utf-8")
            proc = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                cwd=script_dir
            )
            
            launched_tasks.append({
                "id": t["id"],
                "name": t["name"],
                "proc": proc,
                "log_file": log_file_path
            })
            print(f"[OK] Task {t['id']} im Hintergrund gestartet! Logs unter: logs/jules_task_{t['id']}.log")
            time.sleep(4)
        except Exception as e:
            print(f"[FAILED] Fehler beim Starten von Task {t['id']}: {e}")
            
    print("\n=============================================================")
    print("STATUS DER JULES DELEGIERUNGEN:")
    print("=============================================================")
    for lt in launched_tasks:
        pid = lt["proc"].pid
        print(f"  • Task {lt['id']} ('{lt['name']}'): LAUFEND (PID: {pid})")
        
    print("\n[INFO] Alle 7 Aufgaben wurden erfolgreich an Jules übergeben!")
    print("[INFO] Die Google Jules-API verarbeitet die Aufgaben nun im Hintergrund des Repositories.")
    print("[INFO] Nutze die logs/jules_task_<ID>.log-Dateien, um den Live-Status zu überwachen.")

if __name__ == "__main__":
    main()
