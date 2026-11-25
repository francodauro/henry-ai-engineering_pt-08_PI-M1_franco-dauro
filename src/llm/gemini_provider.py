"""Proveedor primario (gratuito): Google Gemini, con el SDK ``google-genai``.

Los tokens salen del ``usage_metadata`` que devuelve la API (Google no tiene un tokenizer local).
Los tokens de "pensamiento" del modelo se cuentan como salida: Google los cobra como salida.
"""

from __future__ import annotations

import re
import time
from typing import Any

from google import genai
from google.genai import errors, types

from .base import (
    AuthError,
    BadRequestError,
    EmptyResponseError,
    LLMProvider,
    LLMResponse,
    ProviderConnectionError,
    ProviderError,
    ProviderTimeoutError,
    RateLimitError,
    ServerError,
)


def find_retry_delay(obj: Any) -> float | None:
    """Busca ``retryDelay`` (por ejemplo "34s") dentro del cuerpo de un error de Google."""
    if isinstance(obj, dict):
        value = obj.get("retryDelay")
        if isinstance(value, str):
            match = re.match(r"^\s*([\d.]+)s\s*$", value)
            if match:
                return float(match.group(1))
        children = obj.values()
    elif isinstance(obj, list):
        children = obj
    else:
        return None
    for child in children:
        found = find_retry_delay(child)
        if found is not None:
            return found
    return None


def _retry_after(exc: errors.APIError) -> float | None:
    """Primero el header Retry-After; si no vino, el ``retryDelay`` del cuerpo del error."""
    try:
        header = exc.response.headers.get("retry-after") if exc.response is not None else None
        if header is not None:
            return float(header)
    except (AttributeError, ValueError):
        pass
    return find_retry_delay(getattr(exc, "details", None))


def usage_tokens(meta: Any) -> tuple[int, int, int]:
    """(entrada, salida, total) desde ``usage_metadata``. La salida incluye los tokens de pensamiento."""
    if meta is None:
        return 0, 0, 0
    prompt = meta.prompt_token_count or 0
    output = (meta.candidates_token_count or 0) + (getattr(meta, "thoughts_token_count", None) or 0)
    total = meta.total_token_count or prompt + output
    return prompt, output, total


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str, max_tokens: int, temperature: float, timeout_s: float):
        super().__init__(model, max_tokens, temperature, timeout_s)
        if not api_key:
            raise AuthError(self.name, "Falta GEMINI_API_KEY en el .env")
        # Timeout en milisegundos. Los reintentos no los hace el SDK: los maneja src/retry.py.
        self._client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=int(timeout_s * 1000)))

    def complete(self, prompt: str, system: str | None = None) -> LLMResponse:
        config = types.GenerateContentConfig(
            system_instruction=system or None,
            temperature=self.temperature,
            max_output_tokens=self.max_tokens,
        )
        start = time.perf_counter()
        try:
            resp = self._client.models.generate_content(model=self.model, contents=prompt, config=config)
        except errors.APIError as exc:
            raise _translate(self.name, exc) from exc
        except Exception as exc:  # errores de red del cliente HTTP
            kind = type(exc).__name__.lower()
            if "timeout" in kind:
                raise ProviderTimeoutError(self.name, str(exc)) from exc
            if "connect" in kind or "network" in kind:
                raise ProviderConnectionError(self.name, str(exc)) from exc
            raise
        latency = time.perf_counter() - start

        text = (resp.text or "").strip()
        if not text:
            raise EmptyResponseError(self.name, "La respuesta llegó sin texto")
        prompt_tokens, completion_tokens, total = usage_tokens(resp.usage_metadata)
        return LLMResponse(
            provider=self.name,
            model=self.model,
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
            latency_s=latency,
        )


def _translate(provider: str, exc: errors.APIError) -> ProviderError:
    """Traduce un error de la API de Google a nuestro tipo de error."""
    code = exc.code or 0
    message = exc.message or str(exc)
    if code == 429:
        # Si Google pide esperar más que LLM_MAX_WAIT_SECONDS (por ejemplo, cuota diaria agotada),
        # retry.py no espera y el router pasa directo al respaldo.
        return RateLimitError(provider, message, retry_after=_retry_after(exc))
    if code in (401, 403):
        return AuthError(provider, message)
    if code >= 500:
        return ServerError(provider, message, retry_after=_retry_after(exc))
    if 400 <= code < 500:
        return BadRequestError(provider, message)
    return ProviderError(provider, message)
