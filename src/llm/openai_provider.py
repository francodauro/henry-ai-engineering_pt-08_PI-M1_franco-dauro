"""Proveedor de respaldo (pago): OpenAI, con el SDK ``openai``.

``gpt-6-luna`` es un modelo de razonamiento. Con ``reasoning_effort="none"`` no "piensa" antes de
responder: es más rápido, más barato y acepta ``temperature=0``.
Los tokens salen del campo ``usage`` de la respuesta.

Tool calling: ``tools`` + ``tool_choice`` con el nombre de la función obligan al modelo a llamarla.
OpenAI entrega los argumentos como **texto JSON**: hay que convertirlo con ``json.loads``, que puede
fallar si llegó cortado (por ejemplo, por el tope de tokens).
"""

from __future__ import annotations

import json
import time

import openai

from .base import (
    AuthError,
    BadRequestError,
    EmptyResponseError,
    LLMProvider,
    LLMResponse,
    ProviderConnectionError,
    ProviderError,
    ProviderTimeoutError,
    QuotaExhaustedError,
    RateLimitError,
    ServerError,
    TOOL_BAD_JSON,
    TOOL_NO_CALL,
    TOOL_NOT_OBJECT,
    ToolSpec,
)


def _retry_after(exc: openai.APIStatusError) -> float | None:
    """Lee el header Retry-After (en segundos), si el servidor lo mandó."""
    try:
        value = exc.response.headers.get("retry-after")
        return float(value) if value is not None else None
    except (AttributeError, ValueError):
        return None


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(
        self,
        api_key: str,
        model: str,
        max_tokens: int,
        temperature: float,
        timeout_s: float,
        reasoning_effort: str = "",
    ):
        super().__init__(model, max_tokens, temperature, timeout_s)
        if not api_key:
            raise AuthError(self.name, "Falta OPENAI_API_KEY en el .env")
        self.reasoning_effort = reasoning_effort
        # max_retries=0: los reintentos los maneja src/retry.py, para no sumar los del SDK.
        self._client = openai.OpenAI(api_key=api_key, max_retries=0, timeout=timeout_s)

    def complete(self, prompt: str, system: str | None = None, tool: ToolSpec | None = None) -> LLMResponse:
        messages = [{"role": "user", "content": prompt}]
        if system:
            messages.insert(0, {"role": "system", "content": system})
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            # max_completion_tokens: el parámetro vigente (los modelos de razonamiento no aceptan max_tokens).
            "max_completion_tokens": self.max_tokens,
        }
        if self.reasoning_effort:
            params["reasoning_effort"] = self.reasoning_effort
        if tool is not None:
            params["tools"] = [{"type": "function", "function": {
                "name": tool.name, "description": tool.description, "parameters": tool.parameters}}]
            # Obliga a llamar a ESTA función (equivale a mode="ANY" de Gemini).
            params["tool_choice"] = {"type": "function", "function": {"name": tool.name}}

        start = time.perf_counter()
        try:
            resp = self._client.chat.completions.create(**params)
        except openai.RateLimitError as exc:
            body = getattr(exc, "body", None) or {}
            if isinstance(body, dict) and body.get("code") == "insufficient_quota":
                raise QuotaExhaustedError(self.name, "Sin saldo en la cuenta de OpenAI (insufficient_quota)") from exc
            raise RateLimitError(self.name, str(exc), retry_after=_retry_after(exc)) from exc
        except (openai.AuthenticationError, openai.PermissionDeniedError) as exc:
            raise AuthError(self.name, str(exc)) from exc
        except (openai.BadRequestError, openai.NotFoundError, openai.UnprocessableEntityError) as exc:
            raise BadRequestError(self.name, str(exc)) from exc
        except openai.APITimeoutError as exc:
            raise ProviderTimeoutError(self.name, str(exc)) from exc
        except openai.APIConnectionError as exc:
            raise ProviderConnectionError(self.name, str(exc)) from exc
        except openai.APIStatusError as exc:
            if exc.status_code >= 500:
                raise ServerError(self.name, str(exc), retry_after=_retry_after(exc)) from exc
            raise ProviderError(self.name, str(exc)) from exc
        latency = time.perf_counter() - start

        message = resp.choices[0].message
        tool_args, tool_error = None, None
        if tool is not None:
            calls = message.tool_calls or []
            if calls:
                text = calls[0].function.arguments or ""  # texto JSON
                tool_args, tool_error = parse_arguments(text)
            else:
                text = (message.content or "").strip()
                tool_error = TOOL_NO_CALL
        else:
            text = (message.content or "").strip()
            if not text:
                raise EmptyResponseError(self.name, f"La respuesta llegó sin texto (finish_reason={resp.choices[0].finish_reason})")
        usage = resp.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        return LLMResponse(
            provider=self.name,
            model=self.model,
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=usage.total_tokens if usage else prompt_tokens + completion_tokens,
            latency_s=latency,
            tool_args=tool_args,
            tool_error=tool_error,
        )


def parse_arguments(raw: str) -> tuple[dict | None, str | None]:
    """Convierte el texto JSON de OpenAI en dict. Devuelve (args, None) o (None, motivo)."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None, TOOL_BAD_JSON
    if not isinstance(data, dict):
        return None, TOOL_NOT_OBJECT
    return data, None
