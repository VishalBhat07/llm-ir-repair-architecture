from __future__ import annotations

import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from typing import Any

from dotenv import load_dotenv

from .prompts import SYSTEM_INSTRUCTION
from .types import LLMResponse, ModelConfig

load_dotenv()
RETRYABLE_HTTP_STATUS_CODES = {408, 429, 500, 502, 503, 504}
# Minimum pause between consecutive Gemini requests to reduce burst 429s.
_GEMINI_INTER_REQUEST_DELAY_S: float = float(os.getenv("GEMINI_INTER_REQUEST_DELAY_S", "1.0"))


class LLMRequestTimeoutError(RuntimeError):
    """Raised when a model HTTP request exceeds the configured timeout."""


def _retry_delay_seconds(
    attempt_index: int, backoff_seconds: float, retry_after_header: str | None = None
) -> float:
    if retry_after_header:
        retry_after = retry_after_header.strip()
        if retry_after.isdigit():
            return max(1.0, float(retry_after))
    return max(1.0, backoff_seconds * (2**attempt_index))


def _extract_retry_after_seconds(exc: urllib.error.HTTPError) -> float | None:
    """Try to find how long we should wait from a 429/5xx HTTP error.

    Checks (in order):
    1. Retry-After header  (standard HTTP)
    2. retryDelay field in the JSON error body  (Gemini-specific)
    """
    # 1. Standard header
    retry_after_header = exc.headers.get("Retry-After", "").strip()
    if retry_after_header:
        if retry_after_header.isdigit():
            return max(1.0, float(retry_after_header))
        # RFC 7231 date – fall through and let caller use backoff

    # 2. Gemini-specific JSON body field, e.g. { "error": { "details": [{ "retryDelay": "30s" }] } }
    try:
        body = exc.read().decode("utf-8", errors="ignore")
        exc._body = body  # cache so callers can still read it
        data = json.loads(body)
        for detail in data.get("error", {}).get("details", []):
            delay_str = detail.get("retryDelay", "")
            if delay_str:
                # Parse "30s" or "30" or "30000ms" style strings
                match = re.match(r"([\d.]+)(ms|s)?", str(delay_str))
                if match:
                    value = float(match.group(1))
                    unit = match.group(2) or "s"
                    return max(1.0, value / 1000.0 if unit == "ms" else value)
    except Exception:  # noqa: BLE001
        pass
    return None


def _request_json(
    request: urllib.request.Request,
    timeout_seconds: int,
    max_retries: int = 0,
    backoff_seconds: float = 2.0,
) -> dict[str, Any]:
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except TimeoutError as exc:
            if attempt >= max_retries:
                raise LLMRequestTimeoutError(
                    f"Request to {request.full_url} timed out after {timeout_seconds}s"
                ) from exc
            time.sleep(_retry_delay_seconds(attempt, backoff_seconds))
        except urllib.error.HTTPError as exc:
            if exc.code in RETRYABLE_HTTP_STATUS_CODES and attempt < max_retries:
                wait = _extract_retry_after_seconds(exc)
                if wait is None:
                    wait = _retry_delay_seconds(attempt, backoff_seconds)
                print(f"  [llm_client] HTTP {exc.code} – retrying in {wait:.1f}s (attempt {attempt + 1}/{max_retries + 1})")
                time.sleep(wait)
                continue
            # Not retryable or retries exhausted – build a useful message
            try:
                details = getattr(exc, "_body", None) or exc.read().decode("utf-8", errors="ignore")
            except Exception:  # noqa: BLE001
                details = ""
            message = f"HTTP {exc.code} from {request.full_url}"
            if details.strip():
                message = f"{message}: {details.strip()}"
            raise RuntimeError(message) from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                if attempt >= max_retries:
                    raise LLMRequestTimeoutError(
                        f"Request to {request.full_url} timed out after {timeout_seconds}s"
                    ) from exc
                time.sleep(_retry_delay_seconds(attempt, backoff_seconds))
                continue
            raise RuntimeError(f"Request to {request.full_url} failed: {exc.reason}") from exc
    raise RuntimeError(f"Request failed after {max_retries} retries: {request.full_url}")


def _get_json(
    url: str,
    headers: dict[str, str] | None = None,
    timeout_seconds: int = 30,
    max_retries: int = 0,
    backoff_seconds: float = 2.0,
) -> dict[str, Any]:
    request = urllib.request.Request(url=url, method="GET")
    request.add_header("Accept", "application/json")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    return _request_json(
        request=request,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        backoff_seconds=backoff_seconds,
    )


def _post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
    timeout_seconds: int = 120,
    max_retries: int = 0,
    backoff_seconds: float = 2.0,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url=url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    return _request_json(
        request=request,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        backoff_seconds=backoff_seconds,
    )


class LLMClient:
    def __init__(self, model_config: ModelConfig) -> None:
        self.model_config = model_config

    def _estimate_cost(self, input_tokens: int | None, output_tokens: int | None) -> float | None:
        pricing = self.model_config.pricing or {}
        input_rate = pricing.get("input_per_million_usd")
        output_rate = pricing.get("output_per_million_usd")
        if input_tokens is None or output_tokens is None:
            return None
        if input_rate is None or output_rate is None:
            return None
        return (input_tokens / 1_000_000 * input_rate) + (output_tokens / 1_000_000 * output_rate)

    def generate(self, prompt: str, system_instruction: str = SYSTEM_INSTRUCTION) -> LLMResponse:
        start = time.perf_counter()
        access_mode = self.model_config.access_mode
        if access_mode == "local_ollama":
            response = self._generate_ollama(prompt, system_instruction)
        elif access_mode == "api_gemini":
            response = self._generate_gemini(prompt, system_instruction)
        else:
            raise ValueError(f"Unsupported access mode: {access_mode}")
        response.latency_seconds = time.perf_counter() - start
        response.estimated_cost_usd = self._estimate_cost(response.input_tokens, response.output_tokens)
        return response

    def preflight(self) -> None:
        if self.model_config.access_mode != "local_ollama":
            return
        if not self.model_config.base_url:
            raise RuntimeError("Ollama model config requires base_url")
        url = f"{self.model_config.base_url.rstrip('/')}/api/tags"
        raw = _get_json(
            url=url,
            timeout_seconds=self.model_config.preflight_timeout_seconds,
            max_retries=1,
            backoff_seconds=1.0,
        )
        model_names = {
            str(item.get("model", "")).strip()
            for item in raw.get("models", [])
            if isinstance(item, dict) and item.get("model")
        }
        if self.model_config.model not in model_names:
            raise RuntimeError(
                f"Ollama model '{self.model_config.model}' is not available locally. "
                f"Run: ollama pull {self.model_config.model}"
            )

    def _generate_ollama(self, prompt: str, system_instruction: str) -> LLMResponse:
        payload = {
            "model": self.model_config.model,
            "stream": False,
            "options": {
                "temperature": self.model_config.temperature,
                "top_p": self.model_config.top_p,
                "num_predict": self.model_config.max_output_tokens,
            },
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt},
            ],
        }
        url = f"{self.model_config.base_url.rstrip('/')}/api/chat"
        raw = _post_json(
            url=url,
            payload=payload,
            timeout_seconds=self.model_config.timeout_seconds,
            max_retries=self.model_config.request_max_retries,
            backoff_seconds=self.model_config.request_backoff_seconds,
        )
        text = raw.get("message", {}).get("content", "")
        return LLMResponse(
            text=text,
            raw_payload=raw,
            input_tokens=raw.get("prompt_eval_count"),
            output_tokens=raw.get("eval_count"),
        )

    def _generate_gemini(self, prompt: str, system_instruction: str) -> LLMResponse:
        api_key_name = self.model_config.env_api_key or "GEMINI_API_KEY"
        api_key = os.getenv(api_key_name)
        if not api_key:
            raise RuntimeError(
                f"Missing required environment variable: {api_key_name}. "
                "Set it in your .env file or shell environment."
            )
        payload = {
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": self.model_config.temperature,
                "topP": self.model_config.top_p,
                "maxOutputTokens": self.model_config.max_output_tokens,
            },
        }
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model_config.model}:generateContent?key={api_key}"
        )
        # Throttle between consecutive Gemini requests to avoid burst 429s.
        time.sleep(_GEMINI_INTER_REQUEST_DELAY_S)
        raw = _post_json(
            url=url,
            payload=payload,
            timeout_seconds=self.model_config.timeout_seconds,
            max_retries=self.model_config.request_max_retries,
            backoff_seconds=self.model_config.request_backoff_seconds,
        )
        candidates = raw.get("candidates", [])
        text_chunks: list[str] = []
        for candidate in candidates:
            for part in candidate.get("content", {}).get("parts", []):
                if "text" in part:
                    text_chunks.append(part["text"])
        usage = raw.get("usageMetadata", {})
        return LLMResponse(
            text="".join(text_chunks).strip(),
            raw_payload=raw,
            input_tokens=usage.get("promptTokenCount"),
            output_tokens=usage.get("candidatesTokenCount"),
        )
