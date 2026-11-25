# Decisiones técnicas

Cada decisión dice qué se eligió, por qué y de dónde sale: la consigna del PI, una lección de Henry,
la documentación oficial de un proveedor o una **decisión propia** del alumno.

| # | Decisión | Por qué | Fuente |
|---|---|---|---|
| D-01 | Repositorio nuevo `henry-ai-engineering_pt-08_PI-M1_franco-dauro`, construido paso a paso | Cubrir exactamente lo que pide el PI, con un commit por entregable. El desarrollo exploratorio anterior queda como antecedente en [nubbix-triage](https://github.com/francodauro/nubbix-triage) | Decisión propia (Henry no exige un formato de nombre) |
| D-02 | Gemini `gemini-3.5-flash-lite` como primario y OpenAI `gpt-6-luna` como respaldo | El PI pide ≥2 proveedores configurables. Gemini tiene plan gratuito; `gpt-6-luna` es el modelo más económico de OpenAI. Objetivo del alumno: gastar menos de USD 5 en el curso | PI (Objetivos) + decisión propia |
| D-03 | Abstracción `LLMProvider` con una respuesta normalizada (`LLMResponse`) y un router con fallback | La lógica de negocio no depende de un proveedor: cambiar o sumar uno no toca el resto | PI (Guía: "abstracción mínima LLMProvider o similar") + M1L1 |
| D-04 | Precios en `config/pricing.json` con fuente y fecha; Gemini a costo 0 | Costo reproducible y auditable: tokens de la API × precio publicado. Gemini se usa en el plan gratuito (sin facturación); el precio del plan pago queda anotado como referencia | PI (Guía: Observabilidad) + documentación oficial (25/11/2026) |
| D-05 | Reintentos solo para 429, 5xx, timeout y red; backoff exponencial con jitter; `Retry-After` manda; si pide esperar > 10 s, se pasa al respaldo | Los errores transitorios se resuelven esperando; los demás (clave inválida, modelo inexistente) no. Esperar más de 10 s es peor que usar el respaldo | M1L1 (Rate limits) + decisión propia (el tope de 10 s) |
| D-06 | Tope de gasto `BUDGET_USD=4.50`, sumado desde `data/metrics.jsonl` | Que el proveedor pago nunca supere el presupuesto del alumno | M1L1 (presupuesto de uso) + decisión propia (el monto) |
| D-07 | `data/metrics.jsonl` con una línea por llamada, sin texto de consulta ni respuesta | Responde costo, latencia y consumo sin guardar datos de clientes | PI (Entregables: registro de métricas) + M1L4 (no registrar entradas en bruto) |
| D-08 | `cost_usd` como número en el archivo y con 6 decimales en pantalla | En el archivo, `1.8e-05` es JSON válido y se suma bien; en pantalla, `0.000018` se lee de un vistazo | Decisión propia |
| D-09 | `temperature=0`, `reasoning_effort="none"` en OpenAI, topes de salida 1024 (Gemini) y 400 (OpenAI) | La misma consulta tiene que dar la misma respuesta; sin razonamiento, `gpt-6-luna` es más rápido y barato. Gemini necesita más margen porque sus tokens de "pensamiento" cuentan como salida | M1L1 (Sampling) + decisión propia (los topes) |
