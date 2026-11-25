"""Construye los proveedores a partir de la configuración.

Es el único lugar que sabe qué clase corresponde a cada nombre: el router y la CLI solo ven ``LLMProvider``.
"""

from __future__ import annotations

from ..config import ProviderSettings, Settings
from .base import LLMProvider
from .gemini_provider import GeminiProvider
from .openai_provider import OpenAIProvider


def build_provider(ps: ProviderSettings, settings: Settings) -> LLMProvider:
    common = {
        "api_key": ps.api_key,
        "model": ps.model,
        "max_tokens": ps.max_tokens,
        "temperature": settings.temperature,
        "timeout_s": settings.timeout_seconds,
    }
    if ps.name == "gemini":
        return GeminiProvider(**common)
    if ps.name == "openai":
        return OpenAIProvider(**common, reasoning_effort=ps.reasoning_effort)
    raise ValueError(f"Proveedor desconocido: {ps.name}")


def build_providers(settings: Settings, only: str | None = None) -> list[LLMProvider]:
    """Proveedores en el orden de ``LLM_PROVIDER_ORDER``, o solo ``only`` si se pide uno."""
    names = [only] if only else settings.provider_order
    return [build_provider(settings.providers[name], settings) for name in names]
