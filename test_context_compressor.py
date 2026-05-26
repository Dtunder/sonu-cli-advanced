import pytest
from context_compressor import count_tokens, get_model_limit, compress_openai_messages, compress_gemini_history
from google.genai import types

def test_count_tokens():
    assert count_tokens("Hello, world!") > 0

def test_get_model_limit():
    assert get_model_limit("gpt-3.5-turbo") == 128_000
    assert get_model_limit("gemini-1.5-pro") == 1_000_000

class DummyAgent:
    def __init__(self):
        self.model = "gpt-3.5-turbo"
        class Choices:
            def __init__(self):
                class Message:
                    def __init__(self):
                        self.content = "Dies ist eine Zusammenfassung."
                self.message = Message()
        class Chat:
            class Completions:
                def create(self, **kwargs):
                    return Choices()
            def __init__(self):
                self.completions = self.Completions()
        class Client:
            def __init__(self):
                self.chat = Chat()
        self.client = Client()

def test_compress_openai_messages_no_compression():
    messages = [{"role": "system", "content": "You are a helpful assistant."}]
    messages += [{"role": "user", "content": "Hi"}] * 10

    compressed = compress_openai_messages(messages, "gpt-3.5-turbo", DummyAgent())
    assert len(compressed) == 11

def test_compress_openai_messages_with_compression():
    # threshold is 70% of 128_000 = 89600. So we need a lot of tokens.
    long_text = "word " * 20000 # 20000 words ~ 25000 tokens
    messages = [{"role": "system", "content": "You are a helpful assistant."}]
    messages += [{"role": "user", "content": long_text}] * 5 # ~125000 tokens > threshold

    agent = DummyAgent()
    compressed = compress_openai_messages(messages, "gpt-3.5-turbo", agent)

    assert sum(len(str(m.get('content', ''))) for m in compressed) < sum(len(str(m.get('content', ''))) for m in messages)
    assert compressed[0]["role"] == "system"
    assert compressed[1]["role"] == "user"
    assert "[SYSTEM_MEMORY:" in compressed[1]["content"]


def test_compress_gemini_history_with_compression():
    class DummyClient:
        class Models:
            def generate_content(self, model, contents):
                class Resp:
                    text = "summary"
                return Resp()
        def __init__(self):
            self.models = self.Models()

    long_text = "word " * 100000
    history = []
    for i in range(10):
        history.append(types.Content(role="user", parts=[types.Part.from_text(text=long_text)]))
        history.append(types.Content(role="model", parts=[types.Part.from_text(text=long_text)]))

    client = DummyClient()
    new_history = compress_gemini_history(history, "gemini-1.5-pro", client)

    assert len(new_history) < len(history)
    assert len(new_history) == 16
    assert "[SYSTEM_MEMORY:" in new_history[0].parts[0].text
