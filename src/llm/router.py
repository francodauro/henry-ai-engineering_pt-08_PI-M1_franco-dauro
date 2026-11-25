"""Router: llama a los proveedores en orden, con reintentos, tope de gasto, costo y métricas.

- El primero de la lista es el primario; si falla (después de sus reintentos), se prueba el siguiente.
- Antes de llamar a un proveedor pago se suma lo gastado en ``data/metrics.jsonl``; si llegó a
  ``budget_usd``, ese proveedor no se llama.
- Cada intento por proveedor (exitoso, fallido u omitido) deja una línea en las métricas.
"""

from __future__ import annotations

from typing import Callable

from ..costs import Pricing
from ..metrics import MetricsLog
from ..retry import call_with_backoff
from .base import AllProvidersFailedError, BudgetExceededError, LLMProvider, LLMResponse, ProviderError


class Router:
    def __init__(
        self,
        providers: list[LLMProvider],
        pricing: Pricing,
        metrics: MetricsLog,
        *,
        budget_usd: float,
        max_retries: int,
        max_wait_s: float,
        sleep: Callable[[float], None] | None = None,
        on_failure: Callable[[str, Exception], None] | None = None,
    ):
        if not providers:
            raise ValueError("El router necesita al menos un proveedor")
        self.providers = providers
        self.pricing = pricing
        self.metrics = metrics
        self.budget_usd = budget_usd
        self.max_retries = max_retries
        self.max_wait_s = max_wait_s
        self._sleep = sleep
        # Se llama cada vez que un proveedor falla o se omite, para que la CLI avise al usuario.
        self._on_failure = on_failure

    def ask(self, prompt: str, system: str | None = None) -> LLMResponse:
        """Devuelve la respuesta del primer proveedor que responda. Si ninguno puede, lanza ``AllProvidersFailedError``."""
        errors: list[Exception] = []
        for index, provider in enumerate(self.providers):
            base = {
                "provider": provider.name,
                "model": provider.model,
                "temperature": provider.temperature,
                "fallback": index > 0,
            }

            if self.pricing.is_paid(provider.model):
                spent = self.metrics.total_cost()
                if spent >= self.budget_usd:
                    err = BudgetExceededError(
                        f"Tope de gasto alcanzado: USD {spent:.4f} de USD {self.budget_usd:.2f}. "
                        f"No se llama a {provider.name}."
                    )
                    self.metrics.append({**base, "status": "skipped", "error_kind": err.kind, "cost_usd": 0.0})
                    errors.append(err)
                    self._notify(provider.name, err)
                    continue

            kwargs = {"max_retries": self.max_retries, "max_wait_s": self.max_wait_s}
            if self._sleep is not None:
                kwargs["sleep"] = self._sleep
            try:
                response, attempts = call_with_backoff(lambda p=provider: p.complete(prompt, system), **kwargs)
            except ProviderError as exc:
                self.metrics.append({
                    **base,
                    "status": "error",
                    "error_kind": exc.kind,
                    "attempts": exc.attempts,
                    "cost_usd": 0.0,
                })
                errors.append(exc)
                self._notify(provider.name, exc)
                continue

            response.cost_usd = self.pricing.cost(response.model, response.prompt_tokens, response.completion_tokens)
            self.metrics.append({
                **base,
                "status": "ok",
                "attempts": attempts,
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
                "total_tokens": response.total_tokens,
                "latency_s": round(response.latency_s, 3),
                "cost_usd": response.cost_usd,
            })
            return response

        raise AllProvidersFailedError(errors)

    def _notify(self, provider_name: str, exc: Exception) -> None:
        if self._on_failure is not None:
            self._on_failure(provider_name, exc)
