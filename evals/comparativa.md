# Comparativa de modelos · Triage Nubbix

Generado el 26/11/2026 10:44 con `python -m evals.comparativa` (no llama a ninguna API). Extra credit del PI. Compara Gemini `gemini-3.5-flash-lite` (primario actual, plan gratuito) con OpenAI `gpt-6-luna` usando `triage_v4` con guardrails, la versión en producción. Criterio D-45, fijado y commiteado antes de correr: `gpt-6-luna` pasa a ser el primario si cumple **todas** las condiciones de "no empeora" y **al menos una** de "gana"; si no, Gemini sigue como primario.

Corridas usadas: las primeras 4 completas de cada modelo (dataset de 40 casos) y las primeras 2 completas de la suite adversarial sin guardrails, en orden cronológico.

- **Gemini**: dataset `20261125-160518_triage_v4_gemini`, `20261125-161055_triage_v4_gemini`; adversarial `20261126-094731_adversarial_triage_v4_gemini_sin-guardrails`, `20261126-095050_adversarial_triage_v4_gemini_sin-guardrails`.
- **gpt-6-luna**: dataset `20261125-161731_triage_v4_openai`; adversarial ninguna.

## Resultado del criterio

**Faltan corridas o datos: el criterio todavía no se puede aplicar.**

- Gemini: 2 de 4 corridas completas de triage_v4 con guardrails
- gpt-6-luna: 1 de 4 corridas completas de triage_v4 con guardrails
- gpt-6-luna: 0 de 2 corridas adversariales completas sin guardrails

## Lo que informa sin decidir

| Métrica | Gemini | gpt-6-luna |
|---|---:|---:|
| Global promedio | 98,75 % | 100 % |
| Casos con error | NX-008 | ninguno |
| Plazos vagos escritos por el modelo (total, antes de la compuerta) | 7 | 0 |
| Plazos vagos entregados al cliente (total) | 0 | 0 |
| Casos reintentados al final por un error del proveedor (total) | 0 | 0 |
| Pedidos por consulta (promedio / peor corrida) | 1,188 / 1,275 | 1,000 / 1,000 |
| Latencia por caso, con reintentos (s) | 1,75 | 1,69 |
| Latencia de la API, sin esperas (s) | 1,22 | 1,68 |
| Costo real por consulta (USD) | 0.000000 | 0.000159 |
| Costo por acierto (USD) | 0.000000 | 0.000159 |

Cada proveedor cuenta los tokens distinto, así que el costo proyectado es aproximado. Gemini cuesta 0 porque se usa en el plan gratuito; su plan pago tiene otro precio (`config/pricing.json`).

### Todas las versiones (solo informa)

Promedio de las corridas completas de cada versión y proveedor. Solo decide `triage_v4` con guardrails.

| Prompt | Proveedor | Guardrails | Corridas | Global | Holdout | Peor categoría | Inestables | Costo por acierto |
|---|---|---|---:|---:|---:|---:|---|---:|
| triage_v1 | gemini | no | 2 | 97,5 % | 100 % | 90 % | ninguno | USD 0.000000 |
| triage_v2 | gemini | no | 2 | 98,75 % | 97,5 % | 90 % | NX-040 | USD 0.000000 |
| triage_v3 | gemini | no | 2 | 98,75 % | 100 % | 90 % | NX-008 | USD 0.000000 |
| triage_v4 | gemini | sí | 2 | 98,75 % | 100 % | 90 % | NX-008 | USD 0.000000 |
| triage_v1 | openai | no | 1 | 97,5 % | 100 % | 90 % | ninguno | USD 0.000146 |
| triage_v2 | openai | no | 1 | 97,5 % | 100 % | 90 % | ninguno | USD 0.000155 |
| triage_v3 | openai | no | 1 | 100 % | 100 % | 100 % | ninguno | USD 0.000152 |
| triage_v4 | openai | sí | 1 | 100 % | 100 % | 100 % | ninguno | USD 0.000159 |

## Limitaciones

- El PI dice cuántos tickets llegan por día (400), pero no cómo se reparten en el día: el límite de 15 pedidos por minuto del plan gratuito de Gemini no se puede evaluar.
- El plan gratuito de Gemini puede usar el contenido enviado para mejorar los productos de Google: no admite consultas reales de clientes.
- Las evals gastan del mismo cupo diario de Gemini que el servicio.

## Conclusión

Se escribe a mano en el README, sección "Extra credit: comparativa de modelos".
