"""One small wrapper around free LLM providers, so the rest of the app doesn't care which one is used.

Pick with LLM_PROVIDER in your .env (default: gemini):
  gemini  -> Google AI Studio free tier. Needs GEMINI_API_KEY (or GOOGLE_API_KEY).
  groq    -> Groq free tier. Needs GROQ_API_KEY.
  ollama  -> a local model, no key, e.g. `ollama pull qwen2.5-coder:7b`.
Optional: LLM_MODEL to override the default model for the provider.

All of these are free. No paid API is used anywhere in this project.
"""

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
# Your key lives in AI Learning\.env (one folder up). A cohort-builder\.env also works.
load_dotenv(ROOT.parent / ".env")
load_dotenv(ROOT / ".env")

DEFAULT_MODELS = {
    "gemini": "gemini-3.5-flash",
    "groq": "llama-3.3-70b-versatile",
    "ollama": "qwen2.5-coder:7b",
}


# Google retires older models for new keys. If the chosen Gemini model is not available
# (404), the next one in this list is tried automatically and remembered.
GEMINI_FALLBACKS = ["gemini-3.5-flash", "gemini-3.7-flash", "gemini-3.8-flash",
                    "gemini-3.5-flash-lite", "gemini-2.5-flash"]
_working_gemini_model: str | None = None
TIMEOUT_SECONDS = 90


class LLMError(RuntimeError):
    pass


def provider() -> str:
    return os.getenv("LLM_PROVIDER", "gemini").strip().lower()


def model_name() -> str:
    if os.getenv("LLM_MODEL"):
        return os.environ["LLM_MODEL"]
    if provider() == "gemini" and _working_gemini_model:
        return _working_gemini_model
    return DEFAULT_MODELS.get(provider(), "")


def is_configured() -> tuple[bool, str]:
    p = provider()
    if p == "gemini" and not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        return False, "No Gemini key found. Add GEMINI_API_KEY=... to AI Learning\\.env (free key from aistudio.google.com)."
    if p == "groq" and not os.getenv("GROQ_API_KEY"):
        return False, "No Groq key found. Add GROQ_API_KEY=... to AI Learning\\.env (free key from console.groq.com)."
    if p not in DEFAULT_MODELS:
        return False, f"Unknown LLM_PROVIDER '{p}'. Use gemini, groq or ollama."
    return True, ""


def complete_json(system: str, messages: list[dict]) -> dict:
    """Send a conversation and return the model's reply parsed as JSON.

    messages: [{"role": "user"|"assistant", "content": str}, ...]
    Retries a couple of times on rate limits (free tiers have per-minute limits).
    """
    ok, why = is_configured()
    if not ok:
        raise LLMError(why)

    last_err = None
    for attempt in range(3):
        try:
            text = _call(system, messages)
            return _parse_json(text)
        except _RateLimited as e:
            last_err = e
            time.sleep(10 * (attempt + 1))
        except json.JSONDecodeError as e:
            last_err = LLMError(f"The model didn't return valid JSON: {e}")
            messages = messages + [{"role": "user", "content": "Reply with valid JSON only, no other text."}]
    raise LLMError(str(last_err))


class _RateLimited(Exception):
    pass


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise json.JSONDecodeError("no JSON object found", text, 0)
    return json.loads(text[start:end + 1])


def _call(system: str, messages: list[dict]) -> str:
    p = provider()
    if p == "gemini":
        return _gemini(system, messages)
    if p == "groq":
        return _openai_compatible("https://api.groq.com/openai/v1/chat/completions",
                                  os.environ["GROQ_API_KEY"], system, messages)
    if p == "ollama":
        host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        return _openai_compatible(f"{host}/v1/chat/completions", "ollama", system, messages)
    raise LLMError(f"Unknown provider {p}")


def _gemini(system: str, messages: list[dict]) -> str:
    global _working_gemini_model
    from google import genai
    from google.genai import errors, types

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
                          http_options=types.HttpOptions(timeout=TIMEOUT_SECONDS * 1000))
    contents = [types.Content(role="model" if m["role"] == "assistant" else "user",
                              parts=[types.Part(text=m["content"])]) for m in messages]
    config = types.GenerateContentConfig(system_instruction=system,
                                         response_mime_type="application/json", temperature=0)

    # The model from LLM_MODEL (or the one that worked last time) first, then the fallbacks.
    candidates = [model_name()] if os.getenv("LLM_MODEL") else \
        list(dict.fromkeys([model_name()] + GEMINI_FALLBACKS))
    for i, model in enumerate(candidates):
        try:
            resp = client.models.generate_content(model=model, contents=contents, config=config)
        except errors.APIError as e:
            code = getattr(e, "code", None)
            if code == 429:
                raise _RateLimited(f"Gemini rate limit reached: {e}") from e
            if code == 404 and i < len(candidates) - 1:
                continue  # model retired or not available for this key: try the next one
            raise LLMError(f"Gemini error ({model}): {e}") from e
        except Exception as e:  # timeouts and network errors
            raise LLMError(f"Couldn't reach Gemini ({model}) within {TIMEOUT_SECONDS}s: {type(e).__name__}: {e}") from e
        _working_gemini_model = model
        if not resp.text:
            raise LLMError("Gemini returned an empty reply (it may have been blocked by a safety filter).")
        return resp.text
    raise LLMError("None of the Gemini models are available for this key. Set LLM_MODEL in .env.")


def _openai_compatible(url: str, key: str, system: str, messages: list[dict]) -> str:
    body = {
        "model": model_name(),
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system}] + messages,
    }
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise _RateLimited(f"Rate limit reached: {e}") from e
        raise LLMError(f"{provider()} error {e.code}: {e.read().decode(errors='ignore')[:300]}") from e
    except urllib.error.URLError as e:
        raise LLMError(f"Couldn't reach {provider()} at {url}: {e.reason}") from e
    return data["choices"][0]["message"]["content"]
