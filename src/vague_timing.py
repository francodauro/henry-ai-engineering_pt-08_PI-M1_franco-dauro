"""Plazos vagos en la respuesta al cliente ("a la brevedad", "en breve"...).

El prompt los prohíbe ("No prometas plazos"), pero la prueba real del paso 2 mostró que el modelo igual
escribió "a la brevedad": el prompt reduce el problema, no lo garantiza. Por eso se mide (evals, paso 3)
y después se controla en código (guardrail de salida, paso 5).

Esta lista es la **única fuente de verdad**: la usan las evals y la va a usar el guardrail. Agregar una
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
