import time
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich import box

_TOOL_ICONS = {
    "read_file": "📖",
    "list_dir": "📂",
    "glob_files": "🌐",
    "grep_search": "🔎",
    "replace": "🩹",
    "write_file": "✏️",
    "run_shell": "⚙️",
    "web_fetch": "🌐",
    "google_search": "🔍",
    "ask_user": "❓",
    "update_topic": "📖",
    "delegate_to_subagent": "🤖",
}


class TerminalUI:
    def __init__(self):
        self.console = Console()
        self.yolo = False

    def show_agent_status(self, action_description):
        self.console.print(f"[dim]  {action_description}[/dim]")

    def show_welcome(self):
        self.console.print()
        self.console.print("[bold cyan]Sonu CLI[/bold cyan]  [dim]gemini-2.5-flash · multi-provider · 15 keys[/dim]")
        self.console.print("[dim]/help für Befehle · /yolo für Auto-Approve · Strg+C zum Beenden[/dim]")
        self.console.print("[dim]" + "─" * 50 + "[/dim]")
        self.console.print()

    def show_spinner(self, message="Lade..."):
        """Context manager für kurze blocking ops (z.B. /models laden)."""
        return self.console.status(f"[dim]{message}[/dim]", spinner="dots")

    def start_thinking(self, message="Denke nach..."):
        clean = message.replace("[yellow]", "").replace("[/yellow]", "").replace("[dim]", "").replace("[/dim]", "")
        self.console.print(f"[dim]⠋ {clean}[/dim]")

    def update_status(self, message):
        clean = message.replace("[yellow]", "").replace("[/yellow]", "").replace("[dim]", "").replace("[/dim]", "")
        self.console.print(f"[dim]  {clean}[/dim]")

    def stop_thinking(self):
        pass  # kein persistenter spinner — nichts zu stoppen

    def _pause_thinking(self):
        pass

    def _resume_thinking(self):
        pass

    def display_response(self, text):
        self.console.print()
        self.console.print("[bold magenta]Sonu[/bold magenta]")
        self.console.print(Markdown(text))
        self.console.print()

    def display_stream(self, response_stream):
        from rich.live import Live
        self.console.print()
        self.console.print("[bold magenta]Sonu[/bold magenta]")
        full_text = ""
        try:
            with Live(Markdown(""), console=self.console, refresh_per_second=15, transient=False) as live:
                for chunk in response_stream:
                    if hasattr(chunk, "text") and chunk.text:
                        full_text += chunk.text
                        live.update(Markdown(full_text))
        except Exception as e:
            self.console.print(f"[bold red]Error:[/bold red] {str(e)}")
        self.console.print()
        return full_text

    def show_error(self, error_message):
        self.console.print(f"\n[bold red]✗ {error_message}[/bold red]\n")

    def show_info(self, info_message):
        self.console.print(f"[green]✓[/green] {info_message}")

    def show_topic(self, title, summary, strategic_intent=None):
        self.console.print(f"\n[bold cyan]📖 {title}[/bold cyan]")
        self.console.print(f"[dim]{summary}[/dim]")
        if strategic_intent:
            self.console.print(f"[dim italic]Intent: {strategic_intent}[/dim italic]")
        self.console.print()

    def show_tool_call(self, name, args):
        icon = _TOOL_ICONS.get(name, "🔧")
        arg_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
        if len(arg_str) > 100:
            arg_str = arg_str[:97] + "..."
        self._tool_start_time = time.monotonic()
        self.console.print(f"[dim]{icon} [bold]{name}[/bold]({arg_str})[/dim]", end="")

    def show_tool_result(self, name, result, rejected=False):
        elapsed = time.monotonic() - getattr(self, "_tool_start_time", time.monotonic())
        duration = f"[dim] {elapsed*1000:.0f}ms[/dim]"
        if rejected:
            self.console.print(f"\r[dim]{_TOOL_ICONS.get(name,'🔧')} [bold]{name}[/bold][/dim] [red]✗ abgelehnt[/red]{duration}")
        else:
            lines = (result or "").count("\n") + 1 if result else 0
            hint = f"[dim] ({lines} Zeilen)[/dim]" if lines > 1 else ""
            self.console.print(f" [dim]✓[/dim]{hint}{duration}")

    def confirm_action(self, name, args):
        if self.yolo:
            self.console.print(f"[bold red]YOLO[/bold red] [dim]auto-approve:[/dim] {name}")
            return True
        from prompt_toolkit import prompt as _prompt
        self.console.print(f"\n[bold yellow]⚠ Bestätigung:[/bold yellow] [bold]{name}[/bold]?")
        try:
            answer = _prompt("  [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        return answer in ("y", "yes", "j", "ja")

    def prompt_user(self, text):
        from prompt_toolkit import prompt as _prompt
        self.console.print(f"\n[bold cyan]? {text}[/bold cyan]")
        try:
            return _prompt("   > ").strip()
        except (EOFError, KeyboardInterrupt):
            return ""

    def set_yolo(self, enabled: bool):
        self.yolo = enabled
        if enabled:
            self.console.print("\n[bold red]YOLO-MODE AKTIVIERT[/bold red] [dim](keine Rückfragen)[/dim]\n")
        else:
            self.console.print("\n[green]✓ YOLO-Mode deaktiviert.[/green]\n")

    def show_help(self):
        self.console.print("\n[bold cyan]Befehle:[/bold cyan]")
        table = Table(box=box.MINIMAL, show_header=False, padding=(0, 2))
        table.add_column("Cmd", style="yellow")
        table.add_column("Desc", style="dim")
        cmds = [
            ("/help", "Hilfe"),
            ("/status", "Systemstatus"),
            ("/clear", "Terminal leeren"),
            ("/exit", "Beenden"),
            ("/provider [name]", "Backend wechseln"),
            ("/model [name]", "Modell wechseln"),
            ("/yolo", "Auto-Approve umschalten"),
            ("/skills", "Experten-Skills"),
            ("/keys", "Key-Pool Status"),
            ("/rotator", "Key-Rotator Status"),
        ]
        for c, d in cmds:
            table.add_row(c, d)
        self.console.print(table)
        self.console.print()

    def show_status_snapshot(self, provider, model, yolo, active_skill, running_tasks, interaction_count):
        self.console.print(f"\n[bold cyan]Status[/bold cyan]")
        self.console.print(f"  Backend   [magenta]{provider}[/magenta]  [dim]{model}[/dim]")
        self.console.print(f"  Skill     [yellow]{active_skill or 'Baseline'}[/yellow]")
        self.console.print(f"  YOLO      {'[red]ON[/red]' if yolo else '[green]OFF[/green]'}")
        self.console.print(f"  Tasks     [cyan]{running_tasks}[/cyan]")
        self.console.print(f"  Session   {interaction_count} Interaktionen")
        self.console.print()

    def show_tools(self):
        self.console.print("\n[bold cyan]Tools:[/bold cyan]")
        tool_list = [f"{_TOOL_ICONS.get(k, '🔧')} {k}" for k in _REG_TOOL_NAMES]
        self.console.print(f"  [dim]{', '.join(tool_list)}[/dim]\n")


_REG_TOOL_NAMES = ["read_file", "list_dir", "glob_files", "grep_search", "replace", "write_file", "run_shell", "web_fetch", "google_search", "delegate_to_subagent"]
