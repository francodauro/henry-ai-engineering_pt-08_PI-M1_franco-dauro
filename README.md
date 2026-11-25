# Nubbix Triage — Proyecto Integrador M1 (Henry, AI Engineering)

Servicio de triage de consultas de soporte para **Nubbix**, un SaaS de gestión para pymes de LATAM.
Recibe una consulta en texto libre y devuelve un JSON validado con el contrato:

```json
{"answer": "...", "confidence": 0.95, "category": "billing", "actions": ["..."]}
```

donde `category` es `billing`, `technical`, `account` u `other`.

> **Estado: paso 0 — esqueleto del proyecto.** Todavía no hay lógica: se construye paso a paso.

## Proveedores de LLM

- **Primario (gratuito):** Google Gemini `gemini-3.5-flash-lite`.
- **Respaldo (pago):** OpenAI `gpt-6-luna`.

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

## Estructura

```
src/       código del servicio
prompts/   prompts del triage, versionados en YAML
evals/     dataset de evaluación y runner
data/      métricas de cada ejecución (data/metrics.jsonl)
tests/     tests con unittest, sin llamadas a APIs
docs/      documentación (incluye los prompts usados con IA)
```

## Uso de IA

El proyecto se construye con asistencia de Claude (Anthropic). Los prompts usados en cada paso
están en [docs/prompts_ia.md](docs/prompts_ia.md).
