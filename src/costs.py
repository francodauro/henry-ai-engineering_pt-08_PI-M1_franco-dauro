"""Costo de cada llamada, calculado con los tokens reales y la tabla de precios.

    costo = tokens_entrada / 1.000.000 × precio_entrada + tokens_salida / 1.000.000 × precio_salida

Los tokens salen siempre del ``usage`` que devuelve la API (nunca de una estimación) y los precios
viven en ``config/pricing.json``, con su fuente y fecha. Así cualquiera puede rehacer la cuenta.
"""

from __future__ import annotations

import json
from pathlib import Path


class PricingError(Exception):
    """Un modelo no tiene precio en config/pricing.json."""


class Pricing:
    def __init__(self, path: Path):
        with open(path, encoding="utf-8") as f:
            self._models: dict[str, dict[str, float]] = json.load(f)["models"]

    def price(self, model: str) -> dict[str, float]:
        try:
            return self._models[model]
        except KeyError as exc:
            raise PricingError(
                f"El modelo {model!r} no tiene precio en config/pricing.json. "
                "Agregalo antes de usarlo, así el costo queda auditable."
            ) from exc

    def is_paid(self, model: str) -> bool:
        p = self.price(model)
        return p["input"] > 0 or p["output"] > 0

    def cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        p = self.price(model)
        return prompt_tokens / 1_000_000 * p["input"] + completion_tokens / 1_000_000 * p["output"]


def format_usd(amount: float) -> str:
    """Costo para mostrar en pantalla: 6 decimales, sin notación científica (0.000018, no 1.8e-05)."""
    return f"{amount:.6f}"
