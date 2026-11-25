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

---

## Paso 3 — Dataset y suite de evals (25/11/2026)

```text
## Contexto
Sigo con el repositorio `henry-ai-engineering_pt-08_PI-M1_franco-dauro` (Proyecto Integrador M1
de Henry: triage de consultas de soporte de Nubbix). El paso 2 dejó la CLI que devuelve el contrato
validado con el prompt `triage_v1`, usando Gemini como primario y OpenAI como respaldo. Windows 11 / PowerShell.

## Tarea de este paso
Crear el dataset de evaluación y una suite de evals que corra por comando y mida la calidad del
triage con datos: score global y por categoría, umbral, costo por acierto y reporte.

## Requisitos
- Dataset `evals/dataset.jsonl`: reusar los 40 casos de `nubbix-triage` (10 por categoría, 28 no
  fáciles), con solo los campos necesarios: `id`, `texto`, `categoria_esperada`, `dificultad`, `nota`
  (por qué esa es la categoría correcta) y `lote` (`dev` / `holdout`, para el paso 4).
- La referencia se fija antes de correr: el dataset se commitea antes de la primera corrida.
- Runner `python -m evals.runner`: un script simple, sin pytest ni framework. Corre todos los casos
  con un solo proveedor elegido (`--proveedor gemini|openai`) y un prompt (`--prompt v1`),
  sin fallback, para que una corrida nunca mezcle modelos.
- Si un caso falla por un error transitorio (por ejemplo "high demand") después de los reintentos
  de red, al terminar se vuelven a intentar solo los casos fallidos, una vez y después de una pausa.
  Si alguno sigue fallando, la corrida queda marcada como "incompleta" y no se usa para comparar.
- Métricas: exact match de la categoría, global y por categoría; umbral de 0,70 por categoría fijado
  de antemano (una categoría por debajo es una regresión); costo total y costo por acierto.
- Plazos vagos: contar las respuestas (`answer`) con expresiones de tiempo vagas ("a la brevedad",
  "en breve", "lo antes posible"…), global y por categoría. Es un error de respuesta aunque la
  categoría sea correcta: una sola respuesta con un plazo vago ya es una regresión (umbral 0).
  La lista de expresiones vive en un solo lugar, para reusarla en el guardrail de salida del paso 5.
- Una corrida = un archivo en `evals/results/` que nunca se pisa (fecha y hora, proveedor y prompt
  en el nombre). Cada línea guarda caso, categoría esperada y obtenida, `answer`, tokens, latencia y
  costo, e incluye el texto de la consulta. Esto se hace porque es un trabajo educativo con un
  dataset ficticio, no un servicio en producción. La salvedad queda documentada en DECISIONES.md y
  en el README. `data/metrics.jsonl` sigue sin guardar texto.
- Reporte en markdown, generado a partir de una o varias corridas guardadas, sin llamar a la API,
  que responda: qué se evaluó (dataset, n, proveedor, modelo, prompt), si alguna categoría quedó
  bajo el umbral (con números), y si el score y el costo por acierto cuentan la misma historia.
  La conclusión la escribo yo a mano.
- Validación contra la M1L5 de Henry y `nubbix-triage`: si algo difiere entre los dos, avisame
  antes de decidir.
- Tests con `unittest`, sin llamadas reales a las APIs.

## Fuera de alcance
Prompt v2 y su comparación (paso 4), guardrails (paso 5), LLM-as-judge.

## Terminado cuando
- Pasan todos los tests.
- Hay una corrida completa con Gemini (costo 0) y una con OpenAI `gpt-6-luna` (≈ USD 0.01),
  cada una en su archivo, con `triage_v1`.
- El reporte de las dos corridas responde las tres preguntas, y el costo de la corrida de OpenAI
  coincide con la suma de `cost_usd` de sus líneas.
```

**Cómo influyó en las decisiones** (detalle en [DECISIONES.md](DECISIONES.md), D-17 a D-25)
- El borrador del alumno pedía guardar el texto de la consulta en cada corrida. Se aceptó con la salvedad
  escrita (trabajo educativo, dataset ficticio), igual que el `RegistroEval` de la M1L5, que también guarda
  `texto`. En `nubbix-triage` se había hecho lo contrario (sin texto); `data/metrics.jsonl` sigue sin texto.
- "Las justas y necesarias para cumplir con el PI": de los 8 campos de la referencia quedaron 6. Se sacaron
  `regla` y `criterio` (solo servían para el juez); se conservó `lote` para decidir el paso 4 con holdout.
  Los nombres `categoria_esperada` y `nota` son los de la M1L5.
- "Una corrida completa y entera de cada modelo": el runner nunca usa el respaldo, reintenta al final los
  casos que el proveedor no respondió y, si alguno sigue sin respuesta, marca la corrida como incompleta.
  La corrida con `gpt-6-luna` se adelantó a este paso por pedido del alumno.
- Los plazos vagos pasaron de "medirlos" a "una sola respuesta ya es regresión", por decisión del alumno.
- Para que el costo sea auditable, cada línea de `data/metrics.jsonl` lleva el nombre de la corrida, y el
  reporte compara la suma de `cost_usd` de esas líneas con el `costo_usd` de la corrida (nombre de la M1L5).

---

## Paso 4 — Prompt `triage_v2` comparado contra `v1` (25/11/2026)

```text
## Contexto
Sigo con el repositorio `henry-ai-engineering_pt-08_PI-M1_franco-dauro` (Proyecto Integrador M1
de Henry: triage de consultas de soporte de Nubbix). El paso 3 dejó la suite de evals:
`triage_v1` (zero-shot) sacó 98 % con Gemini y con `gpt-6-luna`, con un único error repetido en los
dos (NX-008, un cambio de plan con cobro de la diferencia, clasificado `other` en vez de `billing`).
Gemini además escribió un plazo vago. Windows 11 / PowerShell.

## Tarea de este paso
Crear `triage_v2` con otra técnica de prompting, compararla contra `v1` con el runner y elegir la
versión vigente con datos, como pide el PI (≥2 versiones comparadas contra el dataset; la técnica se
justifica con resultados, no con opiniones).

## Requisitos
- Técnica: few-shot (M1L2). La lección recomienda tomar el caso mal clasificado, corregirlo y
  mostrarlo como ejemplo. No uso chain-of-thought porque el razonamiento necesita un campo donde
  escribirse y el contrato `{answer, confidence, category, actions}` no se cambia.
- Un solo cambio respecto de `v1`: `v2` = `v1` + un par de ejemplos de contraste, para poder
  atribuirle la diferencia. Los plazos vagos no se tocan acá (se resuelven en el paso 5 con el guardrail).
- Los ejemplos son inventados, nunca casos del dataset (si estuvieran, el examen traería la respuesta):
  uno que pide cambiar el plan contratado y su cobro (`billing`) y otro parecido que solo pregunta
  un precio (`other`).
- El reporte muestra además el score por lote (`dev` / `holdout`), los casos que cambian entre corridas
  de la misma versión (inestables) y el costo proyectado con los precios de `gpt-6-luna`, porque con
  Gemini el costo real es 0 y así se ve cuánto cuestan los tokens extra de los ejemplos.
- Corridas: dos con Gemini por versión (una más de `v1` y dos de `v2`) y una de `v2` con `gpt-6-luna`
  (≈ USD 0.007), para ver si `v2` corrige NX-008 en los dos modelos.
- Criterio para elegir, fijado antes de correr, sobre las corridas de Gemini: `v2` queda vigente si
  (1) su score en `holdout` no es menor que el de `v1`, (2) su score global no es menor que el de `v1`,
  (3) ninguna categoría queda bajo 70 % en ninguna de sus corridas, (4) no tiene más plazos vagos que
  `v1` y (5) acierta NX-008 en sus dos corridas. Si falla cualquiera, sigue `v1`, que es más simple y
  más barata.
- Documentación: `prompts/triage_v2.yaml`; entrada en el CHANGELOG (qué cambia, por qué y qué resultado
  se espera); sección del README "Técnica elegida y por qué" con la tabla `v1` contra `v2`; decisiones
  en DECISIONES.md. La conclusión la escribo yo (con ayuda si la necesito).
- Tests con `unittest`, sin llamadas reales a las APIs.

## Fuera de alcance
Guardrails y `v3` con seguridad (paso 5) y la comparativa de modelos como extra credit (paso 6).

## Terminado cuando
- Pasan todos los tests.
- Hay dos corridas completas con Gemini de cada versión y una de `v2` con `gpt-6-luna`.
- El reporte compara las dos versiones por categoría y por lote, con casos inestables y costo
  por acierto (real y proyectado).
- La versión vigente queda elegida con el criterio de arriba y su fundamento escrito.
```

**Cómo influyó en las decisiones** (detalle en [DECISIONES.md](DECISIONES.md), D-27 a D-30)
- El primer borrador del alumno dejaba abiertos el criterio ("que el costo extra se justifique"), la cantidad
  de corridas y el proveedor. Se resolvieron antes de correr: cinco condiciones que se chequean sin opinar,
  dos corridas por versión con Gemini y una de `v2` con `gpt-6-luna`.
- Como con Gemini el costo real es 0, "el costo de los ejemplos" no se podía medir: se agregó al reporte el
  costo proyectado con los precios de `gpt-6-luna`, que informa pero no decide.
- Con dos corridas por versión, el reporte marca los casos inestables, para no confundir azar con mejora.
- Los ejemplos se tomaron de `nubbix-triage` v9 (no son casos del dataset y ya se habían probado), pero sin la
  regla escrita que los acompañaba allá, para que `v2` tenga un solo cambio: los ejemplos.

### Paso 4, segundo intento — `triage_v3` (25/11/2026)

Después de ver que `v2` no cumplía el criterio, el alumno preguntó:

```text
Podríamos generar un mejor few shot?
```

**Cómo influyó en las decisiones** (D-31 y D-32)
- La IA explicó qué falló en `v2`: el ejemplo de `billing` compartía tema y palabras con NX-036, y `gpt-6-luna` se guió
  por ese parecido. Propuso un par sobre un tema que no aparece en el dataset (almacenamiento extra), con los dos
  ejemplos iguales salvo la intención, y advirtió el riesgo de probar varias versiones sobre el mismo dataset.
- El alumno eligió cambiar **solo los ejemplos** (no sumar la regla escrita que tenía `nubbix-triage` v9), para poder
  atribuir una mejora a la elección de los ejemplos, y prefirió no fijar todavía si `v3` es el último intento.
- `v3` se compara contra `v1` con el mismo criterio de `v2` (D-30), commiteado antes de correr.
