# Comparativa de modelos · Triage Nubbix

Generado el 26/11/2026 11:57 con `python -m evals.comparativa` (no llama a ninguna API). Extra credit del PI. Compara Gemini `gemini-3.5-flash-lite` (primario actual, plan gratuito) con OpenAI `gpt-6-luna` usando `triage_v4` con guardrails, la versión en producción. Criterio D-45, fijado y commiteado antes de correr: `gpt-6-luna` pasa a ser el primario si cumple **todas** las condiciones de "no empeora" y **al menos una** de "gana"; si no, Gemini sigue como primario.

Corridas usadas: las primeras 4 completas de cada modelo (dataset de 40 casos) y las primeras 2 completas de la suite adversarial sin guardrails, en orden cronológico.

- **Gemini**: dataset `20261125-160518_triage_v4_gemini`, `20261125-161055_triage_v4_gemini`, `20261126-104847_triage_v4_gemini`, `20261126-105616_triage_v4_gemini`; adversarial `20261126-094731_adversarial_triage_v4_gemini_sin-guardrails`, `20261126-095050_adversarial_triage_v4_gemini_sin-guardrails`.
- **gpt-6-luna**: dataset `20261125-161731_triage_v4_openai`, `20261126-112909_triage_v4_openai`, `20261126-113348_triage_v4_openai`, `20261126-115407_triage_v4_openai`; adversarial `20261126-115606_adversarial_triage_v4_openai_sin-guardrails`, `20261126-115625_adversarial_triage_v4_openai_sin-guardrails`.

## Resultado del criterio

| # | Condición | gpt-6-luna | Gemini | ¿Cumple? |
|---|---|---|---|---|
| | **No empeora (todas)** | | | |
| 1 | Holdout promedio ≥ el de Gemini | 100 % | 100 % | ✅ |
| 2 | Ninguna categoría bajo 70% en ninguna corrida | peor 90 % | peor 90 % | ✅ |
| 3 | 0 consultas legítimas bloqueadas o en revisión | 0 | 0 | ✅ |
| 4 | Adversarial sin guardrails 10/10 en sus 2 corridas | 9/10 y 9/10 | 10/10 y 10/10 | ❌ |
| 5 | Costo proyectado ≤ USD 2.00 por mes (12.000 consultas) | USD 1.90 | USD 0.00 | ✅ |
| | **Gana (al menos una)** | | | |
| A | Global promedio mayor que el de Gemini | 98,12 % | 98,12 % | ❌ |
| B | Menos casos inestables que Gemini | 1 (NX-008) | 1 (NX-008) | ❌ |
| C | Gemini no alcanza: pedidos por consulta de su peor corrida × 400 > 500 | — | 1,275 × 400 = 510 por día | ✅ |

Decisión que sale del criterio: **Gemini sigue como primario** y `gpt-6-luna` como respaldo.

## Lo que informa sin decidir

| Métrica | Gemini | gpt-6-luna |
|---|---:|---:|
| Global promedio | 98,12 % | 98,12 % |
| Casos con error | NX-008 | NX-008 |
| Plazos vagos escritos por el modelo (total, antes de la compuerta) | 11 | 0 |
| Plazos vagos entregados al cliente (total) | 0 | 0 |
| Casos reintentados al final por un error del proveedor (total) | 0 | 0 |
| Pedidos por consulta (promedio / peor corrida) | 1,175 / 1,275 | 1,000 / 1,000 |
| Latencia por caso, con reintentos (s) | 3,04 | 1,55 |
| Latencia de la API, sin esperas (s) | 2,21 | 1,54 |
| Costo real por consulta (USD) | 0.000000 | 0.000159 |
| Costo por acierto (USD) | 0.000000 | 0.000162 |

Cada proveedor cuenta los tokens distinto, así que el costo proyectado es aproximado. Gemini cuesta 0 porque se usa en el plan gratuito; su plan pago tiene otro precio (`config/pricing.json`).

### Todas las versiones (solo informa)

Promedio de las corridas completas de cada versión y proveedor. Solo decide `triage_v4` con guardrails.

| Prompt | Proveedor | Guardrails | Corridas | Global | Holdout | Peor categoría | Inestables | Costo por acierto |
|---|---|---|---:|---:|---:|---:|---|---:|
| triage_v1 | gemini | no | 2 | 97,5 % | 100 % | 90 % | ninguno | USD 0.000000 |
| triage_v2 | gemini | no | 2 | 98,75 % | 97,5 % | 90 % | NX-040 | USD 0.000000 |
| triage_v3 | gemini | no | 2 | 98,75 % | 100 % | 90 % | NX-008 | USD 0.000000 |
| triage_v4 | gemini | sí | 4 | 98,12 % | 100 % | 90 % | NX-008 | USD 0.000000 |
| triage_v1 | openai | no | 1 | 97,5 % | 100 % | 90 % | ninguno | USD 0.000146 |
| triage_v2 | openai | no | 1 | 97,5 % | 100 % | 90 % | ninguno | USD 0.000155 |
| triage_v3 | openai | no | 1 | 100 % | 100 % | 100 % | ninguno | USD 0.000152 |
| triage_v4 | openai | sí | 4 | 98,12 % | 100 % | 90 % | NX-008 | USD 0.000162 |

## Limitaciones

- El PI dice cuántos tickets llegan por día (400), pero no cómo se reparten en el día: el límite de 15 pedidos por minuto del plan gratuito de Gemini no se puede evaluar.
- El plan gratuito de Gemini puede usar el contenido enviado para mejorar los productos de Google: no admite consultas reales de clientes.
- Las evals gastan del mismo cupo diario de Gemini que el servicio.

## Conclusión

Se escribe a mano en el README, sección "Extra credit: comparativa de modelos".
