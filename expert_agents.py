import asyncio
import logging

logger = logging.getLogger(__name__)


class SpecializedAgent:
    def __init__(self, role: str, persona_prompt: str, sonu_client):
        self.role = role
        self.persona_prompt = persona_prompt
        self.sonu_client = sonu_client
        # Wir nutzen den ArbitrageOptimizer um automatisch den besten Provider für den Experten zu wählen
        from multi_provider_client import ArbitrageOptimizer

        self.optimizer = ArbitrageOptimizer()
        import providers
        import os

        self.active_providers = []
        for p in providers.list_providers():
            prov_info = providers.get_provider(p)
            if prov_info["env_var"] is None or os.getenv(prov_info["env_var"]):
                self.active_providers.append(p)

    async def analyze(self, task: str) -> str:
        provider = self.optimizer.route_task(task, self.active_providers) or "gemini"

        loop = asyncio.get_running_loop()

        def _sync_call():
            from openai_agent import OpenAICompatibleAgent
            import providers

            prov_info = providers.get_provider(provider)
            model = prov_info["default_model"]

            if provider == "gemini":
                from google import genai
                import os

                api_key = os.getenv("GEMINI_API_KEY")
                client = genai.Client(api_key=api_key)
                resp = client.models.generate_content(
                    model=model, contents=f"{self.persona_prompt}\n\nTask: {task}"
                )
                return resp.text
            else:
                agent = OpenAICompatibleAgent(provider, model, self.sonu_client)
                messages = [
                    {"role": "system", "content": self.persona_prompt},
                    {"role": "user", "content": task},
                ]
                resp = agent.client.chat.completions.create(
                    model=model, messages=messages
                )
                return resp.choices[0].message.content

        try:
            result = await loop.run_in_executor(None, _sync_call)
            return f"[{self.role}] ({provider}):\n{result}"
        except Exception as e:
            logger.error(f"Error in {self.role}: {e}")
            return f"[{self.role}] Failed: {e}"


class MixtureOfExperts:
    def __init__(self, sonu_client, ui=None):
        self.sonu_client = sonu_client
        self.ui = ui
        self.experts = [
            SpecializedAgent(
                "Performance & Stability Architect",
                "You are an expert software architect obsessed with performance, memory safety, and preventing OOM crashes. Analyze the task and propose hyper-optimized solutions.",
                sonu_client,
            ),
            SpecializedAgent(
                "Security & Logic Auditor",
                "You are a paranoid security auditor. You look for vulnerabilities, edge cases, race conditions, and logic flaws in the task description or code. Provide safe, robust solutions.",
                sonu_client,
            ),
            SpecializedAgent(
                "Clean Code & Maintainability Guru",
                "You are a clean code advocate. You focus on readability, modularity, DRY, SOLID principles, and testability. How should this task be structured perfectly?",
                sonu_client,
            ),
        ]

    async def run_expert_panel(self, task: str) -> str:
        if self.ui:
            self.ui.show_info(f"Assembling Mixture of Experts for: '{task[:50]}...'")
            self.ui.show_agent_thought(
                "Experts are analyzing the problem in parallel..."
            )

        tasks = [asyncio.create_task(expert.analyze(task)) for expert in self.experts]
        results = await asyncio.gather(*tasks)

        valid_results = [
            r for r in results if not r.startswith("[") or "Failed" not in r
        ]

        if not valid_results:
            return "Expert panel failed to generate any insights."

        if self.ui:
            self.ui.show_agent_thought(
                "Synthesizing expert opinions into master plan..."
            )

        synthesis_prompt = f"Original Task: {task}\n\nHere are the independent analyses from the Mixture of Experts panel:\n"
        for res in valid_results:
            synthesis_prompt += f"\n{res}\n"

        synthesis_prompt += "\n\nAs the Master Synthesizer, fuse these distinct expert perspectives into one definitive, actionable, and comprehensive solution plan or code artifact. Do not just summarize; integrate their best ideas."

        synthesizer = SpecializedAgent(
            "Master Synthesizer", "You are the project lead.", self.sonu_client
        )
        final_answer = await synthesizer.analyze(synthesis_prompt)

        if self.ui:
            self.ui.show_info("Expert Panel synthesis complete.")

        return f"=== MIXTURE OF EXPERTS (MoE) MASTER PLAN ===\n\n{final_answer}"


def consult_expert_panel(task: str) -> str:
    try:
        from sonu_client import SonuClient

        client = SonuClient()

        class SilentUI:
            def show_info(self, *args, **kwargs):
                pass

            def show_error(self, *args, **kwargs):
                pass

            def show_agent_thought(self, *args, **kwargs):
                pass

        moe = MixtureOfExperts(client, SilentUI())
        return asyncio.run(moe.run_expert_panel(task))
    except Exception as e:
        return f"Failed to run expert panel: {e}"
