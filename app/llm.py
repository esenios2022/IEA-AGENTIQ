"""LLM router - REST directo a OpenAI, Anthropic, Gemini, Mistral y Ollama."""
import os, httpx
TIMEOUT = 120.0
PRICES = {
    "gpt-4o": (2.5, 10.0), "gpt-4o-mini": (0.15, 0.6), "gpt-3.5-turbo": (0.5, 1.5),
    "claude-3-5-sonnet": (3.0, 15.0), "claude-3-5-haiku": (0.8, 4.0), "claude-3-opus": (15.0, 75.0),
    "gemini-2.0-flash": (0.1, 0.4), "gemini-1.5-pro": (1.25, 5.0),
    "mistral-small": (0.2, 0.6), "mistral-medium": (2.7, 8.1), "mistral-large": (2.0, 6.0),
}
def _key(name, get_setting):
    v = get_setting(name) if get_setting else None
    return v or os.getenv(name)
def cost_for(model, tin, tout):
    for k, (pi, po) in PRICES.items():
        if k in model: return (tin * pi + tout * po) / 1_000_000
    return (tin * 0.2 + tout * 0.6) / 1_000_000
def resolve_model(tier_or_model, get_setting=None):
    t = (tier_or_model or "economy").strip(); tl = t.lower()
    if tl.startswith("ollama/"): return "ollama", t.split("/", 1)[1]
    if tl.startswith("gpt"): return "openai", t
    if tl.startswith("claude"): return "anthropic", t
    if tl.startswith("gemini"): return "gemini", t
    if tl.startswith("mistral-"): return "mistralai", t
    chains = {
        "economy":  [("gemini", "gemini-2.0-flash"), ("openai", "gpt-4o-mini"), ("anthropic", "claude-3-5-haiku-20241022"), ("mistralai", "mistral-small-latest"), ("ollama", "llama3.2")],
        "standard": [("openai", "gpt-4o"), ("anthropic", "claude-3-5-sonnet-20241022"), ("gemini", "gemini-1.5-pro"), ("ollama", "llama3.1")],
        "premium":  [("anthropic", "claude-3-opus-20240229"), ("openai", "gpt-4o"), ("gemini", "gemini-1.5-pro")],
    }
    envmap = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY", "mistralai": "MISTRAL_API_KEY"}
    for prov, model in chains.get(tl, chains["economy"]):
        if prov == "ollama":
            if _key("OLLAMA_URL", get_setting): return prov, model
        else:
            k = _key(envmap[prov], get_setting)
            if not k and prov == "gemini": k = _key("GOOGLE_API_KEY", get_setting)
            if k: return prov, model
    return "none", tl
def complete(provider, model, system, user, get_setting=None):
    if provider == "none":
        raise RuntimeError("No hay ningun proveedor de IA configurado. Carga una API key (OpenAI, Anthropic, Gemini o Mistral) en Conexion & API o como variable de entorno en Railway.")
    with httpx.Client(timeout=TIMEOUT) as cx:
        if provider == "openai":
            r = cx.post("https://api.openai.com/v1/chat/completions",
                        headers={"Authorization": "Bearer " + str(_key('OPENAI_API_KEY', get_setting))},
                        json={"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
            r.raise_for_status(); d = r.json(); u = d.get("usage", {})
            return d["choices"][0]["message"]["content"], u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
        if provider == "anthropic":
            r = cx.post("https://api.anthropic.com/v1/messages",
                        headers={"x-api-key": str(_key("ANTHROPIC_API_KEY", get_setting)), "anthropic-version": "2023-06-01"},
                        json={"model": model, "max_tokens": 2048, "system": system, "messages": [{"role": "user", "content": user}]})
            r.raise_for_status(); d = r.json(); u = d.get("usage", {})
            return d["content"][0]["text"], u.get("input_tokens", 0), u.get("output_tokens", 0)
        if provider == "gemini":
            key = _key("GEMINI_API_KEY", get_setting) or _key("GOOGLE_API_KEY", get_setting)
            r = cx.post("https://generativelanguage.googleapis.com/v1beta/models/" + model + ":generateContent?key=" + str(key),
                        json={"system_instruction": {"parts": [{"text": system}]}, "contents": [{"parts": [{"text": user}]}]})
            r.raise_for_status(); d = r.json(); um = d.get("usageMetadata", {})
            return d["candidates"][0]["content"]["parts"][0]["text"], um.get("promptTokenCount", 0), um.get("candidatesTokenCount", 0)
        if provider == "mistralai":
            r = cx.post("https://api.mistral.ai/v1/chat/completions",
                        headers={"Authorization": "Bearer " + str(_key('MISTRAL_API_KEY', get_setting))},
                        json={"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
            r.raise_for_status(); d = r.json(); u = d.get("usage", {})
            return d["choices"][0]["message"]["content"], u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
        if provider == "ollama":
            base = _key("OLLAMA_URL", get_setting) or "http://localhost:11434"
            r = cx.post(base.rstrip('/') + "/api/chat",
                        json={"model": model, "stream": False, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
            r.raise_for_status(); d = r.json()
            return d["message"]["content"], d.get("prompt_eval_count", 0), d.get("eval_count", 0)
    raise RuntimeError("Proveedor desconocido: " + provider)
