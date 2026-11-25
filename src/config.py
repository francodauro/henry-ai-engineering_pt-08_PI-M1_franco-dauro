"""Configuración desde variables de entorno (archivo ``.env``, documentado en ``.env.example``).

Todo llega como texto: se convierte y se valida acá, para que un error de configuración se vea
al arrancar y con un mensaje claro, no en medio de una llamada.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Raíz del proyecto: la carpeta que contiene src/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

PROVIDER_NAMES = ("gemini", "openai")


class ConfigError(Exception):
    """La configuración es inválida o incompleta."""


@dataclass(frozen=True)
class ProviderSettings:
    name: str
    api_key: str
    model: str
    max_tokens: int
    # Solo OpenAI: "none" para que gpt-6-luna no razone. Vacío = no se envía el parámetro.
    reasoning_effort: str = ""


@dataclass(frozen=True)
class Settings:
    providers: dict[str, ProviderSettings]
    provider_order: list[str]
    temperature: float
    max_retries: int
    max_wait_seconds: float
    timeout_seconds: float
    budget_usd: float
    pricing_path: Path = PROJECT_ROOT / "config" / "pricing.json"
    metrics_path: Path = PROJECT_ROOT / "data" / "metrics.jsonl"


def _get(name: str, default: str) -> str:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


def _number(name: str, default: float, cast: type = float, minimum: float = 0) -> float:
    raw = _get(name, str(default))
    try:
        value = cast(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} debe ser un número, llegó: {raw!r}") from exc
    if value < minimum:
        raise ConfigError(f"{name} no puede ser menor que {minimum}, llegó: {value}")
    return value


def load_settings(env_file: Path | None = None) -> Settings:
    """Lee el ``.env`` (si existe) y las variables de entorno, y devuelve la configuración validada."""
    load_dotenv(env_file or PROJECT_ROOT / ".env")

    order = [p.strip().lower() for p in _get("LLM_PROVIDER_ORDER", "gemini,openai").split(",") if p.strip()]
    unknown = [p for p in order if p not in PROVIDER_NAMES]
    if not order or unknown:
        raise ConfigError(f"LLM_PROVIDER_ORDER solo admite {', '.join(PROVIDER_NAMES)}; llegó: {order}")

    providers = {
        "gemini": ProviderSettings(
            name="gemini",
            api_key=_get("GEMINI_API_KEY", ""),
            model=_get("GEMINI_MODEL", "gemini-3.5-flash-lite"),
            max_tokens=int(_number("GEMINI_MAX_TOKENS", 1024, int, 1)),
        ),
        "openai": ProviderSettings(
            name="openai",
            api_key=_get("OPENAI_API_KEY", ""),
            model=_get("OPENAI_MODEL", "gpt-6-luna"),
            max_tokens=int(_number("OPENAI_MAX_TOKENS", 400, int, 1)),
            reasoning_effort=_get("OPENAI_REASONING_EFFORT", "none"),
        ),
    }
    return Settings(
        providers=providers,
        provider_order=order,
        temperature=_number("LLM_TEMPERATURE", 0.0),
        max_retries=int(_number("LLM_MAX_RETRIES", 2, int)),
        max_wait_seconds=_number("LLM_MAX_WAIT_SECONDS", 10.0),
        timeout_seconds=_number("LLM_TIMEOUT_SECONDS", 30.0, float, 1),
        budget_usd=_number("BUDGET_USD", 4.50),
    )
