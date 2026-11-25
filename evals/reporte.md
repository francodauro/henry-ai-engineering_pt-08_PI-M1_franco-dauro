# Reporte de evaluación · Triage Nubbix

Generado el 25/11/2026 17:03 con `python -m evals.runner`. Umbral por categoría: 70%. Plazos vagos permitidos: 0. Consultas legítimas bloqueadas o en revisión permitidas: 0.

Desde el paso 5 las corridas pasan por los guardrails (columna *Guardrails*). En esas, los plazos vagos **entregados** son los que llegaron al cliente; los **corregidos** son los que escribió el modelo y la compuerta de salida sacó. Las corridas anteriores no tienen guardrails: lo que escribió el modelo es lo que se entregaba.

## 1. Qué se evaluó

Dataset `evals/dataset.jsonl`: 40 casos (billing 10, technical 10, account 10, other 10). Métrica: exact match de la categoría.

| Corrida | Proveedor | Modelo | Prompt | Casos | Completa |
|---|---|---|---|---:|---|
| `20261125-130759_triage_v1_gemini` | gemini | gemini-3.5-flash-lite | triage_v1 | 40 | sí |
| `20261125-131901_triage_v1_openai` | openai | gpt-6-luna | triage_v1 | 40 | sí |
| `20261125-142941_triage_v1_gemini` | gemini | gemini-3.5-flash-lite | triage_v1 | 40 | sí |
| `20261125-143954_triage_v2_gemini` | gemini | gemini-3.5-flash-lite | triage_v2 | 40 | sí |
| `20261125-144637_triage_v2_gemini` | gemini | gemini-3.5-flash-lite | triage_v2 | 40 | sí |
| `20261125-145358_triage_v2_openai` | openai | gpt-6-luna | triage_v2 | 40 | sí |
| `20261125-150529_triage_v3_gemini` | gemini | gemini-3.5-flash-lite | triage_v3 | 40 | sí |
| `20261125-151223_triage_v3_gemini` | gemini | gemini-3.5-flash-lite | triage_v3 | 40 | sí |
| `20261125-151947_triage_v3_openai` | openai | gpt-6-luna | triage_v3 | 40 | sí |
| `20261125-160518_triage_v4_gemini` | gemini | gemini-3.5-flash-lite | triage_v4 | 40 | sí |
| `20261125-161055_triage_v4_gemini` | gemini | gemini-3.5-flash-lite | triage_v4 | 40 | sí |
| `20261125-161731_triage_v4_openai` | openai | gpt-6-luna | triage_v4 | 40 | sí |

## 2. ¿Alguna categoría quedó bajo el umbral?

| Corrida | Guardrails | Global | billing | technical | account | other | dev | holdout | Plazos vagos entregados | Plazos corregidos | Bloqueadas o en revisión | Estado |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `20261125-130759_triage_v1_gemini` | no | 98% (39/40) | 90% (9/10) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 95% (19/20) | 100% (20/20) | 1 | — | — | Regresión: plazos vagos en 1 respuesta (máximo 0) |
| `20261125-131901_triage_v1_openai` | no | 98% (39/40) | 90% (9/10) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 95% (19/20) | 100% (20/20) | 0 | — | — | OK |
| `20261125-142941_triage_v1_gemini` | no | 98% (39/40) | 90% (9/10) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 95% (19/20) | 100% (20/20) | 2 | — | — | Regresión: plazos vagos en 2 respuestas (máximo 0) |
| `20261125-143954_triage_v2_gemini` | no | 98% (39/40) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 90% (9/10) | 100% (20/20) | 95% (19/20) | 4 | — | — | Regresión: plazos vagos en 4 respuestas (máximo 0) |
| `20261125-144637_triage_v2_gemini` | no | 100% (40/40) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 100% (20/20) | 100% (20/20) | 4 | — | — | Regresión: plazos vagos en 4 respuestas (máximo 0) |
| `20261125-145358_triage_v2_openai` | no | 98% (39/40) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 90% (9/10) | 95% (19/20) | 100% (20/20) | 0 | — | — | OK |
| `20261125-150529_triage_v3_gemini` | no | 100% (40/40) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 100% (20/20) | 100% (20/20) | 4 | — | — | Regresión: plazos vagos en 4 respuestas (máximo 0) |
| `20261125-151223_triage_v3_gemini` | no | 98% (39/40) | 90% (9/10) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 95% (19/20) | 100% (20/20) | 2 | — | — | Regresión: plazos vagos en 2 respuestas (máximo 0) |
| `20261125-151947_triage_v3_openai` | no | 100% (40/40) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 100% (20/20) | 100% (20/20) | 0 | — | — | OK |
| `20261125-160518_triage_v4_gemini` | sí | 100% (40/40) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 100% (20/20) | 100% (20/20) | 0 | 3 | 0 | OK |
| `20261125-161055_triage_v4_gemini` | sí | 98% (39/40) | 90% (9/10) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 95% (19/20) | 100% (20/20) | 0 | 4 | 0 | OK |
| `20261125-161731_triage_v4_openai` | sí | 100% (40/40) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 100% (20/20) | 100% (20/20) | 0 | 0 | 0 | OK |

## 3. ¿El score y el costo por acierto cuentan la misma historia?

| Corrida | Aciertos | Tokens entrada / salida | Costo total | Costo en `metrics.jsonl` | Costo por acierto | Costo por acierto proyectado con gpt-6-luna | Latencia promedio por caso (con reintentos) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `20261125-130759_triage_v1_gemini` | 39/40 | 40879 / 3057 | USD 0.000000 | USD 0.000000 ✓ | USD 0.000000 | USD 0.000144 | 4.82 s |
| `20261125-131901_triage_v1_openai` | 39/40 | 40159 / 3387 | USD 0.005709 | USD 0.005709 ✓ | USD 0.000146 | USD 0.000146 | 1.48 s |
| `20261125-142941_triage_v1_gemini` | 39/40 | 40879 / 3101 | USD 0.000000 | USD 0.000000 ✓ | USD 0.000000 | USD 0.000145 | 5.52 s |
| `20261125-143954_triage_v2_gemini` | 39/40 | 44679 / 3011 | USD 0.000000 | USD 0.000000 ✓ | USD 0.000000 | USD 0.000153 | 2.22 s |
| `20261125-144637_triage_v2_gemini` | 40/40 | 44679 / 3018 | USD 0.000000 | USD 0.000000 ✓ | USD 0.000000 | USD 0.000149 | 4.44 s |
| `20261125-145358_triage_v2_openai` | 39/40 | 43839 / 3357 | USD 0.006062 | USD 0.006062 ✓ | USD 0.000155 | USD 0.000155 | 1.52 s |
| `20261125-150529_triage_v3_gemini` | 40/40 | 44759 / 3040 | USD 0.000000 | USD 0.000000 ✓ | USD 0.000000 | USD 0.000150 | 2.98 s |
| `20261125-151223_triage_v3_gemini` | 39/40 | 44759 / 2994 | USD 0.000000 | USD 0.000000 ✓ | USD 0.000000 | USD 0.000153 | 2.21 s |
| `20261125-151947_triage_v3_openai` | 40/40 | 43999 / 3367 | USD 0.006083 | USD 0.006083 ✓ | USD 0.000152 | USD 0.000152 | 1.62 s |
| `20261125-160518_triage_v4_gemini` | 40/40 | 47439 / 2922 | USD 0.000000 | USD 0.000000 ✓ | USD 0.000000 | USD 0.000155 | 1.46 s |
| `20261125-161055_triage_v4_gemini` | 39/40 | 47439 / 2869 | USD 0.000000 | USD 0.000000 ✓ | USD 0.000000 | USD 0.000158 | 2.05 s |
| `20261125-161731_triage_v4_openai` | 40/40 | 46559 / 3381 | USD 0.006346 | USD 0.006346 ✓ | USD 0.000159 | USD 0.000159 | 1.69 s |

Mejor score (100%): 20261125-144637_triage_v2_gemini, 20261125-150529_triage_v3_gemini, 20261125-151947_triage_v3_openai, 20261125-160518_triage_v4_gemini, 20261125-161731_triage_v4_openai. Mejor costo por acierto (USD 0.000000): 20261125-130759_triage_v1_gemini, 20261125-142941_triage_v1_gemini, 20261125-143954_triage_v2_gemini, 20261125-144637_triage_v2_gemini, 20261125-150529_triage_v3_gemini, 20261125-151223_triage_v3_gemini, 20261125-160518_triage_v4_gemini, 20261125-161055_triage_v4_gemini. **Cuentan la misma historia**: al menos una corrida es la mejor en las dos. Ojo: 20261125-130759_triage_v1_gemini, 20261125-142941_triage_v1_gemini, 20261125-143954_triage_v2_gemini, 20261125-144637_triage_v2_gemini, 20261125-150529_triage_v3_gemini, 20261125-151223_triage_v3_gemini tiene regresiones (sección 2), aunque gane en score o en costo.

## 4. Comparación por versión y proveedor

Promedio de las corridas completas de cada versión con cada proveedor. Un caso es **inestable** si su categoría cambia entre corridas de la misma versión: ahí una diferencia puede ser azar.

| Prompt | Proveedor | Guardrails | Corridas | Global | dev | holdout | Peor categoría | Plazos vagos entregados (total) | Plazos escritos por el modelo (total) | Bloqueadas o en revisión (total) | Casos con error | Inestables | Costo por acierto | Proyectado con gpt-6-luna |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|
| triage_v1 | gemini | no | 2 | 98% | 95% | 100% | 90% | 3 | 3 | — | NX-008 | ninguno | USD 0.000000 | USD 0.000144 |
| triage_v2 | gemini | no | 2 | 99% | 100% | 98% | 90% | 8 | 8 | — | NX-040 | NX-040 | USD 0.000000 | USD 0.000151 |
| triage_v3 | gemini | no | 2 | 99% | 98% | 100% | 90% | 6 | 6 | — | NX-008 | NX-008 | USD 0.000000 | USD 0.000152 |
| triage_v4 | gemini | sí | 2 | 99% | 98% | 100% | 90% | 0 | 7 | 0 | NX-008 | NX-008 | USD 0.000000 | USD 0.000157 |
| triage_v1 | openai | no | 1 | 98% | 95% | 100% | 90% | 0 | 0 | — | NX-008 | ninguno | USD 0.000146 | USD 0.000146 |
| triage_v2 | openai | no | 1 | 98% | 95% | 100% | 90% | 0 | 0 | — | NX-036 | ninguno | USD 0.000155 | USD 0.000155 |
| triage_v3 | openai | no | 1 | 100% | 100% | 100% | 100% | 0 | 0 | — | ninguno | ninguno | USD 0.000152 | USD 0.000152 |
| triage_v4 | openai | sí | 1 | 100% | 100% | 100% | 100% | 0 | 0 | 0 | ninguno | ninguno | USD 0.000159 | USD 0.000159 |

## Detalle de errores

**`20261125-130759_triage_v1_gemini`**

- Categoría: NX-008 esperaba `billing`, obtuvo `other`
- Plazo vago: NX-011 (billing): "a la brevedad"
- Reintentados al final por un error del proveedor: NX-005, NX-012, NX-027, NX-039

**`20261125-131901_triage_v1_openai`**

- Categoría: NX-008 esperaba `billing`, obtuvo `other`
- Plazos vagos: ninguno.

**`20261125-142941_triage_v1_gemini`**

- Categoría: NX-008 esperaba `billing`, obtuvo `other`
- Plazo vago: NX-002 (technical): "a la brevedad"
- Plazo vago: NX-011 (billing): "a la brevedad"
- Reintentados al final por un error del proveedor: NX-003, NX-007, NX-024, NX-027

**`20261125-143954_triage_v2_gemini`**

- Categoría: NX-040 esperaba `other`, obtuvo `technical`
- Plazo vago: NX-007 (account): "a la brevedad"
- Plazo vago: NX-009 (other): "a la brevedad"
- Plazo vago: NX-011 (billing): "a la brevedad"
- Plazo vago: NX-026 (technical): "a la brevedad"
- Reintentados al final por un error del proveedor: NX-013

**`20261125-144637_triage_v2_gemini`**

- Categoría: ningún error.
- Plazo vago: NX-007 (account): "a la brevedad"
- Plazo vago: NX-011 (billing): "a la brevedad"
- Plazo vago: NX-018 (other): "a la brevedad"
- Plazo vago: NX-029 (account): "de inmediato"

**`20261125-145358_triage_v2_openai`**

- Categoría: NX-036 esperaba `other`, obtuvo `billing`
- Plazos vagos: ninguno.

**`20261125-150529_triage_v3_gemini`**

- Categoría: ningún error.
- Plazo vago: NX-005 (technical): "a la brevedad"
- Plazo vago: NX-011 (billing): "a la brevedad"
- Plazo vago: NX-018 (other): "a la brevedad"
- Plazo vago: NX-039 (other): "a la brevedad"

**`20261125-151223_triage_v3_gemini`**

- Categoría: NX-008 esperaba `billing`, obtuvo `other`
- Plazo vago: NX-011 (billing): "a la brevedad"
- Plazo vago: NX-028 (technical): "a la brevedad"
- Reintentados al final por un error del proveedor: NX-001, NX-005, NX-020

**`20261125-151947_triage_v3_openai`**

- Categoría: ningún error.
- Plazos vagos: ninguno.

**`20261125-160518_triage_v4_gemini`**

- Categoría: ningún error.
- Plazos vagos: ninguno.
- Plazos vagos que sacó la compuerta de salida: NX-026 ("a la brevedad"), NX-028 ("a la mayor brevedad"), NX-029 ("lo antes posible")

**`20261125-161055_triage_v4_gemini`**

- Categoría: NX-008 esperaba `billing`, obtuvo `other`
- Plazos vagos: ninguno.
- Plazos vagos que sacó la compuerta de salida: NX-010 ("a la brevedad"), NX-028 ("a la brevedad"), NX-029 ("de inmediato"), NX-038 ("a la brevedad")

**`20261125-161731_triage_v4_openai`**

- Categoría: ningún error.
- Plazos vagos: ninguno.

## Conclusión

Se escribe a mano en el README: qué queda vigente y por qué, citando el score por categoría, los plazos vagos y el costo por acierto.
