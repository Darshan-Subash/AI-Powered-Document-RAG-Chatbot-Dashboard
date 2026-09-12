"""
LLM provider abstraction. Pick a provider with MODEL_PROVIDER in .env:
  - "openai"       : direct OpenAI API, needs OPENAI_API_KEY
  - "azure_openai" : Azure-hosted OpenAI, needs AZURE_OPENAI_* vars
  - "anthropic"    : needs ANTHROPIC_API_KEY
  - "gemini"       : needs GOOGLE_API_KEY
  - "ollama"       : free, fully local, needs Ollama running
"""
from app.config import (
    MODEL_PROVIDER,
    MODEL_NAME,
    OPENAI_API_KEY,
    ANTHROPIC_API_KEY,
    GOOGLE_API_KEY,
    OLLAMA_BASE_URL,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_DEPLOYMENT,
)


def _is_gpt5_family(model_name: str) -> bool:
    return (model_name or "").lower().startswith("gpt-5")


def _chat_kwargs(model_name: str, system_prompt: str, user_prompt: str) -> dict:
    kwargs = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if _is_gpt5_family(model_name):
        kwargs["reasoning_effort"] = "minimal"
    else:
        kwargs["temperature"] = 0.1
    return kwargs


def _generate_openai(system_prompt: str, user_prompt: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    resp = client.chat.completions.create(**_chat_kwargs(MODEL_NAME or "gpt-5-mini", system_prompt, user_prompt))
    return resp.choices[0].message.content


def _generate_azure_openai(system_prompt: str, user_prompt: str) -> str:
    from openai import AzureOpenAI
    if not (AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY and AZURE_OPENAI_DEPLOYMENT):
        raise RuntimeError(
            "Azure OpenAI is not fully configured. Set AZURE_OPENAI_ENDPOINT, "
            "AZURE_OPENAI_API_KEY, and AZURE_OPENAI_DEPLOYMENT in .env."
        )
    client = AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
    )
    
    kwargs = _chat_kwargs(AZURE_OPENAI_DEPLOYMENT, system_prompt, user_prompt)
    if not _is_gpt5_family(AZURE_OPENAI_DEPLOYMENT) and _is_gpt5_family(MODEL_NAME):
        kwargs.pop("temperature", None)
        kwargs["reasoning_effort"] = "minimal"

    try:
        resp = client.chat.completions.create(**kwargs)
    except Exception as e:
        err = str(e).lower()
        if "temperature" in err or "unrecognized request argument" in err or "reasoning_effort" in err:
            kwargs.pop("temperature", None)
            kwargs.pop("reasoning_effort", None)
            resp = client.chat.completions.create(**kwargs)
        else:
            raise e

    return resp.choices[0].message.content


def _generate_anthropic(system_prompt: str, user_prompt: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model=MODEL_NAME or "claude-sonnet-4-6",
        max_tokens=1000,
        temperature=0.1,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return "".join(block.text for block in resp.content if block.type == "text")


def _generate_gemini(system_prompt: str, user_prompt: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel(MODEL_NAME or "gemini-1.5-flash", system_instruction=system_prompt)
    resp = model.generate_content(user_prompt)
    return resp.text


def _generate_ollama(system_prompt: str, user_prompt: str) -> str:
    import requests
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": MODEL_NAME or "llama3.1",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {"temperature": 0.1},
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


_PROVIDERS = {
    "openai": _generate_openai,
    "azure_openai": _generate_azure_openai,
    "anthropic": _generate_anthropic,
    "gemini": _generate_gemini,
    "ollama": _generate_ollama,
}


def generate(system_prompt: str, user_prompt: str) -> str:
    provider_fn = _PROVIDERS.get(MODEL_PROVIDER)
    if provider_fn is None:
        raise ValueError(
            f"Unknown MODEL_PROVIDER '{MODEL_PROVIDER}'. Use one of: {list(_PROVIDERS)}"
        )
    return provider_fn(system_prompt, user_prompt)