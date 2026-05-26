import os
import json
import urllib.request
from dotenv import load_dotenv

class MultiProviderClient:
    def __init__(self):
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        load_dotenv(env_path, override=True)
        self.xai_key = os.getenv("XAI_API_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY")

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
