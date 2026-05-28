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
        "default_model": "gemini-2.5-flash",
    },
    "groq": {
        "label": "Groq",
        "kind": "openai",
        "env_var": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
    },
    # OpenRouter deaktiviert: Account hat keine Credits (402 bei jedem Request).
    # Zum Reaktivieren: Credits auf openrouter.ai kaufen, dann einkommentieren.
    # "openrouter": {
    #     "label": "OpenRouter",
    #     "kind": "openai",
    #     "env_var": "OPENROUTER_API_KEY",
    #     "base_url": "https://openrouter.ai/api/v1",
    #     "default_model": "openai/gpt-4o-mini",
    # },
    # xAI deaktiviert: Account hat keine Credits (403 bei jedem Request).
    # Zum Reaktivieren: Credits auf console.x.ai kaufen, dann diesen Block einkommentieren.
    # "xai": {
    #     "label": "xAI (Grok)",
    #     "kind": "openai",
    #     "env_var": "XAI_API_KEY",
    #     "base_url": "https://api.x.ai/v1",
    #     "default_model": "grok-3",
    # },
    "huggingface": {
        "label": "Hugging Face",
        "kind": "openai",
        "env_var": "HF_TOKEN",
        "base_url": "https://router.huggingface.co/v1",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct",
    },
    "ollama": {
        "label": "Ollama (Local Offline)",
        "kind": "openai",
        "env_var": None,
        "base_url": "http://localhost:11434/v1",
        "default_model": "llama3",
    },
}


def get_provider(name: str):
    return PROVIDERS.get(name)


def list_providers():
    return list(PROVIDERS.keys())
