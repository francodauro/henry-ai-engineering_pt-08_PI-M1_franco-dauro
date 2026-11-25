"""CLI mínima del paso 1: manda una consulta al modelo y muestra su respuesta, todavía sin contrato.

Uso:
    python -m src.main "consulta"
    python -m src.main --detalle "consulta"           # además: proveedor, tokens, latencia y costo
    python -m src.main --proveedor openai "consulta"  # forzar un proveedor (para probar el respaldo)

La respuesta va a la salida estándar. Los avisos y el detalle van a la salida de errores, así la
salida estándar queda limpia para otro programa.

Códigos de salida: 0 ok · 2 consulta vacía · 3 fallaron todos los proveedores · 5 error de configuración.
"""

from __future__ import annotations

import argparse
import sys

from .config import PROVIDER_NAMES, ConfigError, load_settings
from .costs import Pricing, PricingError, format_usd
from .llm.base import AllProvidersFailedError, LLMResponse, ProviderError
from .llm.factory import build_providers
from .llm.router import Router
from .metrics import MetricsLog

EXIT_OK = 0
EXIT_EMPTY_QUERY = 2
EXIT_ALL_FAILED = 3
EXIT_CONFIG = 5


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m src.main", description="Triage de consultas de soporte de Nubbix (paso 1: sin contrato).")
    parser.add_argument("consulta", help="consulta del cliente, entre comillas")
    parser.add_argument("--proveedor", choices=PROVIDER_NAMES, help="usar solo este proveedor (sin respaldo)")
    parser.add_argument("--detalle", action="store_true", help="mostrar proveedor, tokens, latencia y costo")
    return parser.parse_args(argv)


def describe(response: LLMResponse) -> str:
    """Detalle de la llamada para una persona (el costo con 6 decimales, sin notación científica)."""
    return (
        f"proveedor: {response.provider} ({response.model}) · "
        f"tokens: {response.prompt_tokens} entrada / {response.completion_tokens} salida / {response.total_tokens} total · "
        f"latencia: {response.latency_s:.3f} s · costo: USD {format_usd(response.cost_usd)}"
    )


def warn(message: str) -> None:
    print(f"Aviso: {message}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    # Para que los acentos se vean bien en la consola de Windows.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    args = parse_args(argv)
    query = args.consulta.strip()
    if not query:
        print("Error: la consulta está vacía.", file=sys.stderr)
        return EXIT_EMPTY_QUERY

    try:
        settings = load_settings()
        pricing = Pricing(settings.pricing_path)
        providers = build_providers(settings, only=args.proveedor)
        for provider in providers:
            pricing.price(provider.model)  # falla ahora si un modelo no tiene precio
    except (ConfigError, PricingError, ProviderError) as exc:
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
        response = router.ask(query)
    except AllProvidersFailedError:
        print("Error: ningún proveedor pudo responder (ver los avisos de arriba).", file=sys.stderr)
        return EXIT_ALL_FAILED

    print(response.text)
    if args.detalle:
        print(describe(response), file=sys.stderr)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
