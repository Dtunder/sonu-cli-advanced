import os
import threading
import concurrent.futures
import logging
from typing import Dict, List

# Set up logging
logger = logging.getLogger(__name__)

class SwarmConsensus:
    """Fragt mehrere LLM-Provider parallel ab und gibt die beste Antwort zurück.
    Scoring: Länge × 0.3 + Code-Blöcke × 50 + einzigartiges Vokabular × 0.5
    """

    # Provider die im Swarm laufen sollen (in Priorität)
    SWARM_PROVIDERS = ["gemini", "groq"]

    def __init__(self, sonu_client):
        self.sonu_client = sonu_client

    def _available_providers(self):
        """Ruft die verfügbaren Provider ab."""
        import providers as prov_module
        available = []
        for p in self.SWARM_PROVIDERS:
            prov_info = prov_module.get_provider(p)
            if not prov_info:
                continue
            if prov_info["env_var"] is None or os.getenv(prov_info["env_var"]):
                available.append(p)
        return available

    def _query_gemini(self, topic: str, results: Dict, lock: threading.Lock):
        """Abfrage bei Gemini."""
        try:
            c = self.sonu_client
            if not c.client:
                return
            resp = c.client.models.generate_content(
                model=c.model_name,
                contents=topic
            )
            text = (resp.text or "").strip()
            with lock:
                results["gemini"] = {"text": text, "score": self._score(text)}
        except Exception as e:
            with lock:
                results["gemini"] = {"text": "", "score": 0, "error": str(e)}

    def _query_openai_compat(self, provider: str, topic: str, results: Dict, lock: threading.Lock):
        """Abfrage bei OpenAI-kompatiblen Agenten."""
        try:
            c = self.sonu_client
            if provider not in c.oa_agents:
                import providers as prov_module
                from openai_agent import OpenAICompatibleAgent
                prov_info = prov_module.get_provider(provider)
                c.oa_agents[provider] = OpenAICompatibleAgent(provider, prov_info["default_model"], c)
            agent = c.oa_agents[provider]
            resp = agent.client.chat.completions.create(
                model=agent.model,
                messages=[{"role": "user", "content": topic}],
                max_tokens=2048,
                timeout=30,
            )
            text = (resp.choices[0].message.content or "").strip()
            with lock:
                results[provider] = {"text": text, "score": self._score(text)}
        except Exception as e:
            with lock:
                results[provider] = {"text": "", "score": 0, "error": str(e)}

    @staticmethod
    def _score(text: str) -> float:
        """Qualitätsscore: Struktur + Vollständigkeit + Präzision + Korrektheit.
        Bestraft Halluzinations-Marker und leere Floskeln."""
        if not text:
            return 0.0

        words = text.split()
        n = len(words)
        if n == 0:
            return 0.0

        # Basis: logarithmische Länge (lange Antworten gut, aber kein linearer Vorteil)
        import math
        score = math.log(n + 1) * 10

        # Struktur-Bonus: Überschriften, Listen, Code
        score += text.count("\n#") * 8          # Markdown-Überschriften
        score += text.count("\n-") * 2          # Listen
        score += text.count("\n*") * 2
        score += text.count("```") * 15         # Code-Blöcke (stark gewichtet)
        score += text.count("`") * 1            # Inline-Code

        # Vollständigkeit: beantwortet Fragen mit konkreten Infos
        concrete = ["beispiel", "example", "weil", "because", "daher", "therefore",
                    "schritt", "step", "zuerst", "first", "dann", "then"]
        score += sum(2 for w in concrete if w in text.lower())

        # Präzision: Zahlen und Fakten sind gut
        import re
        score += len(re.findall(r'\b\d+\.?\d*\b', text)) * 0.5

        # Halluzinations-Malus: vage Formulierungen
        vague = ["könnte sein", "vielleicht", "eventuell", "ich bin nicht sicher",
                 "i'm not sure", "might be", "possibly", "ich glaube vielleicht"]
        score -= sum(5 for p in vague if p in text.lower())

        # Wiederholungs-Malus: wenn viele Wörter identisch wiederholt werden
        unique_ratio = len(set(w.lower() for w in words)) / n
        if unique_ratio < 0.4:
            score *= 0.7  # sehr repetitiver Text → bestrafen

        return max(score, 0.0)

    def run(self, topic: str) -> Dict:
        """Befragt alle verfügbaren Provider parallel und gibt die beste Antwort zurück."""
        providers_list = self._available_providers()
        results: Dict[str, dict] = {}
        lock = threading.Lock()

        threads = []
        for provider in providers_list:
            if provider == "gemini":
                t = threading.Thread(target=self._query_gemini, args=(topic, results, lock))
            else:
                t = threading.Thread(target=self._query_openai_compat, args=(provider, topic, results, lock))
            t.start()
            threads.append(t)

        for t in threads:
            t.join(timeout=60)

        scores = {}
        errors = {}
        best_text = ""
        best_score = -1.0
        winner = None
        for provider, data in results.items():
            if data.get("error"):
                errors[provider] = data["error"]
                continue
            score = data.get("score", 0)
            scores[provider] = score
            if score > best_score:
                best_score = score
                best_text = data.get("text", "")
                winner = provider

        return {
            "best": best_text,
            "winner": winner,
            "scores": scores,
            "errors": errors,
        }