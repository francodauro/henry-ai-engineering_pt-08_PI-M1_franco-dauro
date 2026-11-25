# Nubbix Triage — Proyecto Integrador M1 (Henry, AI Engineering)

Servicio de triage de consultas de soporte para **Nubbix**, un SaaS de gestión para pymes de LATAM.
Recibe una consulta en texto libre y devuelve un JSON validado con el contrato:

```json
{"answer": "...", "confidence": 0.95, "category": "billing", "actions": ["..."]}
```

donde `category` es `billing`, `technical`, `account` u `other`.

> **Estado: paso 4 — comparación de prompts.** La CLI devuelve el contrato validado; la suite de evals mide la calidad sobre 40 casos y compara `triage_v1` (zero-shot) contra `triage_v2` (few-shot). El proyecto se construye paso a paso.

## Cómo funciona

```
consulta ──► ¿vacía? ──sí──► error 2 (no se llama al modelo)
                │ no
                ▼
        ┌─► Gemini (gratis) ──ok──────────────────────────┐
        │      │ falla (después de reintentar)             ▼
        │      ▼                                   tool call: el modelo "llena el formulario"
        │  ¿queda presupuesto? ──no──► error 3             │
        │      │ sí                                        ▼
        │      ▼                                   ¿cumple el contrato Pydantic?
        │  OpenAI gpt-6-luna (pago) ──ok──────────►  │ sí               │ no
        │                                            ▼                  ▼
        │                                     JSON validado   ¿quedan intentos? ──no──► error 4
        │                                                               │ sí
        └──────────── se reintenta con el error en el system ◄──────────┘
```

- **Primario (gratuito):** Google Gemini `gemini-3.5-flash-lite`, plan gratuito de la API.
- **Respaldo (pago):** OpenAI `gpt-6-luna`, con `reasoning_effort="none"`.
- **Abstracción común:** los dos heredan de `LLMProvider` ([src/llm/base.py](src/llm/base.py)) y devuelven la misma respuesta normalizada (texto, tokens, latencia y costo). Sumar un proveedor es sumar una subclase.
- **Reintentos:** solo ante errores transitorios (429, 5xx, timeout, red), con espera exponencial y jitter. Si el servidor manda `Retry-After`, se respeta; si pide esperar más de 10 s, se pasa directo al respaldo. Una clave inválida o un modelo inexistente no se reintentan.
- **Costo:** tokens que informa la API × precios de [config/pricing.json](config/pricing.json), tomados de la documentación oficial de cada proveedor (con fuente y fecha). Gemini cuesta 0 en el plan gratuito.
- **Tope de gasto:** antes de llamar a OpenAI se suma lo gastado en `data/metrics.jsonl`; si llegó a `BUDGET_USD` (USD 4.50), no se lo llama.
- **Contrato** ([src/contract.py](src/contract.py)): Pydantic valida tipo y dominio de cada campo. Categorías y acciones están definidas en un solo lugar, y de ahí salen el contrato, el schema de la tool call y las listas del prompt.
- **Tool calling forzado** en los dos proveedores: el modelo está obligado a llamar a la función `registrar_triage`, cuyo schema sale del contrato (`model_json_schema()`). Gemini entrega los argumentos como dict y OpenAI como texto JSON; cada proveedor los convierte a dict.
- **Reintento informado:** si la respuesta no cumple el contrato, se vuelve a pedir (hasta 3 intentos) agregando al system qué campo falló y por qué. Son dos capas distintas: los reintentos de red (paso 1) y los de contrato.
- **Prompt** versionado en YAML, fuera del código: [prompts/triage_v1.yaml](prompts/triage_v1.yaml) (historia en [prompts/CHANGELOG.md](prompts/CHANGELOG.md)).

## El contrato

| Campo | Tipo y dominio |
|---|---|
| `answer` | Texto de 1 a 500 caracteres: la primera respuesta para el cliente |
| `confidence` | Número entre 0 y 1 (un `"0.9"` escrito como texto se rechaza): cuán seguro está el modelo de la categoría |
| `category` | Solo `billing`, `technical`, `account` u `other` |
| `actions` | Lista no vacía y sin repetidos de: `review_charge`, `resend_invoice`, `investigate_incident`, `manage_access`, `contact_sales`, `request_more_info`, `escalate_to_human`, `no_action` (esta última siempre sola) |

Los campos de más se rechazan. Ejemplo: `{"category": "factura", "confidence": 47, ...}` falla con un mensaje por campo (`category: Input should be 'billing', 'technical', 'account' or 'other'`; `confidence: Input should be less than or equal to 1`).

## Instalación (Windows 11, PowerShell)

Requisitos: Python 3.12 y Git.

```powershell
# 1. Clonar el repositorio y entrar a la carpeta
git clone https://github.com/francodauro/henry-ai-engineering_pt-08_PI-M1_franco-dauro.git
cd henry-ai-engineering_pt-08_PI-M1_franco-dauro

# 2. Crear y activar el entorno virtual (el prompt pasa a mostrar "(.venv)")
python -m venv .venv
.\.venv\Scripts\Activate.ps1
#    Si PowerShell no deja ejecutar scripts, correr una sola vez:
#    Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

# 3. Instalar las dependencias
pip install -r requirements.txt

# 4. Crear el archivo de credenciales y completar las claves
Copy-Item .env.example .env
notepad .env
```

## Uso

Siempre desde la carpeta del proyecto y con el entorno virtual activo:

```powershell
# Triage de una consulta: devuelve el contrato (Gemini; si falla, OpenAI)
python -m src.main "no me llega la factura de agosto"

# Lo mismo, mostrando prompt, intentos, proveedor, tokens, latencia y costo (en la salida de errores)
python -m src.main --detalle "no me llega la factura de agosto"

# Elegir la versión del prompt (por defecto, PROMPT_VERSION del .env)
python -m src.main --prompt v1 "no me llega la factura de agosto"

# Forzar un proveedor, sin respaldo (por ejemplo, para probar OpenAI)
python -m src.main --proveedor openai --detalle "no me llega la factura de agosto"

# Correr los tests (no llaman a ninguna API)
python -m unittest discover -s tests
```

La salida estándar trae **solo el JSON validado**, para que otro sistema lo consuma sin transformaciones; los avisos y el detalle van a la salida de errores. Códigos de salida: `0` ok · `2` consulta vacía · `3` fallaron todos los proveedores · `4` ningún intento cumplió el contrato · `5` error de configuración (en PowerShell: `echo $LASTEXITCODE`).

### Métricas (`data/metrics.jsonl`)

Una línea JSON por llamada a cada proveedor, solo se agrega (append-only). No guarda el texto de la consulta ni de la respuesta. Ejemplo real (25/11/2026): Gemini respondió "high demand" (error 5xx del servidor) en los 3 intentos y respondió el respaldo:

```json
{"timestamp": "2026-11-25T13:12:53+00:00", "provider": "gemini", "model": "gemini-3.5-flash-lite", "temperature": 0.0, "fallback": false, "status": "error", "error_kind": "server_error", "attempts": 3, "cost_usd": 0.0}
{"timestamp": "2026-11-25T13:12:57+00:00", "provider": "openai", "model": "gpt-6-luna", "temperature": 0.0, "fallback": true, "status": "ok", "attempts": 1, "prompt_tokens": 13, "completion_tokens": 42, "total_tokens": 55, "latency_s": 3.034, "cost_usd": 2.23e-05}
```

El costo se puede rehacer a mano con `config/pricing.json`: 13 × 0.10 / 1.000.000 + 42 × 0.50 / 1.000.000 = USD 0.0000223.

`status` es `ok`, `error` (con `error_kind`: `rate_limit`, `server_error`, `timeout`, `auth_error`…) o `skipped` (tope de gasto). Desde el paso 2, cada línea del triage suma `prompt_version`, `request_id` (agrupa los intentos de una consulta), `contract_attempt`, `contract_valid` y `contract_errors` (solo campo y tipo de error, por ejemplo `category:literal_error`, nunca el texto). Desde el paso 3, las llamadas hechas por la suite de evals llevan además `corrida`, el nombre de la corrida a la que pertenecen. `cost_usd` se guarda como número (un valor chico puede verse como `1.8e-05`, que es JSON válido); en pantalla se muestra con 6 decimales.

## Evals

El dataset [evals/dataset.jsonl](evals/dataset.jsonl) tiene **40 casos etiquetados**: 10 por categoría, 28 no fáciles (ambiguos o difíciles) y 20 `dev` / 20 `holdout`. Cada caso trae la categoría esperada y una `nota` con el porqué. Se commiteó antes de la primera corrida, para que la referencia no se ajuste después de ver los resultados.

```powershell
# Correr los 40 casos con Gemini (gratis; tarda unos 5 minutos por la pausa entre casos)
python -m evals.runner --proveedor gemini --prompt v1

# Los mismos casos con OpenAI gpt-6-luna (pago: alrededor de USD 0.01)
python -m evals.runner --proveedor openai --prompt v1

# Solo el reporte, juntando corridas guardadas (no llama a ninguna API)
python -m evals.runner --desde "evals/results/*.jsonl"
```

Cómo mide:
- **Un proveedor por corrida, sin respaldo**: el score es de un solo modelo.
- **Exact match** de la categoría, global y por categoría, con un **umbral de 70 % por categoría** fijado antes de correr. Una categoría por debajo es una regresión.
- **Plazos vagos**: si una sola respuesta para el cliente dice "a la brevedad", "en breve", "lo antes posible" u otra expresión de [src/vague_timing.py](src/vague_timing.py), también es una regresión, aunque la categoría sea correcta.
- **Score por lote**: `dev` sirve para diseñar un prompt y `holdout` para decidir, así una versión no se elige con los mismos casos con los que se ajustó.
- **Casos inestables**: con varias corridas de la misma versión, el reporte marca los casos cuya categoría cambia entre corridas (ahí una diferencia puede ser azar).
- **Costo por acierto** = costo total ÷ aciertos. El reporte comprueba que el costo de la corrida coincide con la suma de `cost_usd` de sus líneas en `data/metrics.jsonl`. Como Gemini cuesta 0, también se muestra el costo **proyectado** con los precios de `gpt-6-luna` (aproximado: cada proveedor cuenta los tokens distinto).
- Si el proveedor no responde un caso (por ejemplo, "high demand"), se lo reintenta una vez al final. Si sigue sin respuesta, la corrida queda **incompleta** y no se usa para comparar.

Cada corrida se guarda en su propio archivo en `evals/results/` (nunca se pisa) y el reporte va a [evals/reporte.md](evals/reporte.md). Códigos de salida: `0` completa sin regresiones · `1` completa con regresiones · `2` incompleta · `5` error de configuración o de datos.

> **Salvedad:** las corridas guardan el texto de cada consulta y la respuesta del modelo, para poder revisar los errores. Se hace porque es un trabajo educativo con un dataset ficticio. En un servicio en producción, con consultas reales de clientes, no se guardaría el texto. `data/metrics.jsonl` no lo guarda nunca.

### Resultados

Prompt `triage_v1`, 40 casos, 25/11/2026. Reporte completo en [evals/reporte.md](evals/reporte.md) y corridas en [evals/results/](evals/results/).

| Modelo | Global | billing | technical | account | other | Plazos vagos | Costo total | Costo por acierto | Latencia por caso | Estado |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Gemini `gemini-3.5-flash-lite` | 98 % (39/40) | 90 % | 100 % | 100 % | 100 % | **1** | USD 0 | USD 0 | 4,82 s | **Regresión** (plazo vago) |
| OpenAI `gpt-6-luna` | 98 % (39/40) | 90 % | 100 % | 100 % | 100 % | 0 | USD 0.005709 | USD 0.000146 | 1,48 s | OK |

Qué muestran los datos:
- **El mismo único error en los dos modelos: NX-008** ("quiero pasar del plan Básico al Pro, ¿cuánto me van a cobrar la diferencia?"). La referencia es `billing` (un cambio del plan ya contratado y su cobro), y los dos respondieron `other` con `contact_sales`. Es un caso difícil a propósito: su par de contraste, NX-036 (solo pregunta un precio, `other`), salió bien en los dos.
- **Gemini escribió "a la brevedad" en NX-011** aunque `triage_v1` lo prohíbe: el prompt reduce el problema, no lo garantiza. Con la regla de umbral 0 eso es una regresión. `gpt-6-luna` no escribió ningún plazo vago.
- **El contrato se cumplió al primer intento en los 80 casos**: no hizo falta ningún reintento de contrato.
- **Gemini no respondió 4 casos** ("high demand", error 5xx) después de los reintentos de red; los 4 respondieron en el reintento del final y la corrida quedó completa. Además, 14 casos necesitaron reintentos de red. Por eso la latencia por caso es de 4,82 s, aunque la API sola tardó 1,65 s en promedio.
- **El costo es auditable**: 40.159 tokens de entrada × USD 0.10 / 1M + 3.387 de salida × USD 0.50 / 1M = USD 0.005709, igual a la suma de `cost_usd` de esa corrida en `data/metrics.jsonl`. Proyectado a 12.000 consultas por mes (400 por día, según la consigna), `gpt-6-luna` costaría unos USD 1.71 por mes.
- **Score y costo por acierto**: empatan en score; Gemini gana en costo (USD 0) pero es el que tiene la regresión.

**Conclusión:** Con `triage_v1`, Gemini y `gpt-6-luna` clasifican igual: 98 % global, todas las categorías por encima del 70 % y el mismo único error (NX-008, un cambio de plan con cobro de la diferencia, que los dos mandan a `other`). Como el error se repite con los dos modelos, es un problema del prompt, no del modelo. La diferencia está en la respuesta al cliente: Gemini escribió "a la brevedad" una vez, y con mi regla (cero plazos vagos) eso es una regresión. `gpt-6-luna` pasó todas las reglas, pero cuesta USD 0.000146 por acierto (unos USD 1,71 por mes a 12.000 consultas), contra USD 0 de Gemini.

**Decisión:** Gemini sigue como proveedor primario y `gpt-6-luna` como respaldo. Un plazo vago en 40 respuestas, con una sola corrida por modelo, no alcanza para pagar por un modelo que clasifica igual. Además, el problema está en el prompt y se ataca en el prompt y en el código. `triage_v1` queda como línea base **con una regresión pendiente**. En el paso 4, `triage_v2` tiene que resolver NX-008 sin perder el resto. En el paso 5, el guardrail de salida tiene que garantizar en código que ninguna respuesta lleve un plazo vago, porque el prompt solo no lo garantiza.

## Técnica elegida y por qué

| Versión | Técnica | Qué cambia |
|---|---|---|
| [`triage_v1`](prompts/triage_v1.yaml) | Zero-shot con los 4 principios de la M1L2 (rol, contexto, tarea, formato) + contrato por tool calling | Línea base |
| [`triage_v2`](prompts/triage_v2.yaml) | Few-shot: `v1` + un par de ejemplos de contraste | Dos ejemplos del mismo tema con distinta intención: pedir un cambio en lo que ya se contrata es `billing`; preguntar solo un precio es `other` |

Por qué few-shot: el único error de `v1` (NX-008) se repitió con los dos modelos, así que es del prompt. La M1L2 recomienda, para un caso mal clasificado, mostrar un ejemplo corregido de esa misma ambigüedad. Chain-of-thought quedó afuera porque el razonamiento necesita un campo donde escribirse y el contrato no se cambia. Los ejemplos no son casos del dataset: si lo fueran, el examen traería la respuesta.

Criterio fijado antes de correr (sobre dos corridas con Gemini por versión): `v2` queda vigente si su holdout y su global no son menores que los de `v1`, ninguna categoría queda bajo 70 %, no tiene más plazos vagos que `v1` y acierta NX-008 en sus dos corridas. Si no, sigue `v1`, que es más simple y barata.

Resultados: pendientes de las corridas del paso 4.

## Estructura

```
src/       código del servicio (src/llm/: proveedores y router)
config/    precios por modelo (pricing.json)
prompts/   prompts del triage versionados en YAML + CHANGELOG.md
evals/     dataset de evaluación, runner, métricas, reporte y corridas (results/)
data/      métricas de cada ejecución (data/metrics.jsonl)
tests/     tests con unittest, sin llamadas a APIs
docs/      documentación: decisiones (DECISIONES.md) y prompts usados con IA
```

## Uso de IA

El proyecto se construye con asistencia de Claude (Anthropic). Los prompts usados en cada paso
están en [docs/prompts_ia.md](docs/prompts_ia.md).
