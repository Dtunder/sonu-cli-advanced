"""Plan Mode — agent presents a plan, user approves before any tools run.

When active:
- Agent is instructed to ONLY produce a plan (no tool calls)
- User sees plan and types 'ja'/'yes'/'approve' to proceed or 'nein'/'no'/'abort' to cancel
- On approval: plan mode deactivates and the same prompt re-runs with tools enabled
"""

from __future__ import annotations


class PlanMode:
    def __init__(self):
        self.active = False
        self._pending_prompt: str = None

    def enter(self, prompt: str = None) -> None:
        self.active = True
        self._pending_prompt = prompt

    def exit(self) -> str | None:
        self.active = False
        prompt = self._pending_prompt
        self._pending_prompt = None
        return prompt

    def get_system_addon(self) -> str:
        """Extra instruction injected when plan mode is active."""
        return (
            "\n\n=== PLAN MODE AKTIV ===\n"
            "Produziere NUR einen strukturierten Implementierungsplan (Schritte, betroffene Dateien, "
            "erwartete Änderungen). Führe KEINE Tools aus und schreibe KEINEN Code. "
            "Warte auf explizite Nutzer-Genehmigung bevor du handelst.\n"
        )

    def is_approval(self, text: str) -> bool:
        t = text.strip().lower()
        return t in ("ja", "yes", "j", "y", "approve", "ok", "weiter", "go", "los", "proceed")

    def is_rejection(self, text: str) -> bool:
        t = text.strip().lower()
        return t in ("nein", "no", "n", "abort", "abbruch", "stop", "cancel")
