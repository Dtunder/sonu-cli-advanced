import concurrent.futures
import threading
import json
import logging
import re
from collections import defaultdict

class GroupDebateEngine:
    def __init__(self, sonu_client, ui):
        self.sonu_client = sonu_client
        self.ui = ui
        self.logger = logging.getLogger("GroupDebateEngine")
        # Ensure we have a way to invoke providers
        self.providers = ["gemini", "groq", "openrouter"]

    def _get_provider_response(self, provider, prompt, role_instruction):
        """Helper to get a response from a specific provider."""
        from openai_agent import OpenAICompatibleAgent
        import providers
        import os
        
        # Use appropriate client/agent based on provider type
        prov_info = providers.get_provider(provider)
        if not prov_info:
            raise ValueError(f"Provider {provider} unknown.")
            
        model = prov_info["default_model"]
        
        if provider == "gemini":
            # For Gemini, use the multi-provider client to do a simple stream/completion
            # or build an ephemeral client
            # Using Gemini REST API for simple non-agentic call if possible,
            # or the native google-genai client
            from google import genai
            from google.genai import types
            
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY missing.")
            client = genai.Client(api_key=api_key)
            resp = client.models.generate_content(
                model=model,
                contents=f"{role_instruction}\n\nUser Prompt: {prompt}"
            )
            return resp.text
        else:
            # Use OpenAICompatibleAgent for a single turn
            agent = OpenAICompatibleAgent(provider, model, self.sonu_client)
            # For a simple response without tools, we just use the raw client
            messages = [
                {"role": "system", "content": role_instruction},
                {"role": "user", "content": prompt}
            ]
            resp = agent.client.chat.completions.create(
                model=model,
                messages=messages
            )
            return resp.choices[0].message.content

    def _extract_scores(self, critique_text, provider_names):
        """Parses the critique text to find scores for each provider."""
        scores = {}
        for provider in provider_names:
            # Look for patterns like "Provider Name: 8/10", "Provider Name - Score: 8", etc.
            pattern = rf"(?i){re.escape(provider)}.*?score.*?(\d+(?:\.\d+)?)\s*(?:/|out of)\s*10"
            match = re.search(pattern, critique_text)
            if match:
                scores[provider] = float(match.group(1))
            else:
                # Fallback: just look for the provider name and a number near it
                pattern2 = rf"(?i){re.escape(provider)}.*?(\d+(?:\.\d+)?)\s*(?:/|out of)\s*10"
                match2 = re.search(pattern2, critique_text)
                if match2:
                     scores[provider] = float(match2.group(1))
        return scores

    def run_debate(self, prompt):
        """Runs the debate process across multiple models."""
        self.ui.show_info(f"Starting Group Debate for: '{prompt}'")
        
        # Step 1: Initial Proposals
        proposals = {}
        self.ui.show_agent_thought("Fetching initial proposals from models...")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.providers)) as executor:
            future_to_provider = {
                executor.submit(
                    self._get_provider_response, 
                    provider, 
                    prompt, 
                    "You are an expert. Provide your best proposed solution to the user's prompt."
                ): provider for provider in self.providers
            }
            
            for future in concurrent.futures.as_completed(future_to_provider):
                provider = future_to_provider[future]
                try:
                    proposals[provider] = future.result()
                except Exception as exc:
                    self.ui.show_error(f"Failed to get proposal from {provider}: {exc}")
                    proposals[provider] = f"(Failed to fetch proposal from {provider})"

        for provider, proposal in proposals.items():
            self.ui.show_info(f"Proposal from {provider}:\n{proposal[:150]}...")

        # Step 2: Critique Phase
        critiques = {}
        self.ui.show_agent_thought("Models are now critiquing each other's proposals...")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.providers)) as executor:
            future_to_provider = {}
            for provider in self.providers:
                # Build context of other proposals
                other_proposals_text = ""
                other_providers = []
                for p_name, p_text in proposals.items():
                    if p_name != provider:
                        other_proposals_text += f"\n--- Proposal from {p_name} ---\n{p_text}\n"
                        other_providers.append(p_name)
                
                # Instruction is explicit about how to format the score
                critique_prompt = f"Original Prompt: {prompt}\n\nHere are proposals from other experts:\n{other_proposals_text}\n\nCritique these proposals. You MUST give a final score out of 10 for EACH proposal. Format it exactly like this:\n{other_providers[0]} Score: [score]/10"
                if len(other_providers) > 1:
                    critique_prompt += f"\n{other_providers[1]} Score: [score]/10"

                future = executor.submit(
                    self._get_provider_response,
                    provider,
                    critique_prompt,
                    "You are a critical reviewer. Analyze the provided proposals, highlight flaws, praise strengths, and give a score exactly as requested."
                )
                future_to_provider[future] = provider

            for future in concurrent.futures.as_completed(future_to_provider):
                provider = future_to_provider[future]
                try:
                    critiques[provider] = future.result()
                except Exception as exc:
                    self.ui.show_error(f"Failed to get critique from {provider}: {exc}")
                    critiques[provider] = f"(Failed to fetch critique from {provider})"
                    
        # Step 3: Consensus Calculation
        self.ui.show_agent_thought("Calculating consensus matrix score...")
        
        # Matrix: reviewer -> { reviewee -> score }
        scores_matrix = defaultdict(dict)
        for reviewer, critique_text in critiques.items():
            other_providers = [p for p in self.providers if p != reviewer]
            extracted_scores = self._extract_scores(critique_text, other_providers)
            for reviewee, score in extracted_scores.items():
                scores_matrix[reviewer][reviewee] = score
                
        # Calculate average score for each proposal
        proposal_scores = {p: [] for p in self.providers}
        for reviewer, scores in scores_matrix.items():
            for reviewee, score in scores.items():
                 proposal_scores[reviewee].append(score)
                 
        avg_scores = {}
        for provider, scores in proposal_scores.items():
            if scores:
                avg_scores[provider] = sum(scores) / len(scores)
            else:
                avg_scores[provider] = 0.0 # Default if no scores parsed
                
        self.logger.info(f"Calculated average scores: {avg_scores}")
        
        # Select best
        best_provider = max(avg_scores.keys(), key=lambda k: avg_scores[k])
        
        # If all scores are 0 (e.g. parsing failed for all), fallback to longest
        if all(score == 0.0 for score in avg_scores.values()):
             best_provider = max(proposals.keys(), key=lambda k: len(proposals[k]))

        best_proposal = proposals[best_provider]
        
        self.ui.show_info(f"Consensus reached. Best proposal chosen from: {best_provider} (Avg Score: {avg_scores[best_provider]:.2f})")
        
        return {
            "proposals": proposals,
            "critiques": critiques,
            "scores_matrix": dict(scores_matrix),
            "avg_scores": avg_scores,
            "best_provider": best_provider,
            "best_proposal": best_proposal
        }

import asyncio

class SwarmConsensusEngine:
    """
    A true asynchronous swarm consensus engine that spins up multiple agent calls
    in parallel to synthesize the best possible answer from multiple models/agents.
    """
    def __init__(self, sonu_client, ui=None):
        self.sonu_client = sonu_client
        self.ui = ui
        self.logger = logging.getLogger("SwarmConsensusEngine")

        import providers
        import os
        self.providers = []
        for p in providers.list_providers():
            prov_info = providers.get_provider(p)
            if prov_info["env_var"] is None or os.getenv(prov_info["env_var"]):
                self.providers.append(p)
        if not self.providers:
            self.providers = ["gemini", "groq", "openrouter"] # fallback

    async def _get_async_response(self, provider, prompt, instruction):
        # We run the synchronous call in a threadpool to not block asyncio event loop
        loop = asyncio.get_running_loop()
        engine = GroupDebateEngine(self.sonu_client, self.ui)
        return await loop.run_in_executor(
            None,
            engine._get_provider_response,
            provider,
            prompt,
            instruction
        )

    async def run_swarm_debate(self, prompt: str) -> str:
        if self.ui:
            self.ui.show_info(f"Initiating Swarm Consensus for: '{prompt}'")
            self.ui.show_agent_thought("Swarm nodes generating parallel proposals...")

        # 1. Parallel Proposals
        proposals = {}
        proposal_tasks = []
        for provider in self.providers:
            task = asyncio.create_task(self._get_async_response(
                provider,
                prompt,
                "You are an expert sub-agent in a swarm. Provide your best proposed solution to the user's prompt. Be detailed and accurate."
            ))
            proposal_tasks.append((provider, task))

        for provider, task in proposal_tasks:
            try:
                proposals[provider] = await task
            except Exception as e:
                if self.ui:
                    self.ui.show_error(f"Swarm node {provider} failed proposal: {e}")
                proposals[provider] = ""

        # Filter out empty
        proposals = {p: text for p, text in proposals.items() if text}
        if not proposals:
            return "Swarm failed to generate any proposals."

        if self.ui:
            self.ui.show_agent_thought("Swarm nodes synthesizing final consensus...")

        # 2. Parallel Synthesis (instead of just critiquing, we ask them to synthesize a master answer)
        syntheses = {}
        synthesis_tasks = []
        for provider in proposals.keys():
            other_proposals_text = ""
            for p_name, p_text in proposals.items():
                other_proposals_text += f"\n--- Proposal from Swarm Node {p_name} ---\n{p_text}\n"

            synth_prompt = f"Original Prompt: {prompt}\n\nHere are proposals from the swarm:\n{other_proposals_text}\n\nSynthesize these into the ultimate, most correct, and comprehensive answer."

            task = asyncio.create_task(self._get_async_response(
                provider,
                synth_prompt,
                "You are the master synthesizer of a cybernetic swarm. Combine the best elements of the provided proposals to create a flawless final answer."
            ))
            synthesis_tasks.append((provider, task))

        for provider, task in synthesis_tasks:
            try:
                syntheses[provider] = await task
            except Exception as e:
                if self.ui:
                    self.ui.show_error(f"Swarm node {provider} failed synthesis: {e}")
                syntheses[provider] = ""

        syntheses = {p: text for p, text in syntheses.items() if text}
        if not syntheses:
            return "Swarm failed to synthesize a consensus."

        # 3. Final Evaluator (Use highest capability provider, e.g. Gemini, to pick the best synthesis)
        evaluator_provider = "gemini" if "gemini" in syntheses else list(syntheses.keys())[0]
        final_answer = syntheses[evaluator_provider]

        if self.ui:
            self.ui.show_info("Swarm Consensus achieved.")

        return f"=== SWARM CONSENSUS ANSWER ===\n\n{final_answer}"

def invoke_swarm(prompt: str) -> str:
    # A synchronous wrapper to expose as a tool
    try:
        from sonu_client import SonuClient
        from terminal_ui import TerminalUI
        # Fallback to minimal UI
        class SilentUI:
            def show_info(self, *args, **kwargs): pass
            def show_error(self, *args, **kwargs): pass
            def show_agent_thought(self, *args, **kwargs): pass

        # We need an instance of client, try to get existing or create temporary
        try:
            client = SonuClient()
            engine = SwarmConsensusEngine(client, SilentUI())
            return asyncio.run(engine.run_swarm_debate(prompt))
        except Exception as e:
            return f"Failed to invoke swarm: {e}"
    except Exception as e:
        return f"Failed to initialize swarm: {e}"
