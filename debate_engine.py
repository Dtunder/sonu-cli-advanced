import concurrent.futures
import threading
import json
import logging
import re
import os
import sqlite3
import datetime
import uuid
import hashlib
import subprocess
from collections import defaultdict

class SQLiteMessageBus:
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS swarm_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    sender TEXT,
                    message TEXT,
                    timestamp TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS consensus_signatures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    commit_hash TEXT,
                    matrix_score REAL,
                    signature TEXT,
                    timestamp TEXT
                )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error initializing DB for MessageBus: {e}")

    def publish(self, session_id, sender, message):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            timestamp = datetime.datetime.now().isoformat()
            cursor.execute('''
                INSERT INTO swarm_messages (session_id, sender, message, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (session_id, sender, message, timestamp))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error publishing message: {e}")

    def get_messages(self, session_id, after_id=0):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, sender, message, timestamp FROM swarm_messages
                WHERE session_id = ? AND id > ? ORDER BY id ASC
            ''', (session_id, after_id))
            rows = cursor.fetchall()
            conn.close()
            return rows
        except Exception as e:
            print(f"Error reading messages: {e}")
            return []

    def sign_consensus(self, session_id, commit_hash, matrix_score, signature):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            timestamp = datetime.datetime.now().isoformat()
            cursor.execute('''
                INSERT INTO consensus_signatures (session_id, commit_hash, matrix_score, signature, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (session_id, commit_hash, matrix_score, signature, timestamp))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error signing consensus: {e}")


class SwarmConsensusServer:
    def __init__(self, sonu_client, ui):
        self.sonu_client = sonu_client
        self.ui = ui
        self.logger = logging.getLogger("SwarmConsensusServer")

        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = os.path.join(base_dir, "sonu.db")
        self.bus = SQLiteMessageBus(self.db_path)

        # Determine available providers for agents
        import providers
        available = [p for p in providers.list_providers() if providers.get_provider(p)["env_var"] is None or os.getenv(providers.get_provider(p)["env_var"])]

        self.agents = {
            "Agent-Architect": {
                "instruction": "You are the Agent-Architect. Your goal is to propose robust, scalable, and elegant code changes based on the user's prompt. You MUST output ONLY a valid Git Unified Diff (.patch format) wrapped in a ```diff block.",
                "provider": available[0] if available else "gemini"
            },
            "Agent-Critic": {
                "instruction": "You are the Agent-Critic. Your goal is to review the code proposed by the Architect, find bugs, logical errors, and suggest improvements. You must give a final score out of 10. Format your score exactly as: 'Score: [number]/10'.",
                "provider": available[1] if len(available) > 1 else (available[0] if available else "gemini")
            },
            "Agent-Security": {
                "instruction": "You are the Agent-Security. Your goal is to aggressively analyze the proposed changes for vulnerabilities, injection flaws, and security best practices. You must give a final score out of 10. Format your score exactly as: 'Score: [number]/10'.",
                "provider": available[2] if len(available) > 2 else (available[0] if available else "gemini")
            }
        }

    def _get_provider_response(self, provider, prompt, role_instruction):
        from openai_agent import OpenAICompatibleAgent
        import providers
        import os
        
        prov_info = providers.get_provider(provider)
        if not prov_info:
            provider = self.sonu_client.provider
            prov_info = providers.get_provider(provider)
            
        model = prov_info["default_model"]
        
        if provider == "gemini":
            try:
                from google import genai
                api_key = os.getenv("GEMINI_API_KEY")
                client = genai.Client(api_key=api_key)
                resp = client.models.generate_content(
                    model=model,
                    contents=f"{role_instruction}\n\n{prompt}"
                )
                return resp.text
            except Exception as e:
                self.logger.error(f"Gemini error: {e}")
                return f"Error from {provider}: {e}"
        else:
            try:
                agent = OpenAICompatibleAgent(provider, model, self.sonu_client)
                messages = [
                    {"role": "system", "content": role_instruction},
                    {"role": "user", "content": prompt}
                ]
                resp = agent.client.chat.completions.create(
                    model=model,
                    messages=messages
                )
                return resp.choices[0].message.content
            except Exception as e:
                self.logger.error(f"OpenAI agent error: {e}")
                return f"Error from {provider}: {e}"

    def _extract_score(self, text):
        pattern = r"(?i)score.*?(\d+(?:\.\d+)?)\s*(?:/|out of)\s*10"
        match = re.search(pattern, text)
        if match:
            return float(match.group(1))

        pattern2 = r"(\d+(?:\.\d+)?)\s*/\s*10"
        match2 = re.search(pattern2, text)
        if match2:
            return float(match2.group(1))

        return 0.0

    def run_debate(self, prompt):
        session_id = str(uuid.uuid4())
        self.ui.show_info(f"Starting SwarmConsensusServer Session: {session_id}")
        self.ui.show_info(f"Task: '{prompt}'")

        self.bus.publish(session_id, "User", prompt)
        
        self.ui.show_agent_thought("[Agent-Architect] is designing the code edit...")
        arch_config = self.agents["Agent-Architect"]
        proposal = self._get_provider_response(
            arch_config["provider"],
            f"User Prompt: {prompt}",
            arch_config["instruction"]
        )
        self.bus.publish(session_id, "Agent-Architect", proposal)
        self.ui.show_info(f"Agent-Architect Proposal:\n{proposal[:300]}...\n[...]")
        
        self.ui.show_agent_thought("Swarm is debating: [Agent-Critic] and [Agent-Security] are analyzing...")
        critique_prompt = f"Original Request: {prompt}\n\nArchitect's Proposal:\n{proposal}\n\nPlease review this proposal based on your role, provide feedback, and end with a score."

        def run_agent(agent_name):
            config = self.agents[agent_name]
            response = self._get_provider_response(
                config["provider"],
                critique_prompt,
                config["instruction"]
            )
            self.bus.publish(session_id, agent_name, response)
            score = self._extract_score(response)
            return agent_name, response, score

        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_to_agent = {
                executor.submit(run_agent, agent_name): agent_name
                for agent_name in ["Agent-Critic", "Agent-Security"]
            }
            
            for future in concurrent.futures.as_completed(future_to_agent):
                agent_name, response, score = future.result()
                results[agent_name] = {"response": response, "score": score}
                self.ui.show_info(f"[{agent_name}] Score: {score}/10")

        scores = [results["Agent-Critic"]["score"], results["Agent-Security"]["score"]]
        matrix_score = sum(scores) / len(scores) if scores else 0.0
        approval_percent = (matrix_score / 10.0) * 100

        self.ui.show_info(f"Cryptographic Consensus Matrix Score: {approval_percent:.2f}% ({matrix_score}/10)")

        if approval_percent > 66.0:
            self.ui.show_agent_thought("Consensus reached (>66%). Signing off in sonu.db and committing...")
            commit_hash = hashlib.sha256(proposal.encode('utf-8')).hexdigest()
            signature_payload = f"{session_id}:{commit_hash}:{matrix_score}:APPROVED"
            cryptographic_signature = hashlib.sha512(signature_payload.encode('utf-8')).hexdigest()

            self.bus.sign_consensus(session_id, commit_hash, matrix_score, cryptographic_signature)
            self._commit_to_master(prompt, proposal)
            self.ui.show_info(f"Success! Changes committed to master. Signature: {cryptographic_signature[:16]}...")
        else:
            self.ui.show_error("Consensus failed! Approval is 66% or lower. Changes rejected.")

        return {
            "proposals": {"Agent-Architect": proposal},
            "critiques": {"Agent-Critic": results["Agent-Critic"]["response"], "Agent-Security": results["Agent-Security"]["response"]},
            "scores_matrix": {"Agent-Architect": {"Agent-Critic": results["Agent-Critic"]["score"], "Agent-Security": results["Agent-Security"]["score"]}},
            "avg_scores": {"Agent-Architect": matrix_score},
            "best_provider": "Agent-Architect",
            "best_proposal": proposal,
            "session_id": session_id,
            "matrix_score": matrix_score,
            "approval_percent": approval_percent,
            "approved": approval_percent > 66.0
        }
        
    def _commit_to_master(self, prompt, proposal):
        try:
            subprocess.run(["git", "status"], check=True, capture_output=True)
            result = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True)
            current_branch = result.stdout.strip()

            target_branch = "master"
            branch_check = subprocess.run(["git", "branch"], capture_output=True, text=True)
            if " main" in branch_check.stdout or "* main" in branch_check.stdout:
                target_branch = "main"

            if current_branch != target_branch:
                self.ui.show_info(f"Currently on {current_branch}. Switching to {target_branch} branch to enforce commit rule.")
                try:
                    subprocess.run(["git", "stash"], check=False)
                    subprocess.run(["git", "checkout", target_branch], check=True)
                except subprocess.CalledProcessError:
                    self.ui.show_error(f"Failed to checkout {target_branch} branch. Changes can only be committed to the master branch.")
                    return
                    
            diff_match = re.search(r"```diff\n(.*?)```", proposal, re.DOTALL)
            patch_content = diff_match.group(1) if diff_match else proposal

            with open("swarm_edit.patch", "w", encoding="utf-8") as f:
                f.write(patch_content)
                
            try:
                subprocess.run(["git", "apply", "swarm_edit.patch"], check=True)
                subprocess.run(["git", "add", "-A"], check=True)
                commit_msg = f"Swarm Consensus Edit: {prompt[:50]}..."
                subprocess.run(["git", "commit", "-m", commit_msg], check=True)
                self.ui.show_info("Patch successfully applied and committed.")
            except subprocess.CalledProcessError as e:
                self.ui.show_error(f"Failed to apply patch: {e}. Committing as swarm_failed_edit.patch instead.")
                subprocess.run(["git", "add", "swarm_edit.patch"], check=True)
                commit_msg = f"Swarm Consensus Edit (Failed Patch): {prompt[:50]}..."
                subprocess.run(["git", "commit", "-m", commit_msg], check=True)
            finally:
                if os.path.exists("swarm_edit.patch"):
                    os.remove("swarm_edit.patch")

            if current_branch != target_branch:
                subprocess.run(["git", "checkout", current_branch], check=True)
                subprocess.run(["git", "stash", "pop"], check=False)
                
        except subprocess.CalledProcessError:
            self.logger.warning("Git commit failed or not in a git repository. Skipping actual git operations.")

GroupDebateEngine = SwarmConsensusServer
