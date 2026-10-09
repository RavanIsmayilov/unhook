"""One small interface over the LLM providers (Gemini, Groq).

    result = generate("gemini", system, prompt, image=None, schema=VERDICT_SCHEMA)
    result.text, result.provider, result.model

- Retries 429 / quota / 5xx errors with exponential backoff.
- If Gemini is unavailable, text-only requests fall back to Groq (result.provider says which answered).
- Results are cached in SQLite by hash of (provider, model, system, prompt, image), so re-running eval is free.
- Raises LLMUnavailable when nothing could answer; callers decide how to degrade.
"""
import hashlib
import json
import random
import re
import sqlite3
import sys
import threading
import time
from dataclasses import dataclass

from app import settings


stats = {"api_calls": 0}  # real provider calls made in this process (cache hits don't count); eval uses it to pace calls


class LLMUnavailable(Exception):
    """No provider could answer (missing key, quota exhausted, network, empty response)."""


class LLMBusy(LLMUnavailable):
    """Too many requests at once; waiting longer would not help the person in front of the screen."""


_slots = threading.BoundedSemaphore(settings.MAX_CONCURRENT_LLM)
_waited = threading.local()  # seconds this thread spent sleeping in rate-limit backoff during the current call


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    cached: bool = False
    tokens_in: int | None = None   # as reported by the provider (None for cached answers)
    tokens_out: int | None = None  # includes reasoning tokens, which are billed as output
    latency_ms: int | None = None  # total, including waits
    waited_ms: int | None = None   # the part of latency spent waiting after rate-limit errors


def model_for(provider: str) -> str:
    return {"gemini": settings.GEMINI_MODEL, "groq": settings.GROQ_MODEL}[provider]


def image_media_type(data: bytes) -> str:
    if data.startswith(b"\x89PNG"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:3] == b"GIF":
        return "image/gif"
    return "image/jpeg"


# ---------------------------------------------------------------- retries

def _is_retryable(exc: Exception) -> bool:
    text = str(exc).lower()
    # A daily quota (or a retry hint of more than a minute) won't recover during backoff: fail fast.
    if "perday" in text or "per day" in text:
        return False
    hint = re.search(r"retrydelay['\"]?:\s*['\"]?(\d+(?:\.\d+)?)s", text)
    if hint and float(hint.group(1)) > 60:
        return False
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if code in (408, 429, 500, 502, 503, 504):
        return True
    return any(s in text for s in ("resource_exhausted", "rate limit", "quota", "overloaded", "timed out", "connection"))


def _with_backoff(fn, tries: int = 3, base_delay: float = 2.0):
    for attempt in range(tries):
        try:
            return fn()
        except Exception as e:
            if attempt == tries - 1 or not _is_retryable(e):
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            print(f"[llm] {type(e).__name__}, retrying in {delay:.1f}s ({attempt + 1}/{tries - 1})", file=sys.stderr)
            _waited.seconds = getattr(_waited, "seconds", 0.0) + delay
            time.sleep(delay)


# ---------------------------------------------------------------- providers

def _strip_for_gemini(schema: dict) -> dict:
    """Gemini's schema dialect rejects 'additionalProperties'."""
    if isinstance(schema, dict):
        return {k: _strip_for_gemini(v) for k, v in schema.items() if k != "additionalProperties"}
    if isinstance(schema, list):
        return [_strip_for_gemini(v) for v in schema]
    return schema


def _call_gemini(system: str, prompt: str, image: bytes | None, schema: dict | None, temperature: float,
                 max_tokens: int, model: str | None = None) -> str:
    model = model or settings.GEMINI_MODEL
    if not settings.GEMINI_API_KEY:
        raise LLMUnavailable("GEMINI_API_KEY is not set")
    from google import genai
    from google.genai import types

    contents: list = []
    if image:
        contents.append(types.Part.from_bytes(data=image, mime_type=image_media_type(image)))
    contents.append(prompt)
    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=temperature,
        max_output_tokens=max_tokens,
        response_mime_type="application/json" if schema else None,
        response_json_schema=_strip_for_gemini(schema) if schema else None,
        # Gemini 3.x thinks by default and thinking tokens count against max_output_tokens
        thinking_config=types.ThinkingConfig(thinking_level="LOW") if "gemini-3" in model else None,
    )
    client = genai.Client(api_key=settings.GEMINI_API_KEY, http_options=types.HttpOptions(timeout=30_000))
    try:
        response = _with_backoff(
            lambda: client.models.generate_content(model=model, contents=contents, config=config)
        )
    except Exception as e:
        raise LLMUnavailable(f"gemini: {type(e).__name__}: {str(e)[:200]}") from e
    if not response.text:
        raise LLMUnavailable("gemini: empty response (blocked or no output)")
    u = response.usage_metadata
    usage = {"in": getattr(u, "prompt_token_count", None), "out": (getattr(u, "candidates_token_count", 0) or 0) + (getattr(u, "thoughts_token_count", 0) or 0)} if u else {}
    return response.text, usage


def _call_groq(system: str, prompt: str, image: bytes | None, schema: dict | None, temperature: float,
               max_tokens: int, model: str | None = None) -> str:
    model = model or settings.GROQ_MODEL
    if not settings.GROQ_API_KEY:
        raise LLMUnavailable("GROQ_API_KEY is not set")
    if image:
        raise LLMUnavailable("groq: images are not supported by this adapter")
    from groq import Groq

    if schema:  # Groq's JSON mode only guarantees valid JSON, so describe the shape in the prompt
        system += "\n\nReturn ONLY a JSON object that matches this JSON schema:\n" + json.dumps(schema)
    client = Groq(api_key=settings.GROQ_API_KEY)
    extra = {"response_format": {"type": "json_object"}} if schema else {}
    try:
        response = _with_backoff(
            lambda: client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                **extra,
            )
        )
    except Exception as e:
        raise LLMUnavailable(f"groq: {type(e).__name__}: {str(e)[:200]}") from e
    text = response.choices[0].message.content
    if not text:
        raise LLMUnavailable("groq: empty response")
    u = response.usage
    return text, ({"in": u.prompt_tokens, "out": u.completion_tokens} if u else {})


_PROVIDERS = {"gemini": _call_gemini, "groq": _call_groq}


# ---------------------------------------------------------------- cache

def _cache_key(provider: str, system: str, prompt: str, image: bytes | None, schema: dict | None,
               temperature: float, model: str | None = None) -> str:
    h = hashlib.sha256()
    for part in (provider, model or model_for(provider), system, prompt, json.dumps(schema, sort_keys=True), str(temperature)):
        h.update(part.encode())
        h.update(b"\x00")
    h.update(image or b"")
    return h.hexdigest()


def _cache_conn() -> sqlite3.Connection:
    settings.CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.CACHE_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, text TEXT NOT NULL)")
    return conn


def _cache_get(key: str) -> str | None:
    with _cache_conn() as conn:
        row = conn.execute("SELECT text FROM cache WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def _cache_put(key: str, text: str) -> None:
    with _cache_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO cache (key, text) VALUES (?, ?)", (key, text))


# ---------------------------------------------------------------- public API

def _is_valid(text: str, validate) -> bool:
    if validate is None:
        return True
    try:
        validate(text)
        return True
    except Exception:
        return False


def _call_cached(provider: str, system: str, prompt: str, image: bytes | None, schema: dict | None,
                 temperature: float, max_tokens: int, use_cache: bool, validate=None,
                 model: str | None = None) -> LLMResult:
    model = model or model_for(provider)
    key = _cache_key(provider, system, prompt, image, schema, temperature, model)
    if use_cache and (hit := _cache_get(key)) is not None and _is_valid(hit, validate):
        return LLMResult(hit, provider, model, cached=True)
    if not _slots.acquire(timeout=settings.QUEUE_WAIT_SECONDS):
        raise LLMBusy("too many requests at once")
    try:
        stats["api_calls"] += 1
        _waited.seconds = 0.0
        started = time.monotonic()
        answer = _PROVIDERS[provider](system, prompt, image, schema, temperature, max_tokens, model=model)
        latency_ms = round((time.monotonic() - started) * 1000)
        waited_ms = round(getattr(_waited, "seconds", 0.0) * 1000)
    finally:
        _slots.release()
    text, usage = answer if isinstance(answer, tuple) else (answer, {})  # test doubles may return a bare string
    if not _is_valid(text, validate):  # e.g. truncated JSON: never cache it, let the caller fall back
        raise LLMUnavailable(f"{provider}: output failed validation")
    if use_cache:
        _cache_put(key, text)
    return LLMResult(text, provider, model, tokens_in=usage.get("in"), tokens_out=usage.get("out"), latency_ms=latency_ms,
                     waited_ms=waited_ms)


def _fallback_candidates(provider: str, model: str | None, has_image: bool) -> list[tuple[str, str | None]]:
    """What to try after the primary (provider, model) failed: other models of the same provider, then Groq for text."""
    tried = model or model_for(provider)
    own = settings.GEMINI_FALLBACK_MODELS if provider == "gemini" else settings.GROQ_FALLBACK_MODELS
    chain: list[tuple[str, str | None]] = [(provider, m) for m in own if m != tried]
    if provider == "gemini" and not has_image:  # Groq cannot read images
        chain.append(("groq", None))
        chain += [("groq", m) for m in settings.GROQ_FALLBACK_MODELS if m != settings.GROQ_MODEL]
    return chain


def generate(provider: str, system: str, prompt: str, image: bytes | None = None, schema: dict | None = None,
             temperature: float = 0.0, max_tokens: int = 4000, use_cache: bool = True,
             fallback: bool = True, validate=None, model: str | None = None) -> LLMResult:
    """Ask `provider` (cache first). If it fails, walk a fallback chain (other free models, then Groq for text).

    model: override the provider's default model for this call.
    fallback=False turns the chain off (eval uses it so each provider is measured on its own).
    validate: optional callable(text) that raises if the output is unusable; such outputs are not cached
    and count as a failure of that model (so they trigger the chain).
    """
    if provider not in _PROVIDERS:
        raise ValueError(f"unknown provider {provider!r}; use one of {list(_PROVIDERS)}")
    try:
        return _call_cached(provider, system, prompt, image, schema, temperature, max_tokens, use_cache, validate, model)
    except LLMBusy:
        raise  # a queue of people is waiting: more model calls would only make it worse
    except LLMUnavailable as error:
        if not fallback:
            raise
        started = time.monotonic()
        for next_provider, next_model in _fallback_candidates(provider, model, image is not None):
            if time.monotonic() - started > settings.CHAIN_BUDGET_SECONDS:
                break  # the person has waited long enough; answer with what we have
            print(f"[llm] {error} -> trying {next_provider}/{next_model or model_for(next_provider)}", file=sys.stderr)
            try:
                return _call_cached(next_provider, system, prompt, image if next_provider == "gemini" else None, schema,
                                    temperature, max_tokens, use_cache, validate, next_model)
            except LLMBusy:
                raise
            except LLMUnavailable as e:
                error = e
        raise error
