"""Comparativa de modelos (extra credit del PI, paso 6): Gemini contra ``gpt-6-luna`` con ``triage_v4``.

Uso (PowerShell, desde la raíz del proyecto, con el entorno virtual activo):

    python -m evals.comparativa        # arma evals/comparativa.md con las corridas guardadas (no llama a ninguna API)

No corre nada: junta corridas que ya existen y aplica el criterio de D-45, fijado y commiteado antes de correr.

- Dataset: las corridas de ``triage_v4`` con guardrails de ``evals/results/``. De cada modelo se usan las
  primeras ``CORRIDAS_POR_MODELO`` completas, en orden cronológico (una incompleta no cuenta).
- Adversarial: las corridas sin guardrails de ``triage_v4`` de ``evals/results/adversarial/``. De cada modelo se
  usan las primeras ``CORRIDAS_ADVERSARIAL`` completas.
- Pedidos por consulta: los intentos de red (``attempts``) que ``data/metrics.jsonl`` registra para la corrida,
  divididos por los casos. Incluye los reintentos de red y de contrato, porque también cuentan para el límite
  diario de Gemini.

El reporte muestra cada condición con su resultado y la decisión que sale del criterio. La conclusión se
escribe a mano en el README.

Códigos de salida: 0 criterio evaluado · 2 faltan corridas o datos para evaluarlo · 5 error de configuración
o de datos.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from src.config import PROJECT_ROOT, ConfigError, load_settings
from src.metrics import MetricsLog

from . import adversarial
from .metricas import comparar_versiones, resumir
from .runner import EXIT_CONFIG, EXIT_INCOMPLETA, EXIT_OK, EvalError, expandir, leer_corrida

REPORTE_PATH = PROJECT_ROOT / "evals" / "comparativa.md"
PATRON_DATASET = "evals/results/*.jsonl"
PATRON_ADVERSARIAL = "evals/results/adversarial/*.jsonl"

# --- Criterio D-45, fijado antes de correr. No se ajusta después de ver los datos. ---
PROMPT = "triage_v4"
PRIMARIO = "gemini"                 # el primario actual (D-26)
CANDIDATO = "openai"                # gpt-6-luna
CORRIDAS_POR_MODELO = 4
CORRIDAS_ADVERSARIAL = 2
UMBRAL_CATEGORIA = 0.70
CONSULTAS_POR_MES = 12_000          # 400 tickets por día (consigna del PI) × 30
TOPE_MENSUAL_USD = 2.00             # decisión del alumno (26/11/2026)
TICKETS_POR_DIA = 400               # consigna del PI
LIMITE_DIARIO_GEMINI = 500          # plan gratuito de Gemini (pedidos por día)

NOMBRES = {PRIMARIO: "Gemini", CANDIDATO: "gpt-6-luna"}


# --------------------------------------------------------------------------- selección de corridas


def seleccionar(resumenes: list[dict], proveedor: str, n: int) -> tuple[list[dict], int]:
    """Las primeras ``n`` corridas completas del proveedor, en orden cronológico (el nombre empieza con la fecha).

    :returns: (las elegidas, cuántas completas había en total).
    """
    completas = sorted((r for r in resumenes if r["proveedor"] == proveedor and r["completa"]),
                       key=lambda r: r["corrida"])
    return completas[:n], len(completas)


def es_del_criterio(resumen: dict) -> bool:
    return resumen["version_prompt"] == PROMPT and bool(resumen.get("con_guardrails"))


def es_adversarial_del_criterio(resumen: dict) -> bool:
    return resumen["version_prompt"] == PROMPT and not resumen["guardrails"]


# --------------------------------------------------------------------------- datos de data/metrics.jsonl


def llamadas_de(lineas: list[dict], corrida: str) -> list[dict]:
    """Las líneas de llamadas al modelo de una corrida (sin las de los guardrails)."""
    return [r for r in lineas if r.get("corrida") == corrida and r.get("event") != "guardrail"]


def pedidos_por_consulta(lineas: list[dict], corrida: str, casos: int) -> float | None:
    """Intentos de red registrados para la corrida ÷ casos. ``None`` si la corrida no dejó líneas."""
    propias = llamadas_de(lineas, corrida)
    if not propias or not casos:
        return None
    return sum(int(r.get("attempts") or 0) for r in propias) / casos


def latencia_api(lineas: list[dict], corrida: str) -> float | None:
    """Latencia promedio de las llamadas que respondieron, sin las esperas entre reintentos."""
    ok = [float(r["latency_s"]) for r in llamadas_de(lineas, corrida) if r.get("status") == "ok" and "latency_s" in r]
    return sum(ok) / len(ok) if ok else None


# --------------------------------------------------------------------------- criterio


def _promedio(valores) -> float | None:
    valores = [v for v in valores if v is not None]
    return sum(valores) / len(valores) if valores else None


def resumen_modelo(corridas: list[dict], adversariales: list[dict], lineas: list[dict]) -> dict:
    """Junta, para un modelo, todo lo que mira el criterio y lo que solo informa."""
    grupo = comparar_versiones(corridas)[0] if corridas else None
    casos = sum(r["n"] for r in corridas)
    costo = sum(r["costo_total"] for r in corridas)
    pedidos = {r["corrida"]: pedidos_por_consulta(lineas, r["corrida"], r["n"]) for r in corridas}
    return {
        "corridas": [r["corrida"] for r in corridas],
        "global": _promedio(r["score"] for r in corridas),
        "holdout": _promedio(r["por_lote"]["holdout"]["score"] for r in corridas),
        "peor_categoria": min((d["score"] for r in corridas for d in r["por_categoria"].values()), default=None),
        "falsos_positivos": sum(len(r["falsos_positivos"]) for r in corridas),
        "inestables": grupo["inestables"] if grupo else [],
        "errores": grupo["errores"] if grupo else [],
        "plazos_modelo": sum(len(r["plazos_detectados"]) for r in corridas),
        "plazos_entregados": sum(len(r["plazos_vagos"]) for r in corridas),
        "reintentados": sum(len(r["reintentados"]) for r in corridas),
        "pedidos": pedidos,
        "pedidos_promedio": _promedio(pedidos.values()),
        "pedidos_peor": max((p for p in pedidos.values() if p is not None), default=None),
        "sin_metricas": [c for c, p in pedidos.items() if p is None],
        "latencia": _promedio(r["latencia_promedio"] for r in corridas),
        "latencia_api": _promedio(latencia_api(lineas, r["corrida"]) for r in corridas),
        "costo_total": costo,
        "costo_por_consulta": costo / casos if casos else None,
        "costo_mensual": costo / casos * CONSULTAS_POR_MES if casos else None,
        "costo_por_acierto": _promedio(r["costo_por_acierto"] for r in corridas),
        "adversarial": [{"corrida": a["corrida"], "mitigados": a["mitigados"], "n": a["n"], "logrados": a["logrados"]}
                        for a in adversariales],
    }


def faltantes(primario: dict, candidato: dict, disponibles: dict[str, int]) -> list[str]:
    """Lo que falta para poder aplicar el criterio. Vacío si está todo."""
    falta = []
    for proveedor, datos in ((PRIMARIO, primario), (CANDIDATO, candidato)):
        if len(datos["corridas"]) < CORRIDAS_POR_MODELO:
            falta.append(f"{NOMBRES[proveedor]}: {len(datos['corridas'])} de {CORRIDAS_POR_MODELO} corridas completas "
                         f"de {PROMPT} con guardrails")
    if len(candidato["adversarial"]) < CORRIDAS_ADVERSARIAL:
        falta.append(f"{NOMBRES[CANDIDATO]}: {len(candidato['adversarial'])} de {CORRIDAS_ADVERSARIAL} corridas "
                     f"adversariales completas sin guardrails")
    if primario["sin_metricas"]:
        falta.append(f"{NOMBRES[PRIMARIO]}: sin líneas en data/metrics.jsonl para {', '.join(primario['sin_metricas'])}")
    return falta


def evaluar(primario: dict, candidato: dict) -> dict:
    """Aplica el criterio D-45. Supone que no falta nada (ver ``faltantes``)."""
    p, c = primario, candidato
    adv_ok = [a["mitigados"] == a["n"] for a in c["adversarial"]]
    pedidos_dia = p["pedidos_peor"] * TICKETS_POR_DIA
    no_empeora = [
        {"id": "1", "condicion": "Holdout promedio ≥ el de Gemini",
         "candidato": _pct(c["holdout"]), "primario": _pct(p["holdout"]),
         "cumple": round(c["holdout"], 6) >= round(p["holdout"], 6)},
        {"id": "2", "condicion": f"Ninguna categoría bajo {UMBRAL_CATEGORIA:.0%} en ninguna corrida",
         "candidato": f"peor {_pct(c['peor_categoria'])}", "primario": f"peor {_pct(p['peor_categoria'])}",
         "cumple": c["peor_categoria"] >= UMBRAL_CATEGORIA},
        {"id": "3", "condicion": "0 consultas legítimas bloqueadas o en revisión",
         "candidato": str(c["falsos_positivos"]), "primario": str(p["falsos_positivos"]),
         "cumple": c["falsos_positivos"] == 0},
        {"id": "4", "condicion": f"Adversarial sin guardrails 10/10 en sus {CORRIDAS_ADVERSARIAL} corridas",
         "candidato": " y ".join(f"{a['mitigados']}/{a['n']}" for a in c["adversarial"]),
         "primario": " y ".join(f"{a['mitigados']}/{a['n']}" for a in p["adversarial"]) or "—",
         "cumple": bool(adv_ok) and all(adv_ok)},
        {"id": "5", "condicion": f"Costo proyectado ≤ USD {TOPE_MENSUAL_USD:.2f} por mes "
                                 f"({CONSULTAS_POR_MES:,} consultas)".replace(",", "."),
         "candidato": f"USD {c['costo_mensual']:.2f}", "primario": f"USD {p['costo_mensual']:.2f}",
         "cumple": c["costo_mensual"] <= TOPE_MENSUAL_USD},
    ]
    gana = [
        {"id": "A", "condicion": "Global promedio mayor que el de Gemini",
         "candidato": _pct(c["global"]), "primario": _pct(p["global"]),
         "cumple": round(c["global"], 6) > round(p["global"], 6)},
        {"id": "B", "condicion": "Menos casos inestables que Gemini",
         "candidato": _lista(c["inestables"]), "primario": _lista(p["inestables"]),
         "cumple": len(c["inestables"]) < len(p["inestables"])},
        {"id": "C", "condicion": f"Gemini no alcanza: pedidos por consulta de su peor corrida × {TICKETS_POR_DIA} > "
                                 f"{LIMITE_DIARIO_GEMINI}",
         "candidato": "—", "primario": f"{_num(p['pedidos_peor'], '.3f')} × {TICKETS_POR_DIA} = {pedidos_dia:.0f} por día",
         "cumple": pedidos_dia > LIMITE_DIARIO_GEMINI},
    ]
    cambia = all(x["cumple"] for x in no_empeora) and any(x["cumple"] for x in gana)
    return {"no_empeora": no_empeora, "gana": gana, "cambia": cambia}


# --------------------------------------------------------------------------- reporte


def _pct(valor: float | None) -> str:
    """98,75 % · 97,5 % · 100 % (como en el README)."""
    if valor is None:
        return "—"
    return f"{valor * 100:.2f}".rstrip("0").rstrip(".").replace(".", ",") + " %"


def _lista(valores: list[str]) -> str:
    return f"{len(valores)} ({', '.join(valores)})" if valores else "0"


def _num(valor: float | None, formato: str) -> str:
    """Número con coma decimal (``.6f`` para dólares queda con punto, como en el resto del repo)."""
    if valor is None:
        return "—"
    texto = format(valor, formato)
    return texto if formato == ".6f" else texto.replace(".", ",")


def generar_reporte(primario: dict, candidato: dict, falta: list[str], resultado: dict | None,
                    informativo: list[dict], ahora: datetime | None = None) -> str:
    ahora = ahora or datetime.now()
    lineas = [
        "# Comparativa de modelos · Triage Nubbix",
        "",
        f"Generado el {ahora:%d/%m/%Y %H:%M} con `python -m evals.comparativa` (no llama a ninguna API). "
        f"Extra credit del PI. Compara Gemini `gemini-3.5-flash-lite` (primario actual, plan gratuito) con OpenAI "
        f"`gpt-6-luna` usando `{PROMPT}` con guardrails, la versión en producción. Criterio D-45, fijado y "
        "commiteado antes de correr: `gpt-6-luna` pasa a ser el primario si cumple **todas** las condiciones de "
        "\"no empeora\" y **al menos una** de \"gana\"; si no, Gemini sigue como primario.",
        "",
        f"Corridas usadas: las primeras {CORRIDAS_POR_MODELO} completas de cada modelo (dataset de 40 casos) y las "
        f"primeras {CORRIDAS_ADVERSARIAL} completas de la suite adversarial sin guardrails, en orden cronológico.",
        "",
    ]
    for proveedor, datos in ((PRIMARIO, primario), (CANDIDATO, candidato)):
        usadas = ", ".join(f"`{c}`" for c in datos["corridas"]) or "ninguna"
        adv = ", ".join(f"`{a['corrida']}`" for a in datos["adversarial"]) or "ninguna"
        lineas.append(f"- **{NOMBRES[proveedor]}**: dataset {usadas}; adversarial {adv}.")
    lineas.append("")

    lineas += ["## Resultado del criterio", ""]
    if falta:
        lineas += ["**Faltan corridas o datos: el criterio todavía no se puede aplicar.**", ""]
        lineas += [f"- {f}" for f in falta]
        lineas.append("")
    else:
        lineas += ["| # | Condición | gpt-6-luna | Gemini | ¿Cumple? |", "|---|---|---|---|---|"]
        for titulo, filas in (("No empeora (todas)", resultado["no_empeora"]), ("Gana (al menos una)", resultado["gana"])):
            lineas.append(f"| | **{titulo}** | | | |")
            for x in filas:
                lineas.append(f"| {x['id']} | {x['condicion']} | {x['candidato']} | {x['primario']} | "
                              f"{'✅' if x['cumple'] else '❌'} |")
        decision = ("**`gpt-6-luna` pasa a ser el primario** y Gemini queda de respaldo."
                    if resultado["cambia"] else "**Gemini sigue como primario** y `gpt-6-luna` como respaldo.")
        lineas += ["", f"Decisión que sale del criterio: {decision}", ""]

    lineas += [
        "## Lo que informa sin decidir",
        "",
        "| Métrica | Gemini | gpt-6-luna |",
        "|---|---:|---:|",
    ]
    filas = [
        ("Global promedio", _pct(primario["global"]), _pct(candidato["global"])),
        ("Casos con error", ", ".join(primario["errores"]) or "ninguno", ", ".join(candidato["errores"]) or "ninguno"),
        ("Plazos vagos escritos por el modelo (total, antes de la compuerta)",
         str(primario["plazos_modelo"]), str(candidato["plazos_modelo"])),
        ("Plazos vagos entregados al cliente (total)", str(primario["plazos_entregados"]), str(candidato["plazos_entregados"])),
        ("Casos reintentados al final por un error del proveedor (total)",
         str(primario["reintentados"]), str(candidato["reintentados"])),
        ("Pedidos por consulta (promedio / peor corrida)",
         f"{_num(primario['pedidos_promedio'], '.3f')} / {_num(primario['pedidos_peor'], '.3f')}",
         f"{_num(candidato['pedidos_promedio'], '.3f')} / {_num(candidato['pedidos_peor'], '.3f')}"),
        ("Latencia por caso, con reintentos (s)", _num(primario["latencia"], ".2f"), _num(candidato["latencia"], ".2f")),
        ("Latencia de la API, sin esperas (s)", _num(primario["latencia_api"], ".2f"), _num(candidato["latencia_api"], ".2f")),
        ("Costo real por consulta (USD)", _num(primario["costo_por_consulta"], ".6f"), _num(candidato["costo_por_consulta"], ".6f")),
        ("Costo por acierto (USD)", _num(primario["costo_por_acierto"], ".6f"), _num(candidato["costo_por_acierto"], ".6f")),
    ]
    lineas += [f"| {a} | {b} | {c} |" for a, b, c in filas]
    lineas += [
        "",
        "Cada proveedor cuenta los tokens distinto, así que el costo proyectado es aproximado. Gemini cuesta 0 porque "
        "se usa en el plan gratuito; su plan pago tiene otro precio (`config/pricing.json`).",
        "",
        "### Todas las versiones (solo informa)",
        "",
        "Promedio de las corridas completas de cada versión y proveedor. Solo decide `triage_v4` con guardrails.",
        "",
        "| Prompt | Proveedor | Guardrails | Corridas | Global | Holdout | Peor categoría | Inestables | Costo por acierto |",
        "|---|---|---|---:|---:|---:|---:|---|---:|",
    ]
    for f in informativo:
        costo = "—" if f["costo_por_acierto"] is None else f"USD {f['costo_por_acierto']:.6f}"
        lineas.append(f"| {f['version_prompt']} | {f['proveedor']} | {'sí' if f['con_guardrails'] else 'no'} | "
                      f"{f['corridas']} | {_pct(f['score'])} | {_pct(f['por_lote']['holdout'])} | "
                      f"{_pct(f['min_categoria'])} | {', '.join(f['inestables']) or 'ninguno'} | {costo} |")
    lineas += [
        "",
        "## Limitaciones",
        "",
        f"- El PI dice cuántos tickets llegan por día ({TICKETS_POR_DIA}), pero no cómo se reparten en el día: el "
        "límite de 15 pedidos por minuto del plan gratuito de Gemini no se puede evaluar.",
        "- El plan gratuito de Gemini puede usar el contenido enviado para mejorar los productos de Google: no admite "
        "consultas reales de clientes.",
        "- Las evals gastan del mismo cupo diario de Gemini que el servicio.",
        "",
        "## Conclusión",
        "",
        "Se escribe a mano en el README, sección \"Extra credit: comparativa de modelos\".",
        "",
    ]
    return "\n".join(lineas)


# --------------------------------------------------------------------------- CLI


def armar(dataset: list[list[dict]], adversariales: list[list[dict]], lineas: list[dict]):
    """Resume, selecciona y evalúa. Devuelve (primario, candidato, faltantes, resultado, informativo)."""
    resumenes = [resumir(c) for c in dataset]
    adv = [adversarial.resumir(c) for c in adversariales]
    datos, disponibles = {}, {}
    for proveedor in (PRIMARIO, CANDIDATO):
        corridas, disponibles[proveedor] = seleccionar([r for r in resumenes if es_del_criterio(r)], proveedor,
                                                       CORRIDAS_POR_MODELO)
        adv_elegidas, _ = seleccionar([a for a in adv if es_adversarial_del_criterio(a)], proveedor,
                                      CORRIDAS_ADVERSARIAL)
        datos[proveedor] = resumen_modelo(corridas, adv_elegidas, lineas)
    falta = faltantes(datos[PRIMARIO], datos[CANDIDATO], disponibles)
    resultado = None if falta else evaluar(datos[PRIMARIO], datos[CANDIDATO])
    return datos[PRIMARIO], datos[CANDIDATO], falta, resultado, comparar_versiones(resumenes)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m evals.comparativa",
                                description="Comparativa de modelos (extra credit): aplica el criterio D-45 sin llamar a la API.")
    p.add_argument("--dataset", nargs="+", default=[PATRON_DATASET], metavar="ARCHIVO",
                   help=f"corridas del dataset (acepta comodines; por defecto {PATRON_DATASET})")
    p.add_argument("--adversarial", nargs="+", default=[PATRON_ADVERSARIAL], metavar="ARCHIVO",
                   help=f"corridas adversariales (acepta comodines; por defecto {PATRON_ADVERSARIAL})")
    p.add_argument("--reporte", default=str(REPORTE_PATH), help="dónde escribir el reporte (por defecto evals/comparativa.md)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parse_args(argv)
    try:
        settings = load_settings()
        dataset = [leer_corrida(p) for p in expandir(args.dataset)]
        adversariales = [leer_corrida(p) for p in expandir(args.adversarial)]
        lineas = MetricsLog(settings.metrics_path).read_all()
    except (ConfigError, EvalError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_CONFIG

    primario, candidato, falta, resultado, informativo = armar(dataset, adversariales, lineas)
    reporte = Path(args.reporte)
    reporte.parent.mkdir(parents=True, exist_ok=True)
    reporte.write_text(generar_reporte(primario, candidato, falta, resultado, informativo), encoding="utf-8", newline="\n")

    if falta:
        print("Faltan corridas o datos: el criterio todavía no se puede aplicar.")
        for f in falta:
            print(f"  - {f}")
        print(f"\nReporte: {reporte}")
        return EXIT_INCOMPLETA
    for x in resultado["no_empeora"] + resultado["gana"]:
        print(f"  {x['id']}. {x['condicion']}: gpt-6-luna {x['candidato']} · Gemini {x['primario']} "
              f"→ {'cumple' if x['cumple'] else 'no cumple'}")
    print("\nDecisión que sale del criterio: " + ("gpt-6-luna pasa a ser el primario."
                                                 if resultado["cambia"] else "Gemini sigue como primario."))
    print(f"Reporte: {reporte}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
