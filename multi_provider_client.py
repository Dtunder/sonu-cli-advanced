import os
import json
import urllib.request
import sqlite3
from dotenv import load_dotenv

class ArbitrageOptimizer:
    def __init__(self, db_path="sonu.db"):
        self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_path)
        self.provider_stats = {}
        # Base costs in USD per 1k tokens
        self.base_costs = {
            "groq": 0.0001,
            "xai": 0.005,
            "gemini": 0.007,
            "openrouter": 0.001,
            "ollama": 0.0,
            "huggingface": 0.0005
        }
        # Provider capabilities mapping to max reasoning depth
        # 1: Low (Minor ops, searches)
        # 2: Medium (Fast edits, simple logic)
        # 3: High (Heavy AST-refactoring, architecture)
        self.provider_capability = {
            "ollama": 1,
            "groq": 2,
            "huggingface": 2,
            "openrouter": 2,
            "xai": 3,
            "gemini": 3
        }

    def _update_stats(self):
        """Fetches latest real-time token consumption and average latency from local db."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                # Fetch average latency and token usage by provider
                c.execute('''
                    SELECT provider, AVG(latency_ms), AVG(prompt_tokens + completion_tokens)
                    FROM token_logs
                    GROUP BY provider
                ''')
                rows = c.fetchall()
                for row in rows:
                    provider, avg_lat, avg_tokens = row
                    cost_per_1k = self.base_costs.get(provider, 0.01)
                    self.provider_stats[provider] = {
                        "avg_latency_ms": avg_lat or 1000.0,
                        "avg_tokens": avg_tokens or 0.0,
                        "cost_per_1k": cost_per_1k,
                        "estimated_avg_cost": (avg_tokens or 0.0) / 1000.0 * cost_per_1k
                    }
        except Exception:
            pass

    def get_task_depth(self, prompt: str) -> int:
        """Dynamically calculates the required reasoning depth based on prompt analysis."""
        prompt_lower = prompt.lower()

        high_complexity_keywords = ["refactor", "architect", "ast", "rewrite", "complex", "design", "plan", "debug deep", "heavy"]
        low_complexity_keywords = ["search", "find", "list", "dir", "regex", "minor", "typo", "where is"]

        if any(keyword in prompt_lower for keyword in high_complexity_keywords):
            return 3 # High
        elif any(keyword in prompt_lower for keyword in low_complexity_keywords):
            return 1 # Low
        else:
            return 2 # Medium

    def route_task(self, prompt: str, available_providers: list) -> str:
        """
        Knapsack-based optimization logic to minimize financial overhead while meeting reasoning needs.
        Returns the optimal provider name.
        """
        self._update_stats()
        required_depth = self.get_task_depth(prompt)

        best_provider = None
        best_score = -float('inf')

        for provider in available_providers:
            cap = self.provider_capability.get(provider, 2)
            if cap < required_depth:
                continue # Skip providers incapable of handling the task depth

            stats = self.provider_stats.get(provider, {})
            cost = stats.get("cost_per_1k", self.base_costs.get(provider, 0.01))
            latency = stats.get("avg_latency_ms", 2000.0)

            # Objective: Maximize (Capability) while minimizing (Cost + Latency)
            # Cost heavily weighted for arbitrage
            # But if a model meets the required depth perfectly, we should heavily prefer it over
            # ones that over-qualify if they are more expensive.

            # Since capability 1 (Ollama) has 0 cost, it should win if depth == 1.
            cost_penalty = cost * 10000
            latency_penalty = latency / 1000.0

            # Prefer models that match the depth, or penalize overqualified ones slightly
            # so cheaper models matching the depth win.
            depth_diff = cap - required_depth

            # Base score depends on capability, but we want to maximize efficiency:
            # If required_depth == 1, cap 1 gives score 10. cap 2 gives score 20, but we subtract cost/latency.
            # To ensure Ollama wins for depth 1, let's just make the score heavily dependent on hitting the depth
            # without paying for excess.
            efficiency_bonus = 0
            if depth_diff == 0:
                efficiency_bonus = 50  # Big bonus for exact match

            score = efficiency_bonus - cost_penalty - latency_penalty

            if score > best_score:
                best_score = score
                best_provider = provider

        # Fallback to the first available if none perfectly match
        if not best_provider and available_providers:
            return available_providers[0]

        return best_provider


class MultiProviderClient:
    def __init__(self):
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        load_dotenv(env_path, override=True)
        self.xai_key = os.getenv("XAI_API_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY")
        self.optimizer = ArbitrageOptimizer()

    def get_headers_and_url(self, provider):
        if provider == "xai":
            if not self.xai_key:
                raise ValueError("XAI_API_KEY fehlt in deiner .env-Datei!")
            return {
                "Authorization": f"Bearer {self.xai_key}",
                "Content-Type": "application/json"
            }, "https://api.x.ai/v1/chat/completions"
            
        elif provider == "groq":
            if not self.groq_key:
                raise ValueError("GROQ_API_KEY fehlt in deiner .env-Datei!")
            return {
                "Authorization": f"Bearer {self.groq_key}",
                "Content-Type": "application/json"
            }, "https://api.groq.com/openai/v1/chat/completions"
            
        elif provider == "openrouter":
            if not self.openrouter_key:
                raise ValueError("OPENROUTER_API_KEY fehlt in deiner .env-Datei!")
            return {
                "Authorization": f"Bearer {self.openrouter_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/Dtunder/sonu-cli-advanced",
                "X-Title": "Sonu CLI Advanced"
            }, "https://openrouter.ai/api/v1/chat/completions"
            
        else:
            raise ValueError(f"Unbekannter Provider: {provider}")

    def send_stream(self, provider, model, prompt, system_instruction=None):
        """Sendet eine Stream-Anfrage an den Provider mit silent exponential backoff."""
        import time
        headers, url = self.get_headers_and_url(provider)
        
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        payload_data = {
            "model": model,
            "messages": messages,
            "stream": True
        }
        
        # OpenRouter-spezifische kostenlose Modelle muessen ggf. vollstaendigen Pfad haben
        payload = json.dumps(payload_data).encode("utf-8")
        
        backoff_schedule = [2, 4, 8]
        for attempt in range(len(backoff_schedule) + 1):
            try:
                req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
                response = urllib.request.urlopen(req, timeout=30)
                
                def chunk_generator():
                    buffer = ""
                    # Stream zeilenweise parsen
                    for line_bytes in response:
                        line = line_bytes.decode("utf-8", errors="replace")
                        buffer += line
                        while "\n" in buffer:
                            curr_line, buffer = buffer.split("\n", 1)
                            curr_line = curr_line.strip()
                            if not curr_line:
                                continue
                            if curr_line.startswith("data:"):
                                data_str = curr_line[5:].strip()
                                if data_str == "[DONE]":
                                    break
                                try:
                                    data_json = json.loads(data_str)
                                    choices = data_json.get("choices", [])
                                    if choices:
                                        delta = choices[0].get("delta", {})
                                        content = delta.get("content", "")
                                        if content:
                                            # Mock-Klasse fuer Rich-Live Rendering (.text)
                                            class MockChunk:
                                                def __init__(self, text):
                                                    self.text = text
                                            yield MockChunk(content)
                                except Exception:
                                    pass
                return chunk_generator()
                
            except urllib.error.HTTPError as exc:
                if exc.code in (429, 503, 500, 502, 504) and attempt < len(backoff_schedule):
                    time.sleep(backoff_schedule[attempt])
                    continue
                body = exc.read().decode("utf-8", errors="replace")
                raise Exception(f"HTTP {exc.code} bei {provider.upper()} API-Anfrage: {body}")
            except Exception as e:
                if attempt < len(backoff_schedule):
                    time.sleep(backoff_schedule[attempt])
                    continue
                raise Exception(f"Fehler bei {provider.upper()} API-Anfrage: {str(e)}")
