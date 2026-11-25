# Changelog de prompts

Cada versión es un archivo nuevo en `prompts/` y nunca se edita. Para cada una: qué cambió, por qué y con qué resultado.

## triage_v1 — 2026-11-25

- **Cambio:** primera versión. Zero-shot con los 4 principios de la M1L2 (rol, contexto, tarea, formato) y el contrato `{answer, confidence, category, actions}` por tool calling (M1L3).
- **Por qué:** es la línea base contra la que se comparan las versiones siguientes. Incluye desde el inicio la regla contra los plazos vagos ("a la brevedad"), aprendida en el desarrollo exploratorio ([nubbix-triage](https://github.com/francodauro/nubbix-triage), v8: aparecían en 16 de 20 respuestas).
- **Resultado:** pendiente de medir con la suite de evals (paso 3).
