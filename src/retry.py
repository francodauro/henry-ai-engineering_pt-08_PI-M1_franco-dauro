"""Reintentos con backoff exponencial y jitter, respetando Retry-After.

- Solo se reintentan los errores transitorios (``retryable``): 429, 5xx, timeout y red.
- Espera entre intentos: 1 s, 2 s, 4 s… más un extra al azar de hasta 1 s (jitter), para que muchos
  clientes no reintenten todos a la vez.
- Si el servidor manda ``Retry-After``, ese valor manda sobre el cálculo.
- Si la espera pedida supera ``max_wait_s``, no se espera: se corta y el router pasa al respaldo.
"""

from __future__ import annotations

import random
import time
from typing import Callable, TypeVar

from .llm.base import ProviderError

T = TypeVar("T")


def backoff_seconds(attempt: int, rand: Callable[[], float] = random.random) -> float:
    """Espera antes del reintento número ``attempt`` (1, 2, 3…): 2^(attempt-1) + jitter de 0 a 1 s."""
    return 2 ** (attempt - 1) + rand()


def call_with_backoff(
    fn: Callable[[], T],
    *,
    max_retries: int,
    max_wait_s: float,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[T, int]:
    """Ejecuta ``fn`` y la reintenta ante errores transitorios.

    :param fn: función sin argumentos que hace la llamada al proveedor.
    :param max_retries: reintentos además del primer intento.
    :param max_wait_s: espera máxima aceptable entre intentos.
    :param sleep: función de espera (se reemplaza en los tests para no esperar de verdad).
    :return: (resultado, intentos hechos).
    :raises ProviderError: el último error, si no es transitorio, se agotaron los intentos o pide esperar demasiado.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            return fn(), attempt
        except ProviderError as exc:
            exc.attempts = attempt
            if not exc.retryable or attempt > max_retries:
                raise
            wait = exc.retry_after if exc.retry_after is not None else backoff_seconds(attempt)
            if wait > max_wait_s:
                raise
            sleep(wait)
