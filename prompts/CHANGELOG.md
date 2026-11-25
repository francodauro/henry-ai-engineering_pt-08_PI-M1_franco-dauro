# Changelog de prompts

Cada versión es un archivo nuevo en `prompts/` y nunca se edita. Para cada una: qué cambió, por qué y con qué resultado.

## triage_v2 — 2026-11-25

- **Cambio:** `v1` + un par de ejemplos de contraste entre `billing` y `other` (few-shot, M1L2). Es el único cambio.
- **Por qué:** el único error de `v1` en el paso 3 fue NX-008 ("pasar del plan Básico al Pro… ¿cuánto me cobran la diferencia?"), y se repitió con Gemini y con `gpt-6-luna`: el prompt no marca el límite entre pedir un cambio en lo que ya se paga (`billing`) y preguntar un precio (`other`). Los ejemplos muestran ese límite con un tema distinto (un módulo), para no copiar casos del dataset.
- **Resultado esperado:** NX-008 correcto en las dos corridas de Gemini, sin bajar el holdout (100 % con `v1`) ni el global (98 %), sin categorías bajo 70 % y sin más plazos vagos que `v1`. Más tokens de entrada por consulta.
- **Resultado:** pendiente de medir.

## triage_v1 — 2026-11-25

- **Cambio:** primera versión. Zero-shot con los 4 principios de la M1L2 (rol, contexto, tarea, formato) y el contrato `{answer, confidence, category, actions}` por tool calling (M1L3).
- **Por qué:** es la línea base contra la que se comparan las versiones siguientes. Incluye desde el inicio la regla contra los plazos vagos ("a la brevedad"), aprendida en el desarrollo exploratorio ([nubbix-triage](https://github.com/francodauro/nubbix-triage), v8: aparecían en 16 de 20 respuestas).
- **Resultado (paso 3, 40 casos, 25/11/2026):** Gemini 98 % (39/40) con **1 plazo vago** ("a la brevedad" en NX-011) → regresión por la regla de umbral 0; `gpt-6-luna` 98 % (39/40), 0 plazos vagos, USD 0.000146 por acierto. Único error en los dos: NX-008 (cambio de plan con cobro de la diferencia, `billing`) clasificado como `other`. Detalle en `evals/reporte.md`.
