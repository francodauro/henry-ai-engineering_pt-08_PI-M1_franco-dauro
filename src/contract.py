"""Contrato de salida del triage: ``{answer, confidence, category, actions}`` validado con Pydantic.

Un contrato débil (``category: str``, ``confidence: float``) valida tipos pero no dominio: deja pasar
``category="factura"`` o ``confidence=47``. Este valida **tipo y dominio** (M1L3 · Validación con Pydantic).

Categorías y acciones viven solo acá (única fuente de verdad): de estos diccionarios salen el contrato,
el JSON Schema de la tool call y las listas que se inyectan en el prompt.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .llm.base import ToolSpec

# Categoría → qué cubre. La descripción se inyecta en el prompt con {categorias}.
CATEGORIES: dict[str, str] = {
    "billing": "la suscripción a Nubbix y lo que Nubbix le cobra al cliente: cobros, devoluciones, facturas de Nubbix, medios de pago, plan contratado",
    "technical": "algo de la plataforma no funciona como debería: errores, caídas, lentitud, fallas de integraciones, de la app o de los reportes",
    "account": "la cuenta y los accesos: usuarios, roles y permisos, inicio de sesión, contraseñas, datos de la cuenta",
    "other": "cualquier consulta que no encaje en las anteriores: información comercial o general",
}

# Acciones que se le pueden sugerir al agente humano. Las cinco primeras acompañan a una categoría;
# las tres últimas sirven para cualquiera. Se inyectan en el prompt con {acciones}.
ACTIONS: dict[str, str] = {
    "review_charge": "revisar un cobro, un cobro duplicado o un pedido de devolución",
    "resend_invoice": "reenviar o corregir una factura emitida por Nubbix",
    "investigate_incident": "investigar una falla técnica: error, caída, lentitud o una integración que no funciona",
    "manage_access": "gestionar usuarios, roles, permisos o el acceso a la cuenta",
    "contact_sales": "derivar a ventas una consulta comercial: planes, precios, descuentos o condiciones",
    "request_more_info": "pedirle al cliente los datos que faltan para poder avanzar",
    "escalate_to_human": "pasar el caso de inmediato a una persona: urgencia, riesgo para el negocio del cliente o cliente muy molesto",
    "no_action": "no hace falta ninguna acción (va sola, nunca combinada con otras)",
}
NO_ACTION = "no_action"

CategoryName = Literal[tuple(CATEGORIES)]
ActionName = Literal[tuple(ACTIONS)]

ANSWER_MAX_CHARS = 500


# El contrato. Si un dato no lo cumple, ``model_validate`` lanza ``ValidationError``.
class TriageResult(BaseModel):
    """Triage de una consulta de soporte de Nubbix."""  # Pydantic lo usa como descripción en el schema

    # Campos de más se rechazan; los espacios al principio y al final se recortan.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    answer: str = Field(
        min_length=1,
        max_length=ANSWER_MAX_CHARS,
        description="Primera respuesta breve para el cliente, en el idioma de la consulta (en español, de usted).",
    )
    # strict: un "0.9" escrito como texto se rechaza; tiene que llegar un número.
    confidence: float = Field(ge=0.0, le=1.0, strict=True, description="Qué tan seguro estás de la categoría, de 0 a 1.")
    category: CategoryName = Field(description="Equipo al que se deriva la consulta.")
    actions: list[ActionName] = Field(min_length=1, description="Acciones sugeridas para el agente humano, sin repetir.")

    @field_validator("actions")
    @classmethod
    def _action_rules(cls, actions: list[str]) -> list[str]:
        if len(set(actions)) != len(actions):
            raise ValueError("hay acciones repetidas")
        if NO_ACTION in actions and len(actions) > 1:
            raise ValueError(f"'{NO_ACTION}' no se combina con otras acciones")
        return actions


# El schema de la tool call sale del contrato: no se escribe dos veces (M1L3 · Tool use).
TRIAGE_TOOL = ToolSpec(
    name="registrar_triage",
    description=(
        "Registra el triage de la consulta del cliente: categoría, respuesta breve para el cliente, "
        "confianza y acciones sugeridas para el agente humano."
    ),
    parameters=TriageResult.model_json_schema(),
)


def describe_errors(exc: ValidationError) -> str:
    """Qué campo falló y por qué, en una línea, para el reintento y para la pantalla.

    No incluye el valor recibido: el mensaje vuelve al modelo y no hace falta repetir lo que generó.
    """
    return "; ".join(f"{_location(e)}: {e['msg']}" for e in exc.errors())


def error_codes(exc: ValidationError) -> list[str]:
    """Versión corta para las métricas, sin texto: ``campo:tipo`` (por ejemplo ``category:literal_error``)."""
    return [f"{_location(e)}:{e['type']}" for e in exc.errors()]


def _location(error: dict) -> str:
    return ".".join(str(part) for part in error["loc"]) or "contrato"
