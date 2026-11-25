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
