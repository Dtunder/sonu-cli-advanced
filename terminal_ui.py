from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich.syntax import Syntax
from rich import box
from rich.live import Live

# Icons je Tool fuer schnelle visuelle Orientierung.
_TOOL_ICONS = {
    "read_file": "📖",
    "list_dir": "📂",
    "search_files": "🔎",
    "write_file": "✏️",
    "edit_file": "🩹",
    "run_shell": "⚙️",
}


class TerminalUI:
    def __init__(self):
        self.console = Console()
        # YOLO-Mode: wenn True, werden schreibende/ausfuehrende Aktionen ohne
        # Rueckfrage automatisch ausgefuehrt (voller Zugriff, keine Bremsen).
        self.yolo = False

    def show_welcome(self):
        welcome_message = (
            "[bold cyan]Willkommen bei Sonu CLI — deinem autonomen Terminal-Agenten![/bold cyan]\n\n"
            "Sonu kann jetzt [bold]handeln[/bold], nicht nur reden: Dateien lesen & schreiben,\n"
            "Verzeichnisse durchsuchen und PowerShell-Befehle ausführen.\n"
            "Schreibende Aktionen werden dir vor der Ausführung zur Bestätigung vorgelegt.\n\n"
            "💡 Beschreibe eine Aufgabe in natürlicher Sprache — Sonu wählt die Werkzeuge selbst.\n"
            "💡 Nutze [yellow]/tools[/yellow] für die Werkzeugliste, [yellow]/help[/yellow] für alle Befehle.\n"
            "🔥 [red]/yolo[/red] oder Start mit [red]--yolo[/red]: voller Zugriff ohne Rückfragen.\n"
            "💡 Beende das CLI mit [bold red]/exit[/bold red] oder [bold red]exit[/bold red]."
        )
        self.console.print(Panel(
            welcome_message,
            title="✨ Sonu CLI",
            title_align="left",
            border_style="magenta",
            expand=False,
            box=box.ROUNDED
        ))

    def show_spinner(self, message="Sonu denkt nach..."):
        """Gibt ein Context-Manager Objekt für den Spinner zurück."""
        return self.console.status(f"[bold yellow]{message}[/bold yellow]", spinner="dots")

    def display_response(self, text):
        self.console.print("\n[bold magenta]✦ Sonu:[/bold magenta]")
        md = Markdown(text)
        self.console.print(md)
        self.console.print("\n" + "[dim]" + "-" * 50 + "[/dim]" + "\n")

    def display_stream(self, response_stream):
        """Zeigt die Antwort von Sonu live als gerendertes Markdown im Terminal an."""
        self.console.print("\n[bold magenta]✦ Sonu:[/bold magenta]")
        full_text = ""
        try:
            with Live(Markdown(full_text), console=self.console, refresh_per_second=15, transient=False) as live:
                for chunk in response_stream:
                    if chunk.text:
                        full_text += chunk.text
                        live.update(Markdown(full_text))
        except Exception as e:
            self.console.print(f"\n[bold red]Fehler beim Streamen:[/bold red] {str(e)}")
            
        self.console.print("\n" + "[dim]" + "-" * 50 + "[/dim]" + "\n")
        return full_text

    def show_error(self, error_message):
        self.console.print(Panel(
            f"[bold red]Fehler:[/bold red] {error_message}",
            title="⚠️ Systemfehler",
            title_align="left",
            border_style="red",
            expand=False,
            box=box.ROUNDED
        ))

    def show_info(self, info_message):
        self.console.print(f"\n[bold green]✓[/bold green] {info_message}\n")

    # --- Agent-spezifische Anzeige ------------------------------------------------

    def show_agent_thought(self, text):
        """Zeigt Zwischentext des Agenten (Plan/Begruendung), bevor Tools laufen."""
        self.console.print(f"\n[italic dim]🤔 {text}[/italic dim]\n")

    def _format_args(self, name, args):
        if name == "run_shell":
            return args.get("command", "")
        if name == "write_file":
            content = args.get("content", "")
            preview = content if len(content) <= 600 else content[:600] + "\n[... gekuerzt ...]"
            return f"Datei: {args.get('path', '?')}\n\n{preview}"
        if name == "edit_file":
            old = args.get("old_string", "")
            new = args.get("new_string", "")
            old_p = old if len(old) <= 300 else old[:300] + " [...]"
            new_p = new if len(new) <= 300 else new[:300] + " [...]"
            return f"Datei: {args.get('path', '?')}\n\n[- alt]\n{old_p}\n\n[+ neu]\n{new_p}"
        # read_file / list_dir / search_files: kompakte Key=Value-Darstellung.
        return ", ".join(f"{k}={v!r}" for k, v in args.items())

    def show_tool_call(self, name, args):
        icon = _TOOL_ICONS.get(name, "🔧")
        body = self._format_args(name, args)
        if name == "run_shell":
            renderable = Syntax(body, "powershell", theme="ansi_dark", word_wrap=True)
        else:
            renderable = body
        self.console.print(Panel(
            renderable,
            title=f"{icon} Tool-Aufruf: [bold]{name}[/bold]",
            title_align="left",
            border_style="cyan",
            expand=False,
            box=box.ROUNDED,
        ))

    def show_tool_result(self, name, result, rejected=False):
        style = "red" if rejected else "green"
        text = result if len(result) <= 1500 else result[:1500] + "\n[... gekuerzt ...]"
        self.console.print(Panel(
            f"[dim]{text}[/dim]",
            title=f"↳ Ergebnis: {name}",
            title_align="left",
            border_style=style,
            expand=False,
            box=box.ROUNDED,
        ))

    def confirm_action(self, name, args):
        """Fragt den Nutzer vor schreibenden/ausfuehrenden Aktionen. Standard = Nein.
        Im YOLO-Mode wird ohne Rueckfrage automatisch zugestimmt (nur sichtbar geloggt).
        """
        icon = _TOOL_ICONS.get(name, "🔧")
        if self.yolo:
            self.console.print(
                f"[bold red]🔥 YOLO[/bold red] [dim]auto-approve:[/dim] [bold]{name}[/bold]"
            )
            return True
        from prompt_toolkit import prompt as _prompt
        self.console.print(
            f"\n[bold yellow]{icon} Bestaetigung noetig:[/bold yellow] "
            f"Der Agent moechte [bold]{name}[/bold] ausfuehren."
        )
        try:
            answer = _prompt("   Ausfuehren? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        return answer in ("y", "yes", "j", "ja")

    def set_yolo(self, enabled: bool):
        """Schaltet den YOLO-Mode um und zeigt das Banner bzw. eine Bestaetigung."""
        self.yolo = enabled
        if enabled:
            self.show_yolo_banner()
        else:
            self.console.print("\n[bold green]✓ YOLO-Mode deaktiviert.[/bold green] "
                               "Schreibende Aktionen werden wieder bestaetigt.\n")

    def show_yolo_banner(self):
        self.console.print(Panel(
            "[bold red]🔥 YOLO-MODE AKTIV — VOLLER ZUGRIFF, KEINE RUECKFRAGEN 🔥[/bold red]\n\n"
            "Sonu fuehrt [bold]write_file, edit_file und run_shell ohne Bestaetigung[/bold] aus.\n"
            "Das schliesst potenziell destruktive Befehle ein (z.B. Loeschen, Ueberschreiben).\n"
            "Nutze das nur in einem Verzeichnis/Kontext, dem du vertraust.\n\n"
            "[dim]Mit [yellow]/yolo[/yellow] wieder ausschalten.[/dim]",
            title="⚠️  YOLO",
            title_align="left",
            border_style="red",
            expand=False,
            box=box.DOUBLE,
        ))

    def show_help(self):
        table = Table(
            title="Verfügbare Befehle",
            title_style="bold cyan",
            box=box.ROUNDED,
            header_style="bold magenta",
            expand=False
        )
        table.add_column("Befehl", style="yellow")
        table.add_column("Beschreibung", style="white")

        table.add_row("/help", "Zeigt diese Hilfsübersicht an.")
        table.add_row("/model", "Zeigt das aktuelle Modell an. Nutze '/model <name>', um das Modell zu wechseln.")
        table.add_row("/models", "Listet alle für dich verfügbaren Sonu-Modelle auf.")
        table.add_row("/history", "Zeigt den Pfad des aktuellen Logs und die Anzahl der Interaktionen.")
        table.add_row("/tools", "Listet die Agent-Werkzeuge auf, die Sonu selbststaendig nutzen kann.")
        table.add_row("/yolo", "Schaltet den YOLO-Mode um (voller Zugriff, keine Rueckfragen).")
        table.add_row("/exit", "Beendet das CLI sicher.")

        self.console.print(table)

    def show_tools(self):
        table = Table(
            title="Agent-Werkzeuge",
            title_style="bold cyan",
            box=box.ROUNDED,
            header_style="bold magenta",
            expand=False,
        )
        table.add_column("Werkzeug", style="yellow")
        table.add_column("Funktion", style="white")
        table.add_column("Sicherheit", style="white")
        confirm_label = "[red]YOLO: auto[/red]" if self.yolo else "[yellow]Bestaetigung[/yellow]"
        table.add_row("read_file", "Datei lesen", "[green]auto[/green]")
        table.add_row("list_dir", "Verzeichnis auflisten", "[green]auto[/green]")
        table.add_row("search_files", "Textsuche ueber Dateien", "[green]auto[/green]")
        table.add_row("write_file", "Datei schreiben/ueberschreiben", confirm_label)
        table.add_row("edit_file", "Eindeutige Textstelle ersetzen", confirm_label)
        table.add_row("run_shell", "PowerShell-Befehl ausfuehren", confirm_label)
        self.console.print(table)
        status = "[bold red]AN 🔥[/bold red]" if self.yolo else "[green]aus[/green]"
        self.console.print(f"\nYOLO-Mode: {status}  [dim](umschalten mit /yolo)[/dim]\n")
