"""Anbieter-Konfiguration fuer Sonu CLI (Multi-Provider).

Gemini laeuft nativ ueber das google-genai SDK (voller Funktionsumfang, getestet).
xAI (Grok), Groq, OpenRouter und Hugging Face sind alle OpenAI-kompatibel und
werden ueber EINEN Adapter (openai-SDK mit unterschiedlicher base_url) angesprochen.

Default-Modelle koennen zur Laufzeit mit /model gewechselt werden.
"""

PROVIDERS = {
    "gemini": {
        "label": "Google Gemini",
        "kind": "gemini",
        "env_var": "GEMINI_API_KEY",
        "base_url": None,
        "default_model": "gemini-3.5-flash",
    },
    "groq": {
        "label": "Groq",
        "kind": "openai",
        "env_var": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
    },
    "openrouter": {
        "label": "OpenRouter",
        "kind": "openai",
        "env_var": "OPENROUTER_API_KEY",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "openai/gpt-4o-mini",
    },
    "xai": {
        "label": "xAI (Grok)",
        "kind": "openai",
        "env_var": "XAI_API_KEY",
        "base_url": "https://api.x.ai/v1",
        "default_model": "grok-2",
    },
    "huggingface": {
        "label": "Hugging Face",
        "kind": "openai",
        "env_var": "HF_TOKEN",
        "base_url": "https://router.huggingface.co/v1",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct",
    },
}


def get_provider(name: str):
    return PROVIDERS.get(name)


def list_providers():
    return list(PROVIDERS.keys())
