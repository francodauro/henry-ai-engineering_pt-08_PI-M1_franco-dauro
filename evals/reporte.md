# Reporte de evaluación · Triage Nubbix

Generado el 25/11/2026 13:28 con `python -m evals.runner`. Umbral por categoría: 70%. Plazos vagos permitidos: 0.

## 1. Qué se evaluó

Dataset `evals/dataset.jsonl`: 40 casos (billing 10, technical 10, account 10, other 10). Métrica: exact match de la categoría.

| Corrida | Proveedor | Modelo | Prompt | Casos | Completa |
|---|---|---|---|---:|---|
| `20261125-130759_triage_v1_gemini` | gemini | gemini-3.5-flash-lite | triage_v1 | 40 | sí |
| `20261125-131901_triage_v1_openai` | openai | gpt-6-luna | triage_v1 | 40 | sí |

## 2. ¿Alguna categoría quedó bajo el umbral?

| Corrida | Global | billing | technical | account | other | Plazos vagos | Estado |
|---|---:|---:|---:|---:|---:|---:|---|
| `20261125-130759_triage_v1_gemini` | 98% (39/40) | 90% (9/10) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 1 | Regresión: plazos vagos en 1 respuesta (máximo 0) |
| `20261125-131901_triage_v1_openai` | 98% (39/40) | 90% (9/10) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 0 | OK |

## 3. ¿El score y el costo por acierto cuentan la misma historia?

| Corrida | Aciertos | Tokens entrada / salida | Costo total | Costo en `metrics.jsonl` | Costo por acierto | Latencia promedio por caso (con reintentos) |
|---|---:|---:|---:|---:|---:|---:|
| `20261125-130759_triage_v1_gemini` | 39/40 | 40879 / 3057 | USD 0.000000 | USD 0.000000 ✓ | USD 0.000000 | 4.82 s |
| `20261125-131901_triage_v1_openai` | 39/40 | 40159 / 3387 | USD 0.005709 | USD 0.005709 ✓ | USD 0.000146 | 1.48 s |

Mejor score (98%): 20261125-130759_triage_v1_gemini, 20261125-131901_triage_v1_openai. Mejor costo por acierto (USD 0.000000): 20261125-130759_triage_v1_gemini. **Cuentan la misma historia**: al menos una corrida es la mejor en las dos. Ojo: 20261125-130759_triage_v1_gemini tiene regresiones (sección 2), aunque gane en score o en costo.

## Detalle de errores

**`20261125-130759_triage_v1_gemini`**

- Categoría: NX-008 esperaba `billing`, obtuvo `other`
- Plazo vago: NX-011 (billing): "a la brevedad"
- Reintentados al final por un error del proveedor: NX-005, NX-012, NX-027, NX-039

**`20261125-131901_triage_v1_openai`**

- Categoría: NX-008 esperaba `billing`, obtuvo `other`
- Plazos vagos: ninguno.

## Conclusión

Se escribe a mano en el README: qué queda vigente y por qué, citando el score por categoría, los plazos vagos y el costo por acierto.
