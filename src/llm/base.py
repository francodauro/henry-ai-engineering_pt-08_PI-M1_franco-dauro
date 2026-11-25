"""Abstracción común para los proveedores de LLM.

Todos los proveedores heredan de ``LLMProvider`` y devuelven el mismo ``LLMResponse``: el resto
del sistema no sabe (ni le importa) qué proveedor respondió. Sumar un proveedor = sumar una subclase.

Los errores de cada SDK se traducen a las subclases de ``ProviderError`` de este archivo. Cada una
dice si es transitoria (``retryable``): solo esas se reintentan.

Tool calling (paso 2): ``complete(..., tool=...)`` obliga al modelo a "llenar el formulario" de una
función. OpenAI entrega los argumentos como texto JSON y Gemini como dict: cada proveedor los convierte
y deja siempre un dict en ``tool_args`` (o ``None`` con el motivo en ``tool_error``).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolSpec:
    """Función que el modelo está obligado a llamar. No existe en Python: es un formulario.

    ``parameters`` es el JSON Schema de sus argumentos (sale del contrato Pydantic).
    """

    name: str
    description: str
    parameters: dict[str, Any]


# Por qué ``tool_args`` quedó en None (se registra y se le explica al modelo al reintentar).
TOOL_NO_CALL = "sin_tool_call"        # respondió texto en vez de llamar a la función
TOOL_BAD_JSON = "json_invalido"       # OpenAI: los argumentos no son JSON válido (por ejemplo, cortados)
TOOL_NOT_OBJECT = "args_no_objeto"    # el JSON es válido pero no es un objeto {...}


@dataclass
class LLMResponse:
    """Respuesta normalizada de cualquier proveedor."""

    provider: str
    model: str
    text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_s: float
    # Lo completa el router con config/pricing.json (el proveedor no conoce los precios).
    cost_usd: float = 0.0
    # Solo con tool calling: argumentos como dict, o None con el motivo en tool_error.
    tool_args: dict[str, Any] | None = None
    tool_error: str | None = None


# --------------------------------------------------------------------------- errores


class ProviderError(Exception):
    """Falla de un proveedor. ``retryable`` indica si tiene sentido reintentar."""

    kind = "provider_error"
    retryable = False

    def __init__(self, provider: str, message: str, *, retry_after: float | None = None):
        super().__init__(f"[{provider}] {message}")
        self.provider = provider
        # Segundos que el servidor pidió esperar (header Retry-After), si lo mandó.
        self.retry_after = retry_after
        # Intentos hechos antes de rendirse (lo completa retry.py, se guarda en las métricas).
        self.attempts = 1


class RateLimitError(ProviderError):
    """429: demasiadas llamadas. Transitorio: esperar y reintentar."""

    kind = "rate_limit"
    retryable = True


class ServerError(ProviderError):
    """5xx: falla o sobrecarga del servidor del proveedor. Transitorio."""

    kind = "server_error"
    retryable = True


class ProviderTimeoutError(ProviderError):
    """La respuesta tardó más que el timeout configurado. Transitorio."""

    kind = "timeout"
    retryable = True


class ProviderConnectionError(ProviderError):
    """No se pudo conectar (red caída, DNS). Transitorio."""

    kind = "connection_error"
    retryable = True


class QuotaExhaustedError(ProviderError):
    """429 por cuota o saldo agotado: esperar no lo resuelve, no se reintenta."""

    kind = "quota_exhausted"


class AuthError(ProviderError):
    """401/403 o clave faltante: reintentar no sirve."""

    kind = "auth_error"


class BadRequestError(ProviderError):
    """Otro 4xx (por ejemplo, modelo inexistente): reintentar no sirve."""

    kind = "bad_request"


class EmptyResponseError(ProviderError):
    """El proveedor respondió sin texto."""

    kind = "empty_response"


class BudgetExceededError(Exception):
    """Se alcanzó el tope de gasto (BUDGET_USD): no se llama al proveedor pago."""

    kind = "budget_exceeded"


class AllProvidersFailedError(Exception):
    """Ningún proveedor pudo responder."""

    def __init__(self, errors: list[Exception]):
        detail = "; ".join(str(e) for e in errors)
        super().__init__(f"Todos los proveedores fallaron: {detail}")
        self.errors = errors


# --------------------------------------------------------------------------- abstracción


class LLMProvider(ABC):
    """Un proveedor de LLM. Cada subclase implementa ``complete`` con su SDK."""

    name: str = "base"

    def __init__(self, model: str, max_tokens: int, temperature: float, timeout_s: float):
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout_s = timeout_s

    @abstractmethod
    def complete(self, prompt: str, system: str | None = None, tool: ToolSpec | None = None) -> LLMResponse:
        """Envía ``prompt`` (y las instrucciones ``system``, si hay) y devuelve un ``LLMResponse``.

        Con ``tool``, obliga al modelo a llamar a esa función y completa ``tool_args``. No valida el
        contenido: eso lo hace el contrato Pydantic. Debe traducir los errores del SDK a ``ProviderError``.
        """
