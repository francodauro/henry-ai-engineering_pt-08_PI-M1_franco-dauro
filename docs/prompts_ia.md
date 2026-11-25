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

---

## Paso 2 — Contrato JSON (25/11/2026)

```text
## Contexto
Sigo con el repositorio `henry-ai-engineering_pt-08_PI-M1_franco-dauro` (Proyecto Integrador M1
de Henry: triage de consultas de soporte de Nubbix). El paso 1 dejó el cliente multi-proveedor
(Gemini primario, OpenAI respaldo) con reintentos, costo y métricas. Windows 11 / PowerShell.

## Tarea de este paso
Que la CLI devuelva una respuesta estructurada y validada con el contrato del PI, y crear el primer
prompt del triage.

## Requisitos
- Contrato Pydantic `{answer, confidence, category, actions}` con tipo y dominio bien definidos:
  - `answer`: texto no vacío, la respuesta para el cliente;
  - `confidence`: número entre 0 y 1 (cuán seguro está el modelo de la categoría);
  - `category`: solo `billing`, `technical`, `account` u `other`;
  - `actions`: lista no vacía de acciones de una lista cerrada, para el agente humano.
  Categorías y acciones definidas en un solo lugar (única fuente de verdad).
- Tool calling forzado en Gemini y en OpenAI: el modelo está obligado a "llenar el formulario"
  del contrato, y el schema sale del modelo Pydantic (no se escribe dos veces).
- Si la respuesta no cumple el contrato, reintentar (hasta 3 intentos) diciéndole al modelo qué campo
  falló y por qué. Si se agotan los intentos, error con su propio código de salida.
- Primer prompt del triage `v1` en `prompts/triage_v1.yaml`: quién es (soporte de Nubbix), qué hace
  cada categoría y qué no puede prometer. El prompt va en YAML, nunca dentro del código.
- La CLI devuelve por la salida estándar solo el JSON validado, consumible por otro sistema sin
  transformaciones. Los avisos y el detalle, por la salida de errores.
- Las métricas registran también si la respuesta cumplió el contrato, en qué intento y qué campo falló
  (sin el texto de la consulta ni de la respuesta).
- Validación de lo que se proponga contra la M1L3 de Henry y mi proyecto de referencia `nubbix-triage`:
  las categorías, el dominio de cada campo, la lista de acciones y las reglas del prompt. Si algo
  difiere entre los dos, avisame antes de decidir.
- Tests con `unittest`, sin llamadas reales a las APIs.

## Fuera de alcance
Dataset y evals (paso 3), más versiones del prompt (paso 4), guardrails (paso 5).

## Terminado cuando
- Pasan todos los tests.
- Una consulta real devuelve por la salida estándar un JSON que cumple el contrato.
- Un contrato inválido de prueba (por ejemplo `category: "factura"` o `confidence: 47`) se rechaza con
  un mensaje que dice qué campo falló.
```

**Cómo influyó en las decisiones** (detalle en [DECISIONES.md](DECISIONES.md), D-10 a D-16)
- El borrador del alumno decía "`confidence` es 70 %". Al revisarlo se separaron dos conceptos: `confidence`
  es el número entre 0 y 1 que informa el modelo en cada respuesta (M1L3), y el 70 % es el umbral por
  categoría de las evals (M1L5, paso 3).
- Pedir la validación contra la M1L3 y `nubbix-triage` llevó a comparar las acciones con el ejemplo de Henry
  antes de adoptarlas (D-12), y a que el alumno decidiera incluir en `v1` la regla contra los plazos vagos (D-15).
