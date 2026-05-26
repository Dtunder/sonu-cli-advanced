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
