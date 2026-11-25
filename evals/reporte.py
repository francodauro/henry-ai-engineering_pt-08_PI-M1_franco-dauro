"""Reporte markdown de una o varias corridas (M1L5 · Reportes).

Responde, sin correr nada, las tres preguntas de la lección:
1. ¿Qué se evaluó? (dataset, n, proveedor, modelo, prompt)
2. ¿Alguna categoría quedó bajo el umbral? (con números; acá también los plazos vagos)
3. ¿El score y el costo por acierto cuentan la misma historia?

La conclusión (qué versión o modelo queda y por qué) no se genera: se escribe a mano en el README.
"""

from __future__ import annotations

from datetime import datetime

from src.contract import CATEGORIES

from .metricas import LOTES, MAX_PLAZOS_VAGOS, MODELO_REF, UMBRAL_CATEGORIA, comparar_versiones


def _usd(valor: float | None) -> str:
    return "—" if valor is None else f"USD {valor:.6f}"


def _pct(valor: float | None) -> str:
    return "—" if valor is None else f"{valor:.0%}"


def _estado(r: dict) -> str:
    if not r["completa"]:
        return "Incompleta (no se compara)"
    return "Regresión: " + "; ".join(r["regresiones"]) if r["regresiones"] else "OK"


def _pregunta_3(completas: list[dict]) -> str:
    """Compara score y costo por acierto entre las corridas completas."""
    if not completas:
        return "No hay corridas completas: no se puede comparar."
    if len(completas) == 1:
        r = completas[0]
        return (f"Hay una sola corrida completa ({r['corrida']}): score {r['score']:.0%} y costo por acierto "
                f"{_usd(r['costo_por_acierto'])}. Para saber si cuentan la misma historia hace falta otra corrida.")
    mejor_score = max(r["score"] for r in completas)
    con_aciertos = [r for r in completas if r["costo_por_acierto"] is not None]
    mejor_costo = min((r["costo_por_acierto"] for r in con_aciertos), default=None)
    gana_score = [r["corrida"] for r in completas if r["score"] == mejor_score]
    gana_costo = [r["corrida"] for r in con_aciertos if r["costo_por_acierto"] == mejor_costo]
    texto = (f"Mejor score ({mejor_score:.0%}): {', '.join(gana_score)}. "
             f"Mejor costo por acierto ({_usd(mejor_costo)}): {', '.join(gana_costo) or '—'}. ")
    if set(gana_score) & set(gana_costo):
        texto += "**Cuentan la misma historia**: al menos una corrida es la mejor en las dos."
    else:
        texto += "**No cuentan la misma historia**: hay que decidir mirando los dos números juntos."
    con_regresion = [r["corrida"] for r in completas if r["regresiones"] and r["corrida"] in set(gana_score) | set(gana_costo)]
    if con_regresion:
        texto += f" Ojo: {', '.join(con_regresion)} tiene regresiones (sección 2), aunque gane en score o en costo."
    return texto


def generar_reporte(resumenes: list[dict], dataset: dict, costos_metrics: dict[str, float | None],
                    ahora: datetime | None = None) -> str:
    """Arma el markdown.

    :param dataset: ``{"ruta", "n", "por_categoria"}`` del dataset usado.
    :param costos_metrics: costo de cada corrida sumado desde ``data/metrics.jsonl`` (``None`` si no hay líneas),
        para comprobar que el costo de la corrida es auditable.
    """
    ahora = ahora or datetime.now()
    cats = list(CATEGORIES)
    reparto = ", ".join(f"{c} {dataset['por_categoria'].get(c, 0)}" for c in cats)
    lineas = [
        "# Reporte de evaluación · Triage Nubbix",
        "",
        f"Generado el {ahora:%d/%m/%Y %H:%M} con `python -m evals.runner`. "
        f"Umbral por categoría: {UMBRAL_CATEGORIA:.0%}. Plazos vagos permitidos: {MAX_PLAZOS_VAGOS}.",
        "",
        "## 1. Qué se evaluó",
        "",
        f"Dataset `{dataset['ruta']}`: {dataset['n']} casos ({reparto}). Métrica: exact match de la categoría.",
        "",
        "| Corrida | Proveedor | Modelo | Prompt | Casos | Completa |",
        "|---|---|---|---|---:|---|",
    ]
    for r in resumenes:
        detalle = "sí" if r["completa"] else f"no (sin respuesta: {', '.join(r['errores_api'])})"
        lineas.append(f"| `{r['corrida']}` | {r['proveedor']} | {r['modelo']} | {r['version_prompt']} | {r['n']} | {detalle} |")

    lineas += [
        "",
        "## 2. ¿Alguna categoría quedó bajo el umbral?",
        "",
        "| Corrida | Global | " + " | ".join(cats) + " | " + " | ".join(LOTES) + " | Plazos vagos | Estado |",
        "|---|---:|" + "---:|" * (len(cats) + len(LOTES)) + "---:|---|",
    ]
    for r in resumenes:
        celdas = []
        for c in cats:
            d = r["por_categoria"][c]
            marca = " ⚠" if d["bajo_umbral"] else ""
            celdas.append(f"{d['score']:.0%} ({d['aciertos']}/{d['n']}){marca}")
        lotes = [f"{_pct(r['por_lote'][l]['score'])} ({r['por_lote'][l]['aciertos']}/{r['por_lote'][l]['n']})" for l in LOTES]
        lineas.append(f"| `{r['corrida']}` | {r['score']:.0%} ({r['aciertos']}/{r['n']}) | " + " | ".join(celdas + lotes)
                      + f" | {len(r['plazos_vagos'])} | {_estado(r)} |")

    lineas += [
        "",
        "## 3. ¿El score y el costo por acierto cuentan la misma historia?",
        "",
        f"| Corrida | Aciertos | Tokens entrada / salida | Costo total | Costo en `metrics.jsonl` | Costo por acierto "
        f"| Costo por acierto proyectado con {MODELO_REF} | Latencia promedio por caso (con reintentos) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in resumenes:
        en_metrics = costos_metrics.get(r["corrida"])
        if en_metrics is None:
            control = "sin líneas"
        else:
            control = _usd(en_metrics) + (" ✓" if abs(en_metrics - r["costo_total"]) < 1e-9 else " ✗ no coincide")
        lineas.append(f"| `{r['corrida']}` | {r['aciertos']}/{r['n']} | {r['input_tokens']} / {r['output_tokens']} | "
                      f"{_usd(r['costo_total'])} | {control} | {_usd(r['costo_por_acierto'])} | "
                      f"{_usd(r.get('costo_por_acierto_proyectado'))} | {r['latencia_promedio']:.2f} s |")
    lineas += ["", _pregunta_3([r for r in resumenes if r["completa"]])]

    filas = comparar_versiones(resumenes)
    lineas += [
        "",
        "## 4. Comparación por versión y proveedor",
        "",
        "Promedio de las corridas completas de cada versión con cada proveedor. Un caso es **inestable** si su "
        "categoría cambia entre corridas de la misma versión: ahí una diferencia puede ser azar.",
        "",
        "| Prompt | Proveedor | Corridas | Global | " + " | ".join(LOTES) + " | Peor categoría | Plazos vagos (total) "
        f"| Casos con error | Inestables | Costo por acierto | Proyectado con {MODELO_REF} |",
        "|---|---|---:|---:|" + "---:|" * len(LOTES) + "---:|---:|---|---|---:|---:|",
    ]
    for f in filas:
        lineas.append(
            f"| {f['version_prompt']} | {f['proveedor']} | {f['corridas']} | {_pct(f['score'])} | "
            + " | ".join(_pct(f["por_lote"][l]) for l in LOTES)
            + f" | {_pct(f['min_categoria'])} | {f['plazos_vagos']} | {', '.join(f['errores']) or 'ninguno'} | "
            f"{', '.join(f['inestables']) or 'ninguno'} | {_usd(f['costo_por_acierto'])} | {_usd(f['costo_por_acierto_proyectado'])} |")
    if not filas:
        lineas.append("| — | — | 0 | — |" + " — |" * len(LOTES) + " — | — | — | — | — | — |")

    lineas += ["", "## Detalle de errores", ""]
    for r in resumenes:
        lineas.append(f"**`{r['corrida']}`**")
        lineas.append("")
        if r["errores"]:
            for e in r["errores"]:
                obtenida = e["obtenida"] or "sin respuesta válida"
                lineas.append(f"- Categoría: {e['caso_id']} esperaba `{e['esperada']}`, obtuvo `{obtenida}`")
        else:
            lineas.append("- Categoría: ningún error.")
        if r["plazos_vagos"]:
            for p in r["plazos_vagos"]:
                lineas.append(f"- Plazo vago: {p['caso_id']} ({p['categoria']}): " + ", ".join(f"\"{f}\"" for f in p["frases"]))
        else:
            lineas.append("- Plazos vagos: ninguno.")
        if r["contrato_invalido"]:
            lineas.append(f"- Sin contrato válido después de todos los intentos: {', '.join(r['contrato_invalido'])}")
        if r["reintentados"]:
            lineas.append(f"- Reintentados al final por un error del proveedor: {', '.join(r['reintentados'])}")
        lineas.append("")

    lineas += [
        "## Conclusión",
        "",
        "Se escribe a mano en el README: qué queda vigente y por qué, citando el score por categoría, "
        "los plazos vagos y el costo por acierto.",
        "",
    ]
    return "\n".join(lineas)
