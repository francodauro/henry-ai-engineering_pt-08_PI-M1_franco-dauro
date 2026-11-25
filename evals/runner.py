"""Suite de evals del triage de Nubbix (entregable ``evals/runner.py`` del PI, M1L5).

Uso (PowerShell, desde la raíz del proyecto, con el entorno virtual activo):

    python -m evals.runner --proveedor gemini --prompt v1     # corre los 40 casos con Gemini (gratis)
    python -m evals.runner --proveedor openai --prompt v1     # los mismos casos con gpt-6-luna (pago)
    python -m evals.runner --desde "evals/results/*.jsonl"    # solo el reporte, sin llamar a la API

Qué hace:
1. Corre cada caso del dataset con **un solo proveedor y sin respaldo**: una corrida nunca mezcla modelos.
2. Si un caso falla porque el proveedor no respondió (por ejemplo "high demand") después de los reintentos
   de red, al terminar se lo vuelve a intentar una vez, después de una pausa. Si sigue fallando, la
   corrida queda **incompleta** y el reporte no la usa para comparar.
3. Guarda la corrida en su propio archivo ``evals/results/AAAAMMDD-HHMMSS_<prompt>_<proveedor>.jsonl``,
   creado en modo ``"x"``: nunca pisa una corrida anterior.
4. Escribe el reporte markdown (``evals/reporte.md`` por defecto) con exact match global y por categoría,
   umbral de 0.70, plazos vagos y costo por acierto.

Es un script simple, sin pytest ni frameworks (lo pide el PI).

Texto de la consulta en la corrida: cada línea guarda el texto del caso y la respuesta del modelo. Se hace
porque es un trabajo educativo con un dataset ficticio, no un servicio en producción (ver DECISIONES.md).
``data/metrics.jsonl`` sigue sin guardar texto.

Códigos de salida: 0 corrida completa sin regresiones · 1 completa con regresiones · 2 incompleta ·
5 error de configuración o de datos.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from src.config import PROJECT_ROOT, PROVIDER_NAMES, ConfigError, load_settings
from src.contract import CATEGORIES
from src.costs import Pricing, PricingError
from src.llm.base import AllProvidersFailedError, ProviderError
from src.llm.factory import build_providers
from src.llm.router import Router
from src.metrics import MetricsLog
from src.prompts import PromptError, PromptTemplate, load_prompt
from src.triage import ContractError, triage

from .metricas import CONTRATO_INVALIDO, ERROR_API, MODELO_REF, OK, exact_match, resumir
from .reporte import generar_reporte

DATASET_PATH = PROJECT_ROOT / "evals" / "dataset.jsonl"
RESULTS_DIR = PROJECT_ROOT / "evals" / "results"
REPORTE_PATH = PROJECT_ROOT / "evals" / "reporte.md"

DIFICULTADES = ("facil", "ambiguo", "dificil")
LOTES = ("dev", "holdout")
CAMPOS = ("id", "texto", "categoria_esperada", "dificultad", "lote", "nota")

# Segundos entre casos. Gemini: el plan gratuito limita las llamadas por minuto; 6 s ≈ 10 casos por minuto
# (lo que funcionó en nubbix-triage). OpenAI no lo necesita.
PAUSA_POR_PROVEEDOR = {"gemini": 6.0, "openai": 0.0}
# Espera antes de reintentar los casos que fallaron por el proveedor ("high demand" suele durar poco).
PAUSA_REINTENTO = 30.0

EXIT_OK = 0
EXIT_REGRESION = 1
EXIT_INCOMPLETA = 2
EXIT_CONFIG = 5


class EvalError(Exception):
    """Un problema con los datos de la suite: el dataset o los archivos de corridas."""


class CorridaAbortada(Exception):
    """El proveedor falló por algo que esperar no arregla (clave inválida, tope de gasto…): no tiene sentido seguir."""


# --------------------------------------------------------------------------- dataset


def cargar_dataset(path: Path = DATASET_PATH) -> list[dict]:
    """Lee y valida el dataset. Un error dice en qué línea está, para corregirlo a mano."""
    casos, ids = [], set()
    with open(path, encoding="utf-8") as f:
        for numero, linea in enumerate(f, start=1):
            if not linea.strip():
                continue
            try:
                caso = json.loads(linea)
            except json.JSONDecodeError as exc:
                raise EvalError(f"{path.name}, línea {numero}: no es JSON válido ({exc.msg})") from exc
            faltan = [c for c in CAMPOS if not str(caso.get(c) or "").strip()]
            if faltan:
                raise EvalError(f"{path.name}, línea {numero}: faltan campos {faltan}")
            if caso["id"] in ids:
                raise EvalError(f"{path.name}, línea {numero}: el id {caso['id']} está repetido")
            for campo, validos in (("categoria_esperada", tuple(CATEGORIES)), ("dificultad", DIFICULTADES), ("lote", LOTES)):
                if caso[campo] not in validos:
                    raise EvalError(f"{path.name}, línea {numero}: {campo}={caso[campo]!r} debe ser uno de {validos}")
            ids.add(caso["id"])
            casos.append(caso)
    if not casos:
        raise EvalError(f"{path.name} no tiene casos")
    return casos


def describir_dataset(casos: list[dict], path: Path) -> dict:
    try:
        ruta = path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        ruta = path.name
    return {"ruta": ruta, "n": len(casos), "por_categoria": dict(Counter(c["categoria_esperada"] for c in casos))}


# --------------------------------------------------------------------------- un caso


class RouterDeCorrida:
    """Envuelve al router para la corrida: marca cada línea de ``metrics.jsonl`` con el nombre de la corrida
    y junta las respuestas (incluidas las de los reintentos de contrato), para sumar tokens y costo del caso."""

    def __init__(self, router: Router, corrida: str):
        self.router = router
        self.corrida = corrida
        self.respuestas = []

    def ask(self, prompt, system=None, *, tool=None, context=None, extra_fields=None):
        contexto = {**(context or {}), "corrida": self.corrida}
        respuesta = self.router.ask(prompt, system, tool=tool, context=contexto, extra_fields=extra_fields)
        self.respuestas.append(respuesta)
        return respuesta


def evaluar_caso(caso: dict, router: Router, template: PromptTemplate, *, corrida: str, proveedor: str, modelo: str,
                 temperature: float, max_attempts: int, reloj: Callable[[], float] = time.perf_counter) -> dict:
    """Corre un caso y devuelve su registro: referencia, salida, tokens, latencia y costo juntos (M1L5).

    :raises CorridaAbortada: si el proveedor falló por un error que no es transitorio.
    """
    envuelto = RouterDeCorrida(router, corrida)
    resultado, estado, error = None, OK, None
    inicio = reloj()
    try:
        outcome = triage(caso["texto"], envuelto, template, max_attempts=max_attempts)
        resultado = outcome.result
    except ContractError as exc:
        estado, error = CONTRATO_INVALIDO, str(exc)
    except AllProvidersFailedError as exc:
        transitorio = all(isinstance(e, ProviderError) and e.retryable for e in exc.errors)
        if not transitorio:
            raise CorridaAbortada(str(exc)) from exc
        estado, error = ERROR_API, ", ".join(getattr(e, "kind", "error") for e in exc.errors)
    latencia = reloj() - inicio

    obtenida = resultado.category if resultado else None
    return {
        "corrida": corrida,
        "caso_id": caso["id"],
        "version_prompt": template.version,
        "proveedor": proveedor,
        "modelo": modelo,
        "temperature": temperature,
        "lote": caso["lote"],
        "dificultad": caso["dificultad"],
        "texto": caso["texto"],
        "categoria_esperada": caso["categoria_esperada"],
        "categoria_obtenida": obtenida,
        "acierto": exact_match(obtenida, caso["categoria_esperada"]),
        "estado": estado,
        "error": error,
        "answer": resultado.answer if resultado else None,
        "confidence": resultado.confidence if resultado else None,
        "actions": list(resultado.actions) if resultado else None,
        "intentos_contrato": len(envuelto.respuestas),
        "reintentado_al_final": False,
        "input_tokens": sum(r.prompt_tokens for r in envuelto.respuestas),
        "output_tokens": sum(r.completion_tokens for r in envuelto.respuestas),
        "latencia_s": round(latencia, 3),
        "costo_usd": sum(r.cost_usd for r in envuelto.respuestas),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


# --------------------------------------------------------------------------- la corrida


def nombre_corrida(version: str, proveedor: str, ahora: datetime) -> str:
    return f"{ahora:%Y%m%d-%H%M%S}_{version}_{proveedor}"


def correr(casos: list[dict], router: Router, template: PromptTemplate, *, corrida: str, proveedor: str, modelo: str,
           temperature: float, max_attempts: int, pausa: float, pausa_reintento: float = PAUSA_REINTENTO,
           sleep: Callable[[float], None] = time.sleep, avisar: Callable[[str], None] = print,
           reloj: Callable[[], float] = time.perf_counter) -> list[dict]:
    """Corre todos los casos; al final reintenta una vez los que fallaron por el proveedor."""
    datos = {"corrida": corrida, "proveedor": proveedor, "modelo": modelo, "temperature": temperature,
             "max_attempts": max_attempts, "reloj": reloj}
    registros = []
    for i, caso in enumerate(casos, start=1):
        if i > 1 and pausa:
            sleep(pausa)
        registro = evaluar_caso(caso, router, template, **datos)
        registros.append(registro)
        marca = "✓" if registro["acierto"] else ("sin respuesta del proveedor" if registro["estado"] == ERROR_API else "✗")
        avisar(f"[{i}/{len(casos)}] {caso['id']} esperada {caso['categoria_esperada']}, "
               f"obtenida {registro['categoria_obtenida'] or '—'} {marca}")

    fallidos = [i for i, r in enumerate(registros) if r["estado"] == ERROR_API]
    if fallidos:
        avisar(f"{len(fallidos)} caso(s) sin respuesta del proveedor. Se reintentan en {pausa_reintento:g} s.")
        sleep(pausa_reintento)
        for n, i in enumerate(fallidos):
            if n and pausa:
                sleep(pausa)
            nuevo = evaluar_caso(casos[i], router, template, **datos)
            nuevo["reintentado_al_final"] = True
            registros[i] = nuevo
            resultado = "respondió" if nuevo["estado"] != ERROR_API else "sigue sin respuesta"
            avisar(f"Reintento {casos[i]['id']}: {resultado}.")
    return registros


def guardar_corrida(registros: list[dict], corrida: str, carpeta: Path = RESULTS_DIR) -> Path:
    """Escribe un archivo nuevo. Modo ``"x"``: si ya existe, falla en vez de pisar una corrida anterior."""
    carpeta.mkdir(parents=True, exist_ok=True)
    path = carpeta / f"{corrida}.jsonl"
    with open(path, "x", encoding="utf-8", newline="\n") as f:
        for r in registros:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return path


# --------------------------------------------------------------------------- reporte desde archivos


def expandir(patrones: list[str]) -> list[Path]:
    """Expande los comodines acá, porque PowerShell no los expande al llamar a Python."""
    rutas: list[Path] = []
    for patron in patrones:
        encontrados = sorted(glob.glob(patron)) or sorted(glob.glob(str(PROJECT_ROOT / patron)))
        if not encontrados:
            raise EvalError(f"No hay archivos que coincidan con {patron!r}")
        rutas += [Path(p) for p in encontrados if Path(p) not in rutas]
    return rutas


def leer_corrida(path: Path) -> list[dict]:
    registros = []
    with open(path, encoding="utf-8") as f:
        for numero, linea in enumerate(f, start=1):
            if linea.strip():
                try:
                    registros.append(json.loads(linea))
                except json.JSONDecodeError as exc:
                    raise EvalError(f"{path.name}, línea {numero}: no es JSON válido ({exc.msg})") from exc
    if not registros:
        raise EvalError(f"{path.name} está vacío")
    return registros


def costos_en_metrics(metrics: MetricsLog, corridas: list[str]) -> dict[str, float | None]:
    """Suma ``cost_usd`` de ``data/metrics.jsonl`` por corrida, para comprobar el costo de cada una."""
    lineas = metrics.read_all()
    costos = {}
    for corrida in corridas:
        propias = [r for r in lineas if r.get("corrida") == corrida]
        costos[corrida] = sum(float(r.get("cost_usd") or 0.0) for r in propias) if propias else None
    return costos


def precio_referencia(pricing_path: Path) -> dict[str, float] | None:
    """Precio de ``MODELO_REF`` en ``config/pricing.json``, para proyectar el costo. ``None`` si no está."""
    try:
        return Pricing(pricing_path).price(MODELO_REF)
    except (PricingError, OSError, KeyError):
        return None


def escribir_reporte(corridas: list[list[dict]], casos: list[dict], dataset_path: Path, metrics: MetricsLog,
                     reporte_path: Path, precio_ref: dict[str, float] | None = None) -> list[dict]:
    resumenes = [resumir(r, precio_ref) for r in corridas]
    costos = costos_en_metrics(metrics, [r["corrida"] for r in resumenes])
    texto = generar_reporte(resumenes, describir_dataset(casos, dataset_path), costos)
    reporte_path.parent.mkdir(parents=True, exist_ok=True)
    reporte_path.write_text(texto, encoding="utf-8", newline="\n")
    return resumenes


# --------------------------------------------------------------------------- CLI


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m evals.runner", description="Suite de evals del triage de Nubbix.")
    p.add_argument("--proveedor", choices=PROVIDER_NAMES, help="proveedor de la corrida (por defecto, el primario)")
    p.add_argument("--prompt", help="versión del prompt (por ejemplo v1); por defecto, PROMPT_VERSION del .env")
    p.add_argument("--pausa", type=float, help="segundos entre casos (por defecto: Gemini 6, OpenAI 0)")
    p.add_argument("--desde", nargs="+", metavar="ARCHIVO",
                   help="no corre nada: arma el reporte con estas corridas guardadas (acepta comodines)")
    p.add_argument("--reporte", default=str(REPORTE_PATH), help="dónde escribir el reporte (por defecto evals/reporte.md)")
    return p.parse_args(argv)


def codigo_salida(resumenes: list[dict]) -> int:
    if any(not r["completa"] for r in resumenes):
        return EXIT_INCOMPLETA
    return EXIT_REGRESION if any(r["regresiones"] for r in resumenes) else EXIT_OK


def imprimir_resumen(resumenes: list[dict], reporte_path: Path) -> None:
    for r in resumenes:
        cats = " · ".join(f"{c} {d['score']:.0%}" for c, d in r["por_categoria"].items())
        costo = "—" if r["costo_por_acierto"] is None else f"USD {r['costo_por_acierto']:.6f}"
        lotes = " · ".join(f"{l} {d['score']:.0%}" for l, d in r["por_lote"].items() if d["score"] is not None)
        print(f"\n{r['corrida']}: global {r['score']:.0%} ({r['aciertos']}/{r['n']}) · {cats} · {lotes}")
        print(f"  plazos vagos: {len(r['plazos_vagos'])} · costo total USD {r['costo_total']:.6f} · costo por acierto {costo}")
        if not r["completa"]:
            print(f"  INCOMPLETA: sin respuesta en {', '.join(r['errores_api'])}. Volvé a correrla; no se usa para comparar.")
        elif r["regresiones"]:
            print("  REGRESIÓN: " + "; ".join(r["regresiones"]))
        else:
            print("  OK: todas las categorías superan el umbral y no hay plazos vagos.")
    print(f"\nReporte: {reporte_path}")


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parse_args(argv)
    reporte_path = Path(args.reporte)

    try:
        settings = load_settings()
        casos = cargar_dataset(DATASET_PATH)
        metrics = MetricsLog(settings.metrics_path)

        if args.desde:
            corridas = [leer_corrida(p) for p in expandir(args.desde)]
            resumenes = escribir_reporte(corridas, casos, DATASET_PATH, metrics, reporte_path,
                                         precio_referencia(settings.pricing_path))
            imprimir_resumen(resumenes, reporte_path)
            return codigo_salida(resumenes)

        proveedor = args.proveedor or settings.provider_order[0]
        template = load_prompt(args.prompt or settings.prompt_version, settings.prompts_dir)
        pricing = Pricing(settings.pricing_path)
        (provider,) = build_providers(settings, only=proveedor)  # uno solo: sin respaldo
        pricing.price(provider.model)
    except (ConfigError, PromptError, PricingError, ProviderError, EvalError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_CONFIG

    router = Router(
        [provider], pricing, metrics,
        budget_usd=settings.budget_usd, max_retries=settings.max_retries, max_wait_s=settings.max_wait_seconds,
        on_failure=lambda name, exc: print(f"  Aviso: {name} no respondió ({getattr(exc, 'kind', 'error')}).", file=sys.stderr),
    )
    pausa = PAUSA_POR_PROVEEDOR.get(proveedor, 0.0) if args.pausa is None else args.pausa
    corrida = nombre_corrida(template.version, proveedor, datetime.now())
    print(f"Corrida {corrida}: {len(casos)} casos con {provider.name} ({provider.model}), "
          f"prompt {template.version}, pausa {pausa:g} s, sin respaldo.")
    try:
        registros = correr(casos, router, template, corrida=corrida, proveedor=provider.name, modelo=provider.model,
                           temperature=provider.temperature, max_attempts=settings.contract_max_attempts, pausa=pausa)
    except CorridaAbortada as exc:
        print(f"Error: corrida cancelada, el proveedor falló por algo que reintentar no arregla: {exc}", file=sys.stderr)
        return EXIT_CONFIG

    path = guardar_corrida(registros, corrida)
    print(f"Corrida guardada en {path}")
    resumenes = escribir_reporte([registros], casos, DATASET_PATH, metrics, reporte_path, pricing.price(MODELO_REF))
    imprimir_resumen(resumenes, reporte_path)
    return codigo_salida(resumenes)


if __name__ == "__main__":
    sys.exit(main())
