# Nubbix Triage — Proyecto Integrador M1 (Henry, AI Engineering)

Servicio de triage de consultas de soporte para **Nubbix**, un SaaS de gestión para pymes de LATAM.
Recibe una consulta en texto libre y devuelve un JSON validado con el contrato:

```json
{"answer": "...", "confidence": 0.95, "category": "billing", "actions": ["..."]}
```

donde `category` es `billing`, `technical`, `account` u `other`.

> **Estado: paso 1 — cliente multi-proveedor y métricas.** La CLI ya consulta al modelo (todavía sin contrato JSON). El proyecto se construye paso a paso.

## Cómo funciona (paso 1)

```
consulta ──► Gemini (gratis) ──ok──────────────────────────────► respuesta + línea en data/metrics.jsonl
                 │ falla (después de reintentar los errores transitorios)
                 ▼
           ¿queda presupuesto? ──no──► error 3
                 │ sí
                 ▼
           OpenAI gpt-6-luna (pago) ──ok──► respuesta + línea en data/metrics.jsonl
```

- **Primario (gratuito):** Google Gemini `gemini-3.5-flash-lite`, plan gratuito de la API.
- **Respaldo (pago):** OpenAI `gpt-6-luna`, con `reasoning_effort="none"`.
- **Abstracción común:** los dos heredan de `LLMProvider` ([src/llm/base.py](src/llm/base.py)) y devuelven la misma respuesta normalizada (texto, tokens, latencia y costo). Sumar un proveedor es sumar una subclase.
- **Reintentos:** solo ante errores transitorios (429, 5xx, timeout, red), con espera exponencial y jitter. Si el servidor manda `Retry-After`, se respeta; si pide esperar más de 10 s, se pasa directo al respaldo. Una clave inválida o un modelo inexistente no se reintentan.
- **Costo:** tokens que informa la API × precios de [config/pricing.json](config/pricing.json), tomados de la documentación oficial de cada proveedor (con fuente y fecha). Gemini cuesta 0 en el plan gratuito.
- **Tope de gasto:** antes de llamar a OpenAI se suma lo gastado en `data/metrics.jsonl`; si llegó a `BUDGET_USD` (USD 4.50), no se lo llama.

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
# Consultar al modelo (Gemini; si falla, OpenAI)
python -m src.main "no me llega la factura de agosto"

# Lo mismo, mostrando proveedor, tokens, latencia y costo (en la salida de errores)
python -m src.main --detalle "no me llega la factura de agosto"

# Forzar un proveedor, sin respaldo (por ejemplo, para probar OpenAI)
python -m src.main --proveedor openai --detalle "no me llega la factura de agosto"

# Correr los tests (no llaman a ninguna API)
python -m unittest discover -s tests
```

La respuesta va a la salida estándar; los avisos y el detalle, a la salida de errores. Códigos de salida: `0` ok · `2` consulta vacía · `3` fallaron todos los proveedores · `5` error de configuración (en PowerShell: `echo $LASTEXITCODE`).

### Métricas (`data/metrics.jsonl`)

Una línea JSON por llamada a cada proveedor, solo se agrega (append-only). No guarda el texto de la consulta ni de la respuesta. Ejemplo real (25/11/2026): Gemini respondió "high demand" (error 5xx del servidor) en los 3 intentos y respondió el respaldo:

```json
{"timestamp": "2026-11-25T13:12:53+00:00", "provider": "gemini", "model": "gemini-3.5-flash-lite", "temperature": 0.0, "fallback": false, "status": "error", "error_kind": "server_error", "attempts": 3, "cost_usd": 0.0}
{"timestamp": "2026-11-25T13:12:57+00:00", "provider": "openai", "model": "gpt-6-luna", "temperature": 0.0, "fallback": true, "status": "ok", "attempts": 1, "prompt_tokens": 13, "completion_tokens": 42, "total_tokens": 55, "latency_s": 3.034, "cost_usd": 2.23e-05}
```

El costo se puede rehacer a mano con `config/pricing.json`: 13 × 0.10 / 1.000.000 + 42 × 0.50 / 1.000.000 = USD 0.0000223.

`status` es `ok`, `error` (con `error_kind`: `rate_limit`, `server_error`, `timeout`, `auth_error`…) o `skipped` (tope de gasto). `cost_usd` se guarda como número (un valor chico puede verse como `1.8e-05`, que es JSON válido); en pantalla se muestra con 6 decimales.

## Estructura

```
src/       código del servicio (src/llm/: proveedores y router)
config/    precios por modelo (pricing.json)
prompts/   prompts del triage, versionados en YAML
evals/     dataset de evaluación y runner
data/      métricas de cada ejecución (data/metrics.jsonl)
tests/     tests con unittest, sin llamadas a APIs
docs/      documentación: decisiones (DECISIONES.md) y prompts usados con IA
```

## Uso de IA

El proyecto se construye con asistencia de Claude (Anthropic). Los prompts usados en cada paso
están en [docs/prompts_ia.md](docs/prompts_ia.md).
