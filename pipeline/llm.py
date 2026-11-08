"""Minimal LLM client returning JSON objects.

Backend selection (first match wins):

1. **LiteLLM gateway** (OpenAI-compatible) - when ``LLM_BASE_URL`` (default
   ``http://litellm:4000/v1``) *and* ``LLM_API_KEY`` are set.  The gateway
   maps the aliases ``copy`` / ``classify`` to real models (configured in
   ``infra/``), so switching providers never touches this code.
2. **Anthropic Messages API** - when only ``ANTHROPIC_API_KEY`` is set.
3. Otherwise :class:`LLMUnavailable` is raised and callers fall back to
   deterministic template copy.

Everything goes through ``requests`` (no vendor SDKs).  Timeouts are 60 s,
there is one retry with backoff on 429 / 5xx, and the backend used is logged.
Keys are never read from anywhere but the environment.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, Optional

import requests

from .config import Settings, get_settings

log = logging.getLogger("pipeline.llm")

TIMEOUT = 60
RETRY_STATUSES = {429, 500, 502, 503, 504}
RETRY_BACKOFF_S = 2.0
_FENCE_RE = re.compile(r"^\s*```(?:json|JSON)?\s*(.*?)\s*```\s*$", re.DOTALL)


class LLMError(RuntimeError):
    """A backend was configured but the call failed (HTTP/parse error)."""


class LLMUnavailable(LLMError):
    """No LLM backend is configured - use deterministic fallback copy."""


def strip_fences(text: str) -> str:
    """Remove a surrounding ```json ... ``` fence if the model added one."""
    if not text:
        return ""
    m = _FENCE_RE.match(text)
    if m:
        return m.group(1).strip()
    return text.strip()


def extract_json(text: str) -> Dict[str, Any]:
    """Parse the model answer as a JSON object, tolerating fences / prose."""
    cleaned = strip_fences(text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # last resort: take the outermost {...}
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise LLMError("Model did not return a JSON object")
        data = json.loads(cleaned[start:end + 1])
    if not isinstance(data, dict):
        raise LLMError("Model returned JSON that is not an object")
    return data


def resolve_model(alias: str, settings: Optional[Settings] = None) -> str:
    """Translate the logical alias (``copy``/``classify``) to a model id."""
    s = settings or get_settings()
    if alias == "copy":
        return s.llm_model_copy
    if alias == "classify":
        return s.llm_model_classify
    return alias


def backend_name(settings: Optional[Settings] = None) -> str:
    s = settings or get_settings()
    if s.llm_base_url and s.llm_api_key:
        return "litellm"
    if s.anthropic_api_key:
        return "anthropic"
    return "none"


def _post_with_retry(url: str, *, headers: dict, payload: dict, backend: str) -> requests.Response:
    last_exc: Optional[Exception] = None
    for attempt in (1, 2):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)
        except requests.RequestException as exc:   # network error -> one retry
            last_exc = exc
            log.warning("LLM %s request error (attempt %d): %s", backend, attempt, exc)
            if attempt == 1:
                time.sleep(RETRY_BACKOFF_S)
            continue
        if resp.status_code in RETRY_STATUSES and attempt == 1:
            retry_after = resp.headers.get("Retry-After")
            try:
                delay = min(float(retry_after), 20.0) if retry_after else RETRY_BACKOFF_S
            except ValueError:
                delay = RETRY_BACKOFF_S
            log.warning("LLM %s HTTP %s, retrying in %.1fs", backend, resp.status_code, delay)
            time.sleep(delay)
            continue
        return resp
    raise LLMError(f"LLM {backend} request failed: {last_exc}")


def _chat_litellm(system: str, user: str, model: str, max_tokens: int,
                  temperature: float, s: Settings) -> Dict[str, Any]:
    url = f"{s.llm_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {s.llm_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    resp = _post_with_retry(url, headers=headers, payload=payload, backend="litellm")
    if resp.status_code >= 400:
        raise LLMError(f"LiteLLM HTTP {resp.status_code}: {resp.text[:300]}")
    try:
        body = resp.json()
        content = body["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"LiteLLM: unexpected response shape ({exc})")
    if isinstance(content, list):   # some gateways return content parts
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return extract_json(content or "")


def _chat_anthropic(system: str, user: str, model: str, max_tokens: int,
                    temperature: float, s: Settings) -> Dict[str, Any]:
    url = f"{s.anthropic_base_url.rstrip('/')}/v1/messages"
    headers = {
        "x-api-key": s.anthropic_api_key or "",
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system + "\n\nOdpověz výhradně jedním JSON objektem, bez komentáře a bez ``` ohraničení. "
                           "/ Respond with exactly one JSON object, no commentary, no ``` fences.",
        "messages": [{"role": "user", "content": user}],
    }
    resp = _post_with_retry(url, headers=headers, payload=payload, backend="anthropic")
    if resp.status_code >= 400:
        raise LLMError(f"Anthropic HTTP {resp.status_code}: {resp.text[:300]}")
    try:
        body = resp.json()
        text = "".join(block.get("text", "") for block in body.get("content", [])
                       if block.get("type") == "text")
    except (ValueError, AttributeError, TypeError) as exc:
        raise LLMError(f"Anthropic: unexpected response shape ({exc})")
    return extract_json(text)


def chat_json(system: str, user: str, model_alias: str = "copy", max_tokens: int = 1500,
              temperature: float = 0.4, settings: Optional[Settings] = None) -> Dict[str, Any]:
    """Send one system+user exchange and return the parsed JSON object.

    ``model_alias`` is ``"copy"`` or ``"classify"`` (translated through
    ``LLM_MODEL_COPY`` / ``LLM_MODEL_CLASSIFY``) or an explicit model id.
    Raises :class:`LLMUnavailable` when no backend is configured and
    :class:`LLMError` when the configured backend fails.
    """
    s = settings or get_settings()
    backend = backend_name(s)
    if backend == "litellm":
        model = resolve_model(model_alias, s)
        log.info("LLM backend=litellm model=%s", model)
        return _chat_litellm(system, user, model, max_tokens, temperature, s)
    if backend == "anthropic":
        # aliases are a gateway concept; direct Anthropic calls use ANTHROPIC_MODEL
        model = s.anthropic_model if model_alias in ("copy", "classify") else model_alias
        log.info("LLM backend=anthropic model=%s", model)
        return _chat_anthropic(system, user, model, max_tokens, temperature, s)
    raise LLMUnavailable(
        "Není nakonfigurován žádný LLM backend (LLM_BASE_URL + LLM_API_KEY nebo ANTHROPIC_API_KEY)."
    )
