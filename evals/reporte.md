# Reporte de evaluación · Triage Nubbix

Generado el 25/11/2026 14:55 con `python -m evals.runner`. Umbral por categoría: 70%. Plazos vagos permitidos: 0.

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

## 2. ¿Alguna categoría quedó bajo el umbral?

| Corrida | Global | billing | technical | account | other | dev | holdout | Plazos vagos | Estado |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `20261125-130759_triage_v1_gemini` | 98% (39/40) | 90% (9/10) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 95% (19/20) | 100% (20/20) | 1 | Regresión: plazos vagos en 1 respuesta (máximo 0) |
| `20261125-131901_triage_v1_openai` | 98% (39/40) | 90% (9/10) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 95% (19/20) | 100% (20/20) | 0 | OK |
| `20261125-142941_triage_v1_gemini` | 98% (39/40) | 90% (9/10) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 95% (19/20) | 100% (20/20) | 2 | Regresión: plazos vagos en 2 respuestas (máximo 0) |
| `20261125-143954_triage_v2_gemini` | 98% (39/40) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 90% (9/10) | 100% (20/20) | 95% (19/20) | 4 | Regresión: plazos vagos en 4 respuestas (máximo 0) |
| `20261125-144637_triage_v2_gemini` | 100% (40/40) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 100% (20/20) | 100% (20/20) | 4 | Regresión: plazos vagos en 4 respuestas (máximo 0) |
| `20261125-145358_triage_v2_openai` | 98% (39/40) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 90% (9/10) | 95% (19/20) | 100% (20/20) | 0 | OK |

## 3. ¿El score y el costo por acierto cuentan la misma historia?

| Corrida | Aciertos | Tokens entrada / salida | Costo total | Costo en `metrics.jsonl` | Costo por acierto | Costo por acierto proyectado con gpt-6-luna | Latencia promedio por caso (con reintentos) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `20261125-130759_triage_v1_gemini` | 39/40 | 40879 / 3057 | USD 0.000000 | USD 0.000000 ✓ | USD 0.000000 | USD 0.000144 | 4.82 s |
| `20261125-131901_triage_v1_openai` | 39/40 | 40159 / 3387 | USD 0.005709 | USD 0.005709 ✓ | USD 0.000146 | USD 0.000146 | 1.48 s |
| `20261125-142941_triage_v1_gemini` | 39/40 | 40879 / 3101 | USD 0.000000 | USD 0.000000 ✓ | USD 0.000000 | USD 0.000145 | 5.52 s |
| `20261125-143954_triage_v2_gemini` | 39/40 | 44679 / 3011 | USD 0.000000 | USD 0.000000 ✓ | USD 0.000000 | USD 0.000153 | 2.22 s |
| `20261125-144637_triage_v2_gemini` | 40/40 | 44679 / 3018 | USD 0.000000 | USD 0.000000 ✓ | USD 0.000000 | USD 0.000149 | 4.44 s |
| `20261125-145358_triage_v2_openai` | 39/40 | 43839 / 3357 | USD 0.006062 | USD 0.006062 ✓ | USD 0.000155 | USD 0.000155 | 1.52 s |

Mejor score (100%): 20261125-144637_triage_v2_gemini. Mejor costo por acierto (USD 0.000000): 20261125-130759_triage_v1_gemini, 20261125-142941_triage_v1_gemini, 20261125-143954_triage_v2_gemini, 20261125-144637_triage_v2_gemini. **Cuentan la misma historia**: al menos una corrida es la mejor en las dos. Ojo: 20261125-130759_triage_v1_gemini, 20261125-142941_triage_v1_gemini, 20261125-143954_triage_v2_gemini, 20261125-144637_triage_v2_gemini tiene regresiones (sección 2), aunque gane en score o en costo.

## 4. Comparación por versión y proveedor

Promedio de las corridas completas de cada versión con cada proveedor. Un caso es **inestable** si su categoría cambia entre corridas de la misma versión: ahí una diferencia puede ser azar.

| Prompt | Proveedor | Corridas | Global | dev | holdout | Peor categoría | Plazos vagos (total) | Casos con error | Inestables | Costo por acierto | Proyectado con gpt-6-luna |
|---|---|---:|---:|---:|---:|---:|---:|---|---|---:|---:|
| triage_v1 | gemini | 2 | 98% | 95% | 100% | 90% | 3 | NX-008 | ninguno | USD 0.000000 | USD 0.000144 |
| triage_v2 | gemini | 2 | 99% | 100% | 98% | 90% | 8 | NX-040 | NX-040 | USD 0.000000 | USD 0.000151 |
| triage_v1 | openai | 1 | 98% | 95% | 100% | 90% | 0 | NX-008 | ninguno | USD 0.000146 | USD 0.000146 |
| triage_v2 | openai | 1 | 98% | 95% | 100% | 90% | 0 | NX-036 | ninguno | USD 0.000155 | USD 0.000155 |

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

## Conclusión

Se escribe a mano en el README: qué queda vigente y por qué, citando el score por categoría, los plazos vagos y el costo por acierto.
