"""Triage validado: consulta → tool call → contrato Pydantic, con reintentos que informan el error.

Dos capas de reintento distintas, que no se mezclan:
- Red y proveedor (paso 1): 429, 5xx, timeouts → ``src/retry.py`` + fallback del router.
- Contrato (este módulo): la respuesta llegó pero no cumple el contrato → se vuelve a pedir, hasta
  ``max_attempts`` veces, diciéndole al modelo **qué campo falló y por qué** (M1L3 · Reintentos).
  Repetir la misma llamada sin decir nada sería apostar al azar.

El error va al **system prompt** (es una corrección de cómo responder, no un dato del cliente). Se agrega
solo el último error, para que el prompt no crezca en cada intento.

``guarded_triage`` (paso 5) envuelve a ``triage`` con las dos compuertas de ``src/guardrails.py``: la de entrada
antes de llamar al modelo y la de salida antes de entregar la respuesta.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from pydantic import ValidationError

from . import guardrails
from .contract import TRIAGE_TOOL, TriageResult, describe_errors, error_codes
from .llm.base import TOOL_BAD_JSON, TOOL_NO_CALL, TOOL_NOT_OBJECT, LLMResponse
from .llm.router import Router
from .metrics import MetricsLog
from .prompts import PromptTemplate, render_system, render_user

RETRY_NOTE = "\n\n(Tu respuesta anterior fue inválida: {error}. Corrígela y vuelve a llamar a la función {tool}.)"

_TOOL_ERROR_TEXT = {
    TOOL_NO_CALL: "no llamaste a la función {tool}, respondiste con texto",
    TOOL_BAD_JSON: "los argumentos de la función no son un JSON válido (¿se cortaron?)",
    TOOL_NOT_OBJECT: "los argumentos de la función deben ser un objeto JSON con los campos del contrato",
}


class InvalidQueryError(Exception):
    """La consulta no se puede procesar (por ejemplo, vacía). No se reintenta ni se llama al modelo."""


class ContractError(Exception):
    """Se agotaron los intentos sin obtener una respuesta que cumpla el contrato."""

    def __init__(self, message: str, attempts: int):
        super().__init__(message)
        self.attempts = attempts


@dataclass
class TriageOutcome:
    result: TriageResult
    response: LLMResponse   # la respuesta que cumplió el contrato (proveedor, tokens, latencia, costo)
    attempts: int           # intentos de contrato que hicieron falta
    request_id: str
    prompt_version: str


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


def validate(response: LLMResponse) -> tuple[TriageResult | None, str | None, list[str]]:
    """Valida la respuesta contra el contrato. Devuelve (resultado, error para el modelo, códigos para métricas)."""
    if response.tool_args is None:
        reason = response.tool_error or TOOL_NO_CALL
        return None, _TOOL_ERROR_TEXT.get(reason, reason).format(tool=TRIAGE_TOOL.name), [f"tool:{reason}"]
    try:
        return TriageResult.model_validate(response.tool_args), None, []
    except ValidationError as exc:
        return None, describe_errors(exc), error_codes(exc)


def triage(query: str, router: Router, template: PromptTemplate, *, max_attempts: int = 3,
           on_retry=None, request_id: str | None = None) -> TriageOutcome:
    """Clasifica ``query`` y devuelve un contrato válido.

    :param on_retry: función opcional ``(intento, error)`` para avisar al usuario que se reintenta.
    :raises InvalidQueryError: si la consulta está vacía (sin llamar al modelo).
    :raises ContractError: si ningún intento cumple el contrato.
    :raises AllProvidersFailedError: si no respondió ningún proveedor (lo lanza el router).
    """
    if not query or not query.strip():
        raise InvalidQueryError("La consulta está vacía.")

    request_id = request_id or new_request_id()  # agrupa en las métricas los intentos de una misma consulta
    base_system = render_system(template)
    user = render_user(template, query.strip())
    error: str | None = None
    for attempt in range(1, max_attempts + 1):
        system = base_system if error is None else base_system + RETRY_NOTE.format(error=error, tool=TRIAGE_TOOL.name)
        checked: dict = {}

        def contract_fields(response: LLMResponse) -> dict:
            checked["outcome"] = validate(response)
            _, _, codes = checked["outcome"]
            return {"contract_attempt": attempt, "contract_valid": not codes, "contract_errors": codes}

        response = router.ask(
            user, system, tool=TRIAGE_TOOL,
            context={"prompt_version": template.version, "request_id": request_id},
            extra_fields=contract_fields,
        )
        result, error, _ = checked["outcome"]
        if result is not None:
            return TriageOutcome(result, response, attempt, request_id, template.version)
        if on_retry is not None and attempt < max_attempts:
            on_retry(attempt, error)
    raise ContractError(f"Ningún intento cumplió el contrato. Último error: {error}", max_attempts)


# --------------------------------------------------------------------------- con guardrails (paso 5)


@dataclass
class GuardedOutcome:
    """Resultado del triage con las dos compuertas. ``result`` es siempre un contrato válido: lo que se entrega."""

    result: TriageResult
    decision: str                       # guardrails.OK, CORRECTED, BLOCKED o REVIEW
    request_id: str
    prompt_version: str
    input_rules: list[str] = field(default_factory=list)
    output_rules: list[str] = field(default_factory=list)
    vague_removed: list[str] = field(default_factory=list)
    model_answer: str | None = None     # lo que escribió el modelo, antes de la compuerta de salida
    outcome: TriageOutcome | None = None  # None si la consulta se bloqueó (no se llamó al modelo)


def guarded_triage(query: str, router: Router, template: PromptTemplate, metrics: MetricsLog, *,
                   max_attempts: int = 3, on_retry=None, context: dict | None = None) -> GuardedOutcome:
    """Triage con la compuerta de entrada antes del modelo y la de salida después (M1L4 · dos compuertas).

    Cuando una compuerta actúa, deja una línea en ``data/metrics.jsonl`` con qué regla y qué decisión, sin el
    texto. Una consulta bloqueada no llama al modelo: su línea es la única de ese request (tokens y costo 0).

    :raises InvalidQueryError, ContractError, AllProvidersFailedError: igual que ``triage``.
    """
    if not query or not query.strip():
        raise InvalidQueryError("La consulta está vacía.")
    request_id = new_request_id()
    base = {**(context or {}), "event": "guardrail", "prompt_version": template.version, "request_id": request_id}

    input_rules = guardrails.check_input(query)
    if input_rules:
        metrics.append({**base, "gate": "entrada", "decision": guardrails.BLOCKED, "rules": input_rules,
                        "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "latency_s": 0.0,
                        "cost_usd": 0.0})
        return GuardedOutcome(guardrails.blocked_result(), guardrails.BLOCKED, request_id, template.version,
                              input_rules=input_rules)

    outcome = triage(guardrails.escape_tags(query), router, template, max_attempts=max_attempts,
                     on_retry=on_retry, request_id=request_id)
    checked = guardrails.check_output(outcome.result)
    if checked.decision != guardrails.OK:
        metrics.append({**base, "gate": "salida", "decision": checked.decision, "rules": checked.rules, "cost_usd": 0.0})
    return GuardedOutcome(checked.result, checked.decision, request_id, template.version,
                          output_rules=checked.rules, vague_removed=checked.vague_removed,
                          model_answer=outcome.result.answer, outcome=outcome)
