import json
import os


STYLES = {
    "expert": (
        "Maximale technische Tiefe. Keine Grundlagen erklären. "
        "Direkt mit Code, Formeln, Implementierungsdetails. "
        "Shubham ist Mechatronik-Experte — auf Augenhöhe kommunizieren."
    ),
    "concise": (
        "Extrem kurz und präzise. Nur das Wesentliche. "
        "Keine Einleitungen, keine Zusammenfassungen. "
        "Code-first, Prosa minimal."
    ),
    "debug": (
        "Fokus auf Fehleranalyse. Immer: Wurzelursache zuerst, dann Fix, dann Validierung. "
        "Stack-Traces, Hypothesen und Tests zeigen. Cybernetic-Loop-Denken: "
        "Ist-Zustand → Soll-Zustand → Gap → Aktion → Validierung."
    ),
    "architect": (
        "System-Architektur-Perspektive. Denke in Modulen, Interfaces, Datenflüssen. "
        "Trade-offs, Downstream-Effekte, Skalierbarkeit zeigen. "
        "Diagramm-Beschreibungen und Strukturübersichten bevorzugen."
    ),
    "hft": (
        "High-Frequency-Trading-Experte. Latenz in µs denken. "
        "Fokus auf Orderbook-Mechanik, Execution-Algos, Pre-Trade Risk. "
        "Immer: Edge zuerst, dann Implementierung. Krypto und TradFi."
    ),
}

_STYLE_PATH = os.path.expanduser("~/.sonu/style.json")


class PersonalityEngine:
    def __init__(self):
        os.makedirs(os.path.dirname(_STYLE_PATH), exist_ok=True)
        self.active_style = self._load()

    def _load(self) -> str:
        if os.path.exists(_STYLE_PATH):
            try:
                with open(_STYLE_PATH, "r", encoding="utf-8") as f:
                    return json.load(f).get("style", "expert")
            except Exception:
                pass
        return "expert"

    def _save(self):
        with open(_STYLE_PATH, "w", encoding="utf-8") as f:
            json.dump({"style": self.active_style}, f)

    def set_style(self, name: str) -> str:
        if name not in STYLES:
            return f"Unbekannter Stil '{name}'. Verfügbar: {', '.join(STYLES)}"
        self.active_style = name
        self._save()
        return f"Stil '{name}' aktiviert und gespeichert."

    def get_style_instruction(self) -> str:
        return STYLES.get(self.active_style, STYLES["expert"])

    def list_styles(self) -> dict:
        return {k: v[:65] + "..." for k, v in STYLES.items()}
