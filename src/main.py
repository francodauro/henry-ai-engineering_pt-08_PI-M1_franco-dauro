"""CLI de triage: recibe una consulta y devuelve el contrato ``{answer, confidence, category, actions}``.

Uso:
    python -m src.main "consulta"
    python -m src.main --detalle "consulta"           # además: proveedor, tokens, latencia, costo e intentos
    python -m src.main --proveedor openai "consulta"  # forzar un proveedor (para probar el respaldo)
    python -m src.main --prompt v1 "consulta"         # elegir la versión del prompt

La salida estándar trae **solo el JSON validado**, para que otro sistema lo consuma sin transformaciones.
Los avisos y el detalle van a la salida de errores.

Códigos de salida: 0 ok · 2 consulta vacía · 3 fallaron todos los proveedores · 4 ningún intento cumplió
el contrato · 5 error de configuración.
"""

from __future__ import annotations

import argparse
import json
import sys

from .config import PROVIDER_NAMES, ConfigError, load_settings
from .costs import Pricing, PricingError, format_usd
from .llm.base import AllProvidersFailedError, ProviderError
from .llm.factory import build_providers
from .llm.router import Router
from .metrics import MetricsLog
from .prompts import PromptError, load_prompt
from .triage import ContractError, InvalidQueryError, TriageOutcome, triage

EXIT_OK = 0
EXIT_EMPTY_QUERY = 2
EXIT_ALL_FAILED = 3
EXIT_CONTRACT = 4
EXIT_CONFIG = 5


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m src.main", description="Triage de consultas de soporte de Nubbix.")
    parser.add_argument("consulta", help="consulta del cliente, entre comillas")
    parser.add_argument("--proveedor", choices=PROVIDER_NAMES, help="usar solo este proveedor (sin respaldo)")
    parser.add_argument("--prompt", help="versión del prompt (por ejemplo v1); por defecto, PROMPT_VERSION del .env")
    parser.add_argument("--detalle", action="store_true", help="mostrar proveedor, tokens, latencia, costo e intentos")
    return parser.parse_args(argv)


def describe(outcome: TriageOutcome) -> str:
    """Detalle de la llamada para una persona (el costo con 6 decimales, sin notación científica)."""
    r = outcome.response
    return (
        f"prompt: {outcome.prompt_version} · intentos de contrato: {outcome.attempts} · "
        f"proveedor: {r.provider} ({r.model}) · "
        f"tokens: {r.prompt_tokens} entrada / {r.completion_tokens} salida / {r.total_tokens} total · "
        f"latencia: {r.latency_s:.3f} s · costo: USD {format_usd(r.cost_usd)}"
    )


def warn(message: str) -> None:
    print(f"Aviso: {message}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    # Para que los acentos se vean bien en la consola de Windows.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    args = parse_args(argv)
    if not args.consulta.strip():
        print("Error: la consulta está vacía.", file=sys.stderr)
        return EXIT_EMPTY_QUERY

    try:
        settings = load_settings()
        template = load_prompt(args.prompt or settings.prompt_version, settings.prompts_dir)
        pricing = Pricing(settings.pricing_path)
        providers = build_providers(settings, only=args.proveedor)
        for provider in providers:
            pricing.price(provider.model)  # falla ahora si un modelo no tiene precio
    except (ConfigError, PromptError, PricingError, ProviderError) as exc:
        print(f"Error de configuración: {exc}", file=sys.stderr)
        return EXIT_CONFIG

    router = Router(
        providers,
        pricing,
        MetricsLog(settings.metrics_path),
        budget_usd=settings.budget_usd,
        max_retries=settings.max_retries,
        max_wait_s=settings.max_wait_seconds,
        on_failure=lambda name, exc: warn(f"{name} no respondió ({getattr(exc, 'kind', 'error')}): {exc}"),
    )
    try:
        outcome = triage(
            args.consulta, router, template,
            max_attempts=settings.contract_max_attempts,
            on_retry=lambda attempt, error: warn(f"el intento {attempt} no cumplió el contrato ({error}); se reintenta."),
        )
    except InvalidQueryError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_EMPTY_QUERY
    except AllProvidersFailedError:
        print("Error: ningún proveedor pudo responder (ver los avisos de arriba).", file=sys.stderr)
        return EXIT_ALL_FAILED
    except ContractError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_CONTRACT

    print(json.dumps(outcome.result.model_dump(), ensure_ascii=False, indent=2))
    if args.detalle:
        print(describe(outcome), file=sys.stderr)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
