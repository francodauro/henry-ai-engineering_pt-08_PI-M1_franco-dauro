# Changelog de prompts

Cada versión es un archivo nuevo en `prompts/` y nunca se edita. Para cada una: qué cambió, por qué y con qué resultado.

## triage_v3 — 2026-11-25

- **Cambio:** `v1` + un par de contraste nuevo (few-shot). Respecto de `v2` cambian solo los ejemplos.
- **Por qué:** en `v2` el ejemplo de `billing` compartía tema y palabras con NX-036 ("¿cuánto cuesta agregar el módulo…?") y `gpt-6-luna` se guió por el parecido de superficie. Los ejemplos nuevos hablan de un tema que no aparece en el dataset (almacenamiento extra) y solo difieren en la intención: "súmennos el paquete… ¿cuánto va a aumentar la cuota?" (pide el cambio → `billing`) contra "¿cuánto cuesta el paquete…?" (solo pregunta → `other`).
- **Resultado esperado:** el mismo criterio que `v2` contra `v1` (D-30): NX-008 bien en las dos corridas de Gemini, holdout y global no menores que los de `v1`, ninguna categoría bajo 70 % y no más plazos vagos que `v1`. Además, NX-036 bien con `gpt-6-luna`.
- **Resultado:** pendiente de medir.

## triage_v2 — 2026-11-25

- **Cambio:** `v1` + un par de ejemplos de contraste entre `billing` y `other` (few-shot, M1L2). Es el único cambio.
- **Por qué:** el único error de `v1` en el paso 3 fue NX-008 ("pasar del plan Básico al Pro… ¿cuánto me cobran la diferencia?"), y se repitió con Gemini y con `gpt-6-luna`: el prompt no marca el límite entre pedir un cambio en lo que ya se paga (`billing`) y preguntar un precio (`other`). Los ejemplos muestran ese límite con un tema distinto (un módulo), para no copiar casos del dataset.
- **Resultado esperado:** NX-008 correcto en las dos corridas de Gemini, sin bajar el holdout (100 % con `v1`) ni el global (98 %), sin categorías bajo 70 % y sin más plazos vagos que `v1`. Más tokens de entrada por consulta.
- **Resultado (2 corridas con Gemini + 1 con `gpt-6-luna`, 25/11/2026):** NX-008 bien en las 3 corridas y global de Gemini 98,75 % (`v1`: 97,5 %), pero **no cumple el criterio** (D-30): holdout 97,5 % contra 100 % (NX-040 salió `technical` en una corrida: inestable) y 8 plazos vagos contra 3. Con `gpt-6-luna` arregló NX-008 pero **rompió NX-036** (`other` → `billing`): el ejemplo de `billing` ("sumar el módulo… ¿cuánto aumenta la cuota?") se parecía demasiado a esa pregunta de precio. No queda vigente; sigue `v1`.

## triage_v1 — 2026-11-25

- **Cambio:** primera versión. Zero-shot con los 4 principios de la M1L2 (rol, contexto, tarea, formato) y el contrato `{answer, confidence, category, actions}` por tool calling (M1L3).
- **Por qué:** es la línea base contra la que se comparan las versiones siguientes. Incluye desde el inicio la regla contra los plazos vagos ("a la brevedad"), aprendida en el desarrollo exploratorio ([nubbix-triage](https://github.com/francodauro/nubbix-triage), v8: aparecían en 16 de 20 respuestas).
- **Resultado (paso 3, 40 casos, 25/11/2026):** Gemini 98 % (39/40) con **1 plazo vago** ("a la brevedad" en NX-011) → regresión por la regla de umbral 0; `gpt-6-luna` 98 % (39/40), 0 plazos vagos, USD 0.000146 por acierto. Único error en los dos: NX-008 (cambio de plan con cobro de la diferencia, `billing`) clasificado como `other`. Detalle en `evals/reporte.md`.
