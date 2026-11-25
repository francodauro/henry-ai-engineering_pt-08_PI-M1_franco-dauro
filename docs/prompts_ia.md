# Prompts usados con IA

La guía del PI pide documentar los prompts usados con herramientas de IA y cómo influyeron en las
decisiones técnicas. Este proyecto se construye paso a paso con **Claude (Anthropic)**. En cada paso,
el prompt lo redacta el alumno, se revisa con la IA **antes de usarlo** y se registra acá tal como se usó.

**Antecedente:** antes de este repositorio hubo un desarrollo exploratorio, lección por lección,
en [nubbix-triage](https://github.com/francodauro/nubbix-triage). Se usa como referencia: en cada
paso se toma lo que funcionó y se simplifica a lo que pide la consigna.

---

## Paso 0 — Esqueleto del proyecto (24/11/2026)

```text
## Contexto
Soy alumno de AI Engineering en Henry (cohorte ai-engineering-pt08). Construyo el Proyecto
Integrador del Módulo 1, repositorio `henry-ai-engineering_pt-08_PI-M1_franco-dauro`: un servicio
de triage para Nubbix, un SaaS de gestión para pymes.
Recibe una consulta de soporte en texto libre y devuelve un JSON validado con el contrato
{answer, confidence, category, actions}, con category ∈ {billing, technical, account, other}.
La consigna completa está en la plataforma de Henry, sección "M1PI | Proyecto".

## Tarea de este paso
Armá solo el esqueleto del proyecto en Python, sin lógica de negocio todavía.

## Requisitos
- Estructura de carpetas sugerida por la guía del PI: src/, prompts/, evals/, data/, tests/ y docs/.
- Dos proveedores de LLM configurables:
  - primario gratuito: Google Gemini (`gemini-3.5-flash-lite`, plan gratuito);
  - respaldo pago: OpenAI (`gpt-6-luna`).
- Credenciales en un archivo `.env` local que nunca se sube al repo. Su estructura se documenta
  en `.env.example`, sin valores reales. No leas ni modifiques mi `.env`.
- `.gitignore` que solo deje subir archivos de desarrollo (afuera: `.env`, `.venv/`, cachés).
- `requirements.txt` con las dependencias mínimas y versiones fijadas.
- `README.md` mínimo: qué es el proyecto y cómo instalarlo en Windows 11 con PowerShell y `.venv`.
- `docs/prompts_ia.md` para registrar los prompts que uso con IA en cada paso (este es el primero).

## Fuera de alcance
Cliente LLM, contrato, prompts del triage, evals y guardrails: van en los pasos siguientes.

## Terminado cuando
- `pip install -r requirements.txt` instala sin errores en un `.venv` nuevo.
- `git status` no muestra `.env` ni `.venv/`.
- Cada archivo nuevo tiene un propósito que puedo explicar.
```

**Cómo influyó en las decisiones**
- La estructura de carpetas sale de la guía del PI y no de la IA, para que quede respaldada por la consigna.
- `requirements.txt` arranca solo con los SDK de los dos proveedores y `python-dotenv`. Cada paso
  agrega lo que usa (por ejemplo, Pydantic con el contrato), así cada dependencia tiene un motivo.
- `.env.example` documenta solo las variables que existen hasta ahora. Las demás se suman con el paso que las usa.
- `data/metrics.jsonl` se deja preparado para subirse al repo, porque el checklist del PI pide una ejecución registrada.

---

## Paso 1 — Cliente multi-proveedor y métricas (25/11/2026)

```text
## Contexto
Sigo con el repositorio `henry-ai-engineering_pt-08_PI-M1_franco-dauro` (Proyecto Integrador M1
de Henry: triage de consultas de soporte de Nubbix). El paso 0 dejó el esqueleto. Windows 11 / PowerShell.

## Tarea de este paso
Integrar dos LLM por API con una abstracción real (no un llamado hardcodeado a un proveedor),
controlando costo, latencia y errores, y una CLI mínima para probarlo.

## Requisitos
- Abstracción común (`LLMProvider`) con dos implementaciones:
  - Gemini `gemini-3.5-flash-lite` como primario (gratuito);
  - OpenAI `gpt-6-luna` como respaldo (pago).
  Las dos devuelven la misma respuesta normalizada: texto, proveedor, modelo, tokens
  (prompt / completion / total), latencia en segundos y costo en USD.
- Fallback: si el primario falla después de sus reintentos, se llama al respaldo, y la CLI avisa
  qué falló y por qué.
- Reintentos solo ante errores transitorios (rate limit 429, errores 5xx, timeout, red), con backoff
  exponencial y jitter. Si el servidor manda `Retry-After`, se respeta. Si pide esperar más de un
  máximo configurable, se pasa directo al respaldo. Los errores no transitorios (clave inválida,
  modelo inexistente) no se reintentan.
- Costo calculado desde los tokens que informa cada API y una tabla de precios en `config/pricing.json`,
  tomada de la documentación oficial de cada proveedor, con la fuente y la fecha de consulta.
- Tope de gasto `BUDGET_USD` (4.50 por defecto): si lo gastado en OpenAI según las métricas lo alcanza,
  no se llama al proveedor pago.
- Parámetros (modelo, temperature, tope de tokens, reintentos, timeouts) en `.env`, documentados en
  `.env.example` con el motivo de cada valor.
- `data/metrics.jsonl`: una línea por llamada (append-only) con timestamp, proveedor, modelo, tokens,
  latencia, costo y estado (ok / error y tipo). Sin el texto de la consulta ni de la respuesta.
- CLI mínima: `python -m src.main "consulta"` imprime la respuesta del modelo, sin contrato ni prompt
  de sistema todavía. Opciones `--proveedor openai` (forzar un proveedor, para probar el respaldo) y
  `--detalle` (tokens, latencia y costo; el costo en pantalla con 6 decimales, en el archivo como número).
- Tests con `unittest`, sin llamadas reales a las APIs.

## Fuera de alcance
Contrato JSON, prompts del triage en YAML, evals y guardrails: van en los pasos siguientes.

## Terminado cuando
- Pasan todos los tests.
- Una consulta con Gemini y una forzada con OpenAI responden y dejan su línea en `data/metrics.jsonl`.
- El costo de la llamada a OpenAI coincide con tokens × precio de `config/pricing.json`.
```

**Cómo influyó en las decisiones** (detalle en [DECISIONES.md](DECISIONES.md), D-02 a D-09)
- Antes de escribir código se verificaron los precios y las bajas en la documentación oficial de Google y OpenAI
  (25/11/2026): `gpt-6-luna` cuesta USD 0.10 / 0.50 por 1M de tokens y ninguno de los dos modelos tiene baja anunciada.
- Pedir que el respaldo se pueda forzar (`--proveedor openai`) permite probarlo sin esperar a que Gemini falle.
- Escribir el criterio de "terminado" fijó la verificación del costo: tokens × precio, a mano.
