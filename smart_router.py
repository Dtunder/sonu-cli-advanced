import re

_AGENT_SIGNALS = [
    r'\b(schreib|erstell|lauf|f[uü]hr|[äa]nder|l[oö]sch|edit|refactor|fix|repair|deploy|build|install|run|create|delete|move|copy|start|stop|kill|generate|bau)\b',
    r'\b(datei|ordner|verzeichnis|skript|script|file|folder|directory)\b',
    r'\.(py|js|ts|json|yaml|yml|md|txt|csv|sh|bat|ps1|html|css|sql|env)\b',
    r'[/\\]\w',
    r'\b(shell|terminal|powershell|cmd|bash|befehl|command|git|npm|pip|docker|python)\b',
    r'`[^`]+`',
]

_KNOWLEDGE_SIGNALS = [
    r'^(was ist|was sind|was bedeutet|erkl[äa]r|warum|wie funktioniert|wann|wo ist)',
    r'^(what is|what are|explain|why|how does|how do|when|where)',
    r'^(ist |sind |kann |gibt es |hat |haben )',
]

# Signale für hohe Komplexität → MoA lohnt sich
_COMPLEX_SIGNALS = [
    r'\b(analysier|vergleich|optimier|evaluier|bewert|entscheid|architektur|strategie|refactor|implementier|redesign|migrier)',
    r'\b(analyse|compare|optimize|evaluate|decide|architecture|strategy|implement|design|migrate)',
    r'\b(vor.*nach.*|besser.*schlechter|option.*[12]|welche.*l[oö]sung|best practice|trade.?off)\b',
    r'```',          # Code-Block → komplexe Aufgabe
    r'\?.*\?',       # Mehrere Fragen in einer Nachricht
]

# Signale für niedrige Komplexität → MoA überspringen
_SIMPLE_SIGNALS = [
    r'^(ok|ja|nein|danke|super|gut|alles klar|verstanden|weiter|stop|zeig|list|ls|pwd)',
    r'^(yes|no|ok|thanks|continue|show|list|go|next|done)',
    r'^(was kostet|wie heißt|wann|wo|wer)',
]


class SmartRouter:
    def classify(self, text: str) -> str:
        """Gibt 'agent' oder 'knowledge' zurück."""
        t = text.strip()
        for pat in _AGENT_SIGNALS:
            if re.search(pat, t, re.IGNORECASE):
                return "agent"
        for pat in _KNOWLEDGE_SIGNALS:
            if re.search(pat, t, re.IGNORECASE):
                return "knowledge"
        return "agent"

    def needs_moa(self, text: str) -> bool:
        """Entscheidet ob Mixture-of-Agents sinnvoll ist.
        True  → komplex, parallele Cheap-Agents bringen Mehrwert
        False → einfach/kurz, direkt zu 3.5-flash
        """
        t = text.strip()
        words = len(t.split())

        # Einfache Kommandos → kein MoA (höchste Priorität)
        for pat in _SIMPLE_SIGNALS:
            if re.search(pat, t, re.IGNORECASE):
                return False

        # Explizit komplexe Signale → immer MoA (auch kurze Eingaben wie "refactor x.py")
        for pat in _COMPLEX_SIGNALS:
            if re.search(pat, t, re.IGNORECASE):
                return True

        # Kurze neutrale Eingaben ohne komplexe Signale → kein MoA
        if words < 10:
            return False

        # Lange Nachrichten → MoA
        if words > 60 or len(t) > 400:
            return True

        return False

    def preferred_provider(self, text: str, providers: list) -> str:
        """Gibt den bevorzugten ersten Provider zurück."""
        if self.classify(text) == "knowledge" and "groq" in providers:
            return "groq"
        return providers[0] if providers else "gemini"
