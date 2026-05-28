import os
import json

import tools
from skills_manager import SkillsManager
from process_manager import ProcessManager
from memory_manager import MemoryManager
from context_compressor import compress_openai_messages



class OpenAICompatibleAgent:
    def __init__(self, provider_name, model, sonu_client):
        self.provider_name = provider_name
        self.model = model
        self.sonu_client = sonu_client

        import providers
        prov_info = providers.get_provider(provider_name)
        if not prov_info:
            raise ValueError(f"Provider {provider_name} unbekannt.")

        if prov_info["env_var"] is not None:
            api_key = os.getenv(prov_info["env_var"])
            if not api_key:
                raise ValueError(f"Kein API-Key fuer {provider_name} in .env ({prov_info['env_var']}) gefunden.")
        else:
            api_key = "dummy-key-for-local"

        headers = {}

        from openai import OpenAI
        self.client = OpenAI(
            api_key=api_key,
            base_url=prov_info["base_url"],
            default_headers=headers
        )

        self.messages = []
        self._build_system_message()

    def _build_system_message(self):
        # Basis-System-Prompt aus dem SonuClient importieren (dort in SYSTEM_INSTRUCTION definiert)
        from sonu_client import SYSTEM_INSTRUCTION
        active_instruction = SYSTEM_INSTRUCTION
        
        if self.sonu_client.skills_mgr.active_skill:
            try:
                skill_content = self.sonu_client.skills_mgr.activate_skill(self.sonu_client.skills_mgr.active_skill)
                active_instruction += (
                    f"\n\n=== ERWÄHLTE EXPERTEN-SKILL-REGELN ({self.sonu_client.skills_mgr.active_skill}) ===\n"
                    f"{skill_content}\n"
                )
            except Exception:
                pass
                
        mem_context = self.sonu_client.memory_mgr.load_memory(os.getcwd())
        full_sys_prompt = (
            f"{active_instruction}\n\n"
            f"=== ERMITTELTER SYSTEMKONTEXT (4-EBENEN-GEDÄCHTNIS) ===\n"
            f"{mem_context}\n"
        )
        
        sys_msg = {"role": "system", "content": full_sys_prompt}
        if not self.messages:
            self.messages = [sys_msg]
        else:
            self.messages[0] = sys_msg

    def _get_tool_specs(self):
        base_tools = tools.get_openai_tools()
        
        skill_tool = {"type": "function", "function": {
            "name": "activate_skill",
            "description": "Aktiviert ein Experten-Skill-Profil. name='off' deaktiviert. Verfuegbar: " + ", ".join(self.sonu_client.skills_mgr.list_skills()),
            "parameters": {"type": "object",
                "properties": {"name": {"type": "string", "description": "Skill-Name oder 'off'."}},
                "required": ["name"]}}}
                
        return base_tools + [skill_tool]

    def _set_skill(self, name):
        if name in (None, "", "none", "clear", "off", "aus", "deactivate"):
            self.sonu_client.skills_mgr.deactivate_skill()
            self._build_system_message()
            return True, "Skill deaktiviert. Zurueck zum Baseline-Modus."
        try:
            self.sonu_client.skills_mgr.activate_skill(name)
        except Exception:
            avail = ", ".join(self.sonu_client.skills_mgr.list_skills()) or "(keine)"
            return False, f"Skill '{name}' nicht gefunden. Verfuegbar: {avail}"
        self._build_system_message()
        return True, f"Skill '{name}' aktiviert."

    def run_agent_turn(self, user_input, ui, max_steps=25):
        import time
        import openai
        self.messages.append({"role": "user", "content": user_input})
        
        # Check and compress before starting the loop
        self.messages = compress_openai_messages(self.messages, self.model, self)

        
        for _ in range(max_steps):
            try:
                # Tool Specs vorbereiten
                tool_specs = self._get_tool_specs()
                kwargs = {
                    "model": self.model,
                    "messages": self.messages,
                    "tools": tool_specs,
                    "tool_choice": "auto"
                }
                
                try:
                    start_time = time.time()
                    resp = self.client.chat.completions.create(**kwargs)
                    latency = (time.time() - start_time) * 1000
                except openai.BadRequestError as e:
                    err_msg = str(e).lower()
                    if "tool call validation failed" in err_msg or "tool_use_failed" in err_msg:
                        ui.show_agent_thought("(Tool-Call Format fehlerhaft, fordere Modell zur Korrektur auf...)")
                        self.messages.append({
                            "role": "user", 
                            "content": f"System Error: Your last tool call failed validation with: {e}\n\nPlease correct your tool call format. Do NOT append arguments to the tool name. Output valid JSON arguments."
                        })
                        continue
                    elif "tool" in err_msg or "function" in err_msg:
                        ui.show_agent_thought(f"({self.provider_name} scheint Tool-Calling nicht zu unterstützen, Fallback auf reinen Chat...)")
                        kwargs.pop("tools", None)
                        kwargs.pop("tool_choice", None)
                        start_time = time.time()
                        resp = self.client.chat.completions.create(**kwargs)
                        latency = (time.time() - start_time) * 1000
                    else:
                        raise e
            except openai.RateLimitError:
                raise  # propagate directly — sonu_client._is_rate_limit_error() handles rotation
            except Exception:
                raise
            
            prompt_tokens = 0
            completion_tokens = 0
            if hasattr(resp, "usage") and resp.usage:
                prompt_tokens = getattr(resp.usage, "prompt_tokens", 0)
                completion_tokens = getattr(resp.usage, "completion_tokens", 0)
            
            if prompt_tokens or completion_tokens:
                if hasattr(self, "sonu_client") and hasattr(self.sonu_client, "storage_mgr"):
                    self.sonu_client.storage_mgr.log_token_usage(
                        provider=self.provider_name,
                        model=self.model,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        latency_ms=latency,
                        estimated_cost_usd=0.0
                    )
                
            msg = resp.choices[0].message
            
            if not msg.tool_calls:
                self.messages.append({"role": "assistant", "content": msg.content or ""})
                return (msg.content or "").strip()
                
            interim = (msg.content or "").strip()
            if interim:
                ui.show_agent_thought(interim)
                
            # Assistant-Turn mit tool_calls im Verlauf speichern (als Dictionaries)
            assistant_msg = {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in msg.tool_calls
                ]
            }
            self.messages.append(assistant_msg)
            
            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                    if not isinstance(args, dict):
                        args = {}
                except Exception:
                    args = {}
                    
                ui.show_tool_call(name, args)
                
                if name == "activate_skill":
                    ok, m = self._set_skill(args.get("name"))
                    ui.show_tool_result(name, m, rejected=not ok)
                    result = m
                else:
                    if not tools.is_safe(name) and not ui.confirm_action(name, args):
                        result = "ABGELEHNT: Der Nutzer hat diese Aktion abgelehnt."
                        ui.show_tool_result(name, result, rejected=True)
                    else:
                        result = tools.dispatch(name, args)
                        ui.show_tool_result(name, result)
                        
                self.messages.append({
                    "role": "tool", "tool_call_id": tc.id, "content": str(result),
                })
                
        return "(Abbruch: maximale Anzahl an Tool-Schritten erreicht.)"
