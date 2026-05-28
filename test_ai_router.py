import pytest
from smart_router import AIClassifierRouter

class MockResponse:
    def __init__(self, text):
        self.text = text

class MockModels:
    def __init__(self, response_text, delay=0):
        self.response_text = response_text
        self.delay = delay

    def generate_content(self, model, contents, config=None):
        import time
        if self.delay > 0:
            time.sleep(self.delay)
        if isinstance(self.response_text, Exception):
            raise self.response_text
        return MockResponse(self.response_text)

class MockClient:
    def __init__(self, response_text, delay=0):
        self.models = MockModels(response_text, delay)

def test_flash_selection():
    router = AIClassifierRouter()
    client = MockClient('{"model_choice": "flash", "reasoning": "complex"}')
    result = router.classify_with_ai("Write a python script", [], client, "gemini-2.0-flash-lite")
    assert result["model_choice"] == "flash"

    choice, budget = router.select_model("Write a python script", [], client, ["gemini-2.5-flash", "gemini-2.0-flash-lite"])
    assert choice == "gemini-2.5-flash"
    assert budget == 4096

def test_lite_selection():
    router = AIClassifierRouter()
    client = MockClient('{"model_choice": "lite", "reasoning": "simple"}')
    result = router.classify_with_ai("Hello", [], client, "gemini-2.0-flash-lite")
    assert result["model_choice"] == "lite"

    choice, budget = router.select_model("Hello, how are you today?", [], client, ["gemini-2.5-flash", "gemini-2.0-flash-lite"])
    assert choice == "gemini-2.0-flash-lite"
    assert budget == 1024

def test_short_input_bypass():
    router = AIClassifierRouter()
    client = MockClient(Exception("Should not be called"))
    # Input len <= 15
    choice, budget = router.select_model("Hi", [], client, ["gemini-2.5-flash", "gemini-2.0-flash-lite"])
    assert choice == "gemini-2.0-flash-lite"
    assert budget == 512

def test_classifier_failure_fallback():
    router = AIClassifierRouter()
    client = MockClient('{"invalid_json": true}')
    choice, budget = router.select_model("This is a long input string that should trigger the AI", [], client, ["gemini-2.5-flash", "gemini-2.0-flash-lite"])
    assert choice == "gemini-2.5-flash"
    assert budget == 4096

def test_latency_timeout():
    router = AIClassifierRouter()
    client = MockClient('{"model_choice": "lite"}', delay=0.9)
    choice, budget = router.select_model("This is a long input string that should trigger the AI", [], client, ["gemini-2.5-flash", "gemini-2.0-flash-lite"])
    assert choice == "gemini-2.5-flash"
    assert router._last_classification["reasoning"].startswith("latency timeout")

def test_model_restoration():
    # Test that sonu_client restores the model
    from sonu_client import SonuClient
    from unittest.mock import MagicMock

    client = SonuClient()
    client.client = MagicMock()
    client.chat = MagicMock()
    client.chat.get_history.return_value = []
    client._send_with_rotation = MagicMock(return_value=MagicMock(text="test"))

    original_model = client.model_name
    client.ai_router = AIClassifierRouter()
    client.ai_router.select_model = MagicMock(return_value=("gemini-2.5-flash", 4096))

    client._run_agent_turn_internal("Hello world!", ui=MagicMock(), max_steps=5)

    assert client.model_name == original_model
