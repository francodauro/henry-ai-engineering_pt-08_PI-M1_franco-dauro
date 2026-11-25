"""Plazos vagos en la respuesta al cliente ("a la brevedad", "en breve"...).

El prompt los prohíbe ("No prometas plazos"), pero la prueba real del paso 2 mostró que el modelo igual
escribió "a la brevedad": el prompt reduce el problema, no lo garantiza. Por eso se mide (evals, paso 3)
y se controla en código: el guardrail de salida (``src/guardrails.py``, paso 5) **saca** la expresión con
``remove_vague_timing`` antes de entregar la respuesta.

Esta lista es la **única fuente de verdad**: la usan las evals y el guardrail de salida. Agregar una
expresión es agregar una línea acá. Es determinista y no llama a ningún modelo.
"""

from __future__ import annotations

import re

# Expresiones regulares, una por expresión de tiempo vaga. [aá] acepta la palabra con o sin tilde.
VAGUE_TIMING_PATTERNS = (
    r"a la (?:mayor )?brevedad(?: posible)?",
    r"en breve",
    r"lo (?:m[aá]s )?antes posible",
    r"lo m[aá]s pronto posible",
    r"de inmediato",
    r"cuanto antes",
    r"en los pr[oó]ximos d[ií]as(?: h[aá]biles)?",
    r"en las pr[oó]ximas horas",
)

VAGUE_TIMING = re.compile(r"\b(?:" + "|".join(VAGUE_TIMING_PATTERNS) + r")\b", re.IGNORECASE)


def find_vague_timing(text: str | None) -> list[str]:
    """Devuelve las expresiones vagas encontradas, en minúsculas y en el orden en que aparecen.

    ``"Le responderemos a la brevedad."`` → ``["a la brevedad"]``; un texto sin plazos → ``[]``.
    """
    return [m.group(0).lower() for m in VAGUE_TIMING.finditer(text or "")]


# Para sacar la expresión se lleva también la coma y los espacios de adelante: "Le escribiremos, a la brevedad."
_REMOVABLE = re.compile(r"\s*,?\s*" + VAGUE_TIMING.pattern, re.IGNORECASE)


def remove_vague_timing(text: str) -> tuple[str, list[str]]:
    """Saca los plazos vagos del texto y devuelve también **cuáles** sacó (en minúsculas).

    ``"Le escribiremos a la brevedad."`` → ``("Le escribiremos.", ["a la brevedad"])``.
    ``"En breve, un agente lo contactará."`` → ``("Un agente lo contactará.", ["en breve"])``.
    Corregir en vez de rechazar: la respuesta sigue sirviendo sin la expresión (M1L4; lección de nubbix-triage).
    """
    removed = find_vague_timing(text)
    if not removed:
        return text, []
    out = _REMOVABLE.sub("", text)
    out = re.sub(r"\s+([.,;:!?])", r"\1", out)            # "usted ." → "usted."
    out = re.sub(r"(^|[.!?]\s+)[,;]\s*", r"\1", out)       # ", un agente…" al comienzo de una oración
    out = re.sub(r"\s{2,}", " ", out).strip()
    # Mayúscula al comienzo de cada oración, por si la expresión estaba primera.
    out = re.sub(r"(^|[.!?]\s+)([a-záéíóúñ])", lambda m: m.group(1) + m.group(2).upper(), out)
    return out, removed
