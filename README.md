# Nubbix Triage — Proyecto Integrador M1 (Henry, AI Engineering)

Servicio de triage de consultas de soporte para **Nubbix**, un SaaS de gestión para pymes de LATAM.
Recibe una consulta en texto libre y devuelve un JSON validado con el contrato:

```json
{"answer": "...", "confidence": 0.95, "category": "billing", "actions": ["..."]}
```

donde `category` es `billing`, `technical`, `account` u `other`.

> **Estado: paso 2 — contrato JSON.** La CLI devuelve el contrato validado, con el prompt `triage_v1`. El proyecto se construye paso a paso.

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

`status` es `ok`, `error` (con `error_kind`: `rate_limit`, `server_error`, `timeout`, `auth_error`…) o `skipped` (tope de gasto). Desde el paso 2, cada línea del triage suma `prompt_version`, `request_id` (agrupa los intentos de una consulta), `contract_attempt`, `contract_valid` y `contract_errors` (solo campo y tipo de error, por ejemplo `category:literal_error`, nunca el texto). `cost_usd` se guarda como número (un valor chico puede verse como `1.8e-05`, que es JSON válido); en pantalla se muestra con 6 decimales.

## Estructura

```
src/       código del servicio (src/llm/: proveedores y router)
config/    precios por modelo (pricing.json)
prompts/   prompts del triage versionados en YAML + CHANGELOG.md
evals/     dataset de evaluación y runner
data/      métricas de cada ejecución (data/metrics.jsonl)
tests/     tests con unittest, sin llamadas a APIs
docs/      documentación: decisiones (DECISIONES.md) y prompts usados con IA
```

## Uso de IA

El proyecto se construye con asistencia de Claude (Anthropic). Los prompts usados en cada paso
están en [docs/prompts_ia.md](docs/prompts_ia.md).
