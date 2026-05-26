import json
import tiktoken
from google.genai import types

def count_tokens(text: str, model_name: str = "gpt-3.5-turbo") -> int:
    """Schätzt die Tokenzahl eines Textes. Nutzt standardmäßig cl100k_base."""
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

def get_model_limit(model_name: str) -> int:
    """Gibt das ungefähre Token-Limit für gängige Modelle zurück."""
    model_name = model_name.lower()
    if "gemini-1.5" in model_name or "gemini-2" in model_name or "gemini-3" in model_name:
        return 1_000_000 # Eher defensiv
    elif "gpt-4o" in model_name or "gpt-4-turbo" in model_name:
        return 128_000
    elif "claude-3" in model_name:
        return 200_000
    elif "llama-3" in model_name:
        return 8_192 if "8b" in model_name else 128_000
    elif "grok" in model_name:
        return 128_000
    return 128_000 # Default fallback

def compress_openai_messages(messages: list, model_name: str, client_or_agent) -> list:
    """Komprimiert OpenAI-kompatible Nachrichten, falls Limit überschritten."""
    limit = get_model_limit(model_name)
    threshold = int(limit * 0.7)

    total_tokens = 0
    for msg in messages:
        total_tokens += count_tokens(str(msg.get("content", "")))

    if total_tokens <= threshold:
        return messages

    # Suche nach der letzten System Message
    sys_end = 0
    for i, msg in enumerate(messages):
        if msg.get("role") == "system":
            sys_end = i + 1

    history_msgs = messages[sys_end:]
    if len(history_msgs) < 3:
        return messages # Zu kurz für Kompression

    # Wir wollen die ältesten 30% der history messages komprimieren
    to_compress_count = int(len(history_msgs) * 0.3)
    # Nicht mitten in einem tool_call / tool response abbrechen
    while to_compress_count < len(history_msgs) and history_msgs[to_compress_count].get("role") == "tool":
        to_compress_count += 1

    if to_compress_count == 0:
        return messages

    msgs_to_compress = history_msgs[:to_compress_count]
    remaining_msgs = history_msgs[to_compress_count:]

    summary = summarize_messages_openai(msgs_to_compress, client_or_agent)

    compressed_msg = {
        "role": "user",
        "content": f"[SYSTEM_MEMORY: ZUSAMMENFASSUNG ALTER CHATS]\n{summary}"
    }

    return messages[:sys_end] + [compressed_msg] + remaining_msgs

def summarize_messages_openai(messages: list, agent) -> str:
    """Führt einen API Call aus, um Nachrichten zusammenzufassen."""
    text_to_summarize = []
    for m in messages:
        role = m.get("role", "unknown")
        content = m.get("content") or ""
        if role == "assistant" and m.get("tool_calls"):
            content += " [Tool Calls getätigt]"
        text_to_summarize.append(f"{role.upper()}: {content}")

    full_text = "\n".join(text_to_summarize)

    # Nutze den Client des Agenten für die Zusammenfassung
    prompt = f"Bitte fasse den folgenden Gesprächsverlauf kurz und prägnant zusammen, fokussiere dich auf Fakten und Code-Zustände, die für den weiteren Verlauf wichtig sind:\n\n{full_text}"
    try:
        resp = agent.client.chat.completions.create(
            model=agent.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500
        )
        return resp.choices[0].message.content or "Zusammenfassung fehlgeschlagen."
    except Exception as e:
        return f"Kontext komprimiert, aber Zusammenfassung schlug fehl: {e}"

def compress_gemini_history(history: list, model_name: str, client) -> list:
    """Komprimiert Gemini Chat History, falls Limit überschritten."""
    limit = get_model_limit(model_name)
    threshold = int(limit * 0.7)

    total_tokens = 0
    for content in history:
        for part in content.parts:
            if part.text:
                 total_tokens += count_tokens(part.text)
            elif part.function_call:
                 total_tokens += 50
            elif part.function_response:
                 total_tokens += count_tokens(str(part.function_response))

    if total_tokens <= threshold:
        return history

    if len(history) < 3:
         return history

    to_compress_count = int(len(history) * 0.3)
    if to_compress_count % 2 != 0:
        to_compress_count += 1 # Paarweise (user/model) lassen

    if to_compress_count == 0 or to_compress_count >= len(history):
        return history

    # Darauf achten, nicht nach einem function_call abzuschneiden,
    # sodass die verbleibenden Nachrichten mit einer function_response beginnen
    while to_compress_count < len(history):
        next_msg = history[to_compress_count]
        has_function_response = any(p.function_response for p in next_msg.parts)
        if has_function_response:
            to_compress_count += 2
        else:
            break

    if to_compress_count >= len(history):
        return history

    msgs_to_compress = history[:to_compress_count]
    remaining_msgs = history[to_compress_count:]

    summary = summarize_messages_gemini(msgs_to_compress, client, model_name)

    # Gemini History erwartet ein Part und role ("user" oder "model")
    # Wir fügen die Zusammenfassung als User-Nachricht und ein "Ok" vom Model ein,
    # um das Alternieren von user/model beizubehalten, falls nötig.
    compressed_history = [
        types.Content(role="user", parts=[types.Part.from_text(text=f"[SYSTEM_MEMORY: ZUSAMMENFASSUNG ALTER CHATS]\n{summary}")]),
        types.Content(role="model", parts=[types.Part.from_text(text="Verstanden. Ich werde das im weiteren Verlauf berücksichtigen.")])
    ]

    return compressed_history + remaining_msgs

def summarize_messages_gemini(history: list, client, model_name: str) -> str:
    """Führt einen API Call aus, um Gemini Nachrichten zusammenzufassen."""
    text_to_summarize = []
    for content in history:
        role = content.role
        text_parts = []
        for p in content.parts:
            if p.text: text_parts.append(p.text)
            elif p.function_call: text_parts.append(f"[Tool Call: {p.function_call.name}]")
        text_to_summarize.append(f"{role.upper()}: {' '.join(text_parts)}")

    full_text = "\n".join(text_to_summarize)
    prompt = f"Bitte fasse den folgenden Gesprächsverlauf kurz und prägnant zusammen, fokussiere dich auf Fakten und Code-Zustände, die für den weiteren Verlauf wichtig sind:\n\n{full_text}"

    try:
        resp = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        return resp.text or "Zusammenfassung fehlgeschlagen."
    except Exception as e:
         return f"Kontext komprimiert, aber Zusammenfassung schlug fehl: {e}"
