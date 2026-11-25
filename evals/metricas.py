"""Métricas de una corrida de evals (M1L5): exact match, umbrales, plazos vagos y costo por acierto.

Todo se calcula a partir de los registros guardados de la corrida: no llama a ninguna API, así que el
reporte se puede regenerar cuantas veces haga falta.
"""

from __future__ import annotations

from src.contract import CATEGORIES
from src.vague_timing import find_vague_timing

# Umbrales fijados ANTES de correr nada (M1L5 · Umbrales y regresiones). No se ajustan para que pase una versión.
UMBRAL_CATEGORIA = 0.70      # score mínimo por categoría
MAX_PLAZOS_VAGOS = 0         # respuestas con plazos vagos permitidas: una sola ya es regresión (decisión del alumno)

LOTES = ("dev", "holdout")   # dev para diseñar, holdout para decidir (M1L2)
MODELO_REF = "gpt-6-luna"    # con sus precios se proyecta el costo de las corridas de Gemini (que cuestan 0)

# Estado de cada caso en el registro de la corrida.
OK = "ok"                            # el modelo devolvió un contrato válido
CONTRATO_INVALIDO = "contrato_invalido"  # respondió, pero ningún intento cumplió el contrato: cuenta como error
ERROR_API = "error_api"              # el proveedor no respondió (por ejemplo, "high demand"): corrida incompleta


def exact_match(obtenida: str | None, esperada: str) -> bool:
    """Igual que en la M1L5: sin categoría (respuesta inválida) es un error; si no, se compara el texto."""
    if obtenida is None:
        return False
    return obtenida.strip().lower() == esperada.strip().lower()


def costo_por_acierto(costo_total: float, aciertos: int) -> float | None:
    """Costo total ÷ aciertos (M1L5). ``None`` si no hubo aciertos (el costo por acierto sería infinito)."""
    return costo_total / aciertos if aciertos else None


def resumir(registros: list[dict], precio_ref: dict[str, float] | None = None) -> dict:
    """Resume una corrida: qué se corrió, scores, umbrales, plazos vagos, costo y latencia.

    :param precio_ref: precio por 1M de tokens (``{"input", "output"}``) de ``MODELO_REF``, para proyectar
        cuánto costaría la corrida con ese modelo. Sin él, la proyección queda en ``None``.
    """
    if not registros:
        raise ValueError("La corrida no tiene registros")
    primero = registros[0]
    n = len(registros)
    aciertos = sum(1 for r in registros if exact_match(r.get("categoria_obtenida"), r["categoria_esperada"]))

    # Score por categoría (la esperada). Una categoría sin casos tampoco pasa: no hay evidencia de que funcione.
    por_categoria = {}
    for cat in CATEGORIES:
        casos = [r for r in registros if r["categoria_esperada"] == cat]
        ok = sum(1 for r in casos if exact_match(r.get("categoria_obtenida"), cat))
        score = ok / len(casos) if casos else 0.0
        por_categoria[cat] = {"n": len(casos), "aciertos": ok, "score": score, "bajo_umbral": score < UMBRAL_CATEGORIA}

    # Score por lote: dev para diseñar, holdout para decidir.
    por_lote = {}
    for lote in LOTES:
        casos = [r for r in registros if r.get("lote") == lote]
        ok = sum(1 for r in casos if exact_match(r.get("categoria_obtenida"), r["categoria_esperada"]))
        por_lote[lote] = {"n": len(casos), "aciertos": ok, "score": ok / len(casos) if casos else None}

    # Plazos vagos: se buscan en la respuesta para el cliente, aunque la categoría sea correcta.
    plazos = []
    for r in registros:
        frases = find_vague_timing(r.get("answer"))
        if frases:
            plazos.append({"caso_id": r["caso_id"], "categoria": r["categoria_esperada"], "frases": frases})
    plazos_por_categoria = {cat: sum(1 for p in plazos if p["categoria"] == cat) for cat in CATEGORIES}

    regresiones = [f"{cat} {d['score']:.0%} < {UMBRAL_CATEGORIA:.0%}" for cat, d in por_categoria.items() if d["bajo_umbral"]]
    if len(plazos) > MAX_PLAZOS_VAGOS:
        regresiones.append(f"plazos vagos en {len(plazos)} respuesta{'s' if len(plazos) != 1 else ''} (máximo {MAX_PLAZOS_VAGOS})")

    errores_api = [r["caso_id"] for r in registros if r.get("estado") == ERROR_API]
    costo_total = sum(float(r.get("costo_usd") or 0.0) for r in registros)
    respondidos = [r for r in registros if r.get("estado") != ERROR_API]
    input_tokens = sum(int(r.get("input_tokens") or 0) for r in registros)
    output_tokens = sum(int(r.get("output_tokens") or 0) for r in registros)
    costo_proyectado = (input_tokens / 1_000_000 * precio_ref["input"] + output_tokens / 1_000_000 * precio_ref["output"]
                        if precio_ref else None)
    return {
        "corrida": primero["corrida"],
        "proveedor": primero["proveedor"],
        "modelo": primero["modelo"],
        "version_prompt": primero["version_prompt"],
        "n": n,
        "aciertos": aciertos,
        "score": aciertos / n,
        "por_categoria": por_categoria,
        "por_lote": por_lote,
        "plazos_vagos": plazos,
        "plazos_por_categoria": plazos_por_categoria,
        "regresiones": regresiones,
        "completa": not errores_api,
        "errores_api": errores_api,
        "contrato_invalido": [r["caso_id"] for r in registros if r.get("estado") == CONTRATO_INVALIDO],
        "reintentados": [r["caso_id"] for r in registros if r.get("reintentado_al_final")],
        "errores": [
            {"caso_id": r["caso_id"], "esperada": r["categoria_esperada"], "obtenida": r.get("categoria_obtenida")}
            for r in registros if not exact_match(r.get("categoria_obtenida"), r["categoria_esperada"])
        ],
        "costo_total": costo_total,
        "costo_por_acierto": costo_por_acierto(costo_total, aciertos),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "costo_proyectado": costo_proyectado,
        "costo_por_acierto_proyectado": (costo_por_acierto(costo_proyectado, aciertos)
                                         if costo_proyectado is not None else None),
        "obtenida_por_caso": {r["caso_id"]: r.get("categoria_obtenida") for r in registros},
        "latencia_promedio": (sum(float(r.get("latencia_s") or 0.0) for r in respondidos) / len(respondidos)
                              if respondidos else 0.0),
    }


def comparar_versiones(resumenes: list[dict]) -> list[dict]:
    """Agrupa las corridas **completas** por (prompt, proveedor) y promedia sus scores.

    Un caso es **inestable** si la categoría obtenida cambia entre corridas de la misma versión y proveedor:
    si un caso mejora en una corrida y no en la otra, eso es azar, no una mejora del prompt.
    """
    grupos: dict[tuple[str, str], list[dict]] = {}
    for r in resumenes:
        if r["completa"]:
            grupos.setdefault((r["version_prompt"], r["proveedor"]), []).append(r)

    def promedio(valores):
        valores = [v for v in valores if v is not None]
        return sum(valores) / len(valores) if valores else None

    filas = []
    for (version, proveedor), rs in grupos.items():
        casos = sorted(set().union(*(r["obtenida_por_caso"] for r in rs)))
        inestables = [c for c in casos if len({r["obtenida_por_caso"].get(c) for r in rs}) > 1]
        filas.append({
            "version_prompt": version,
            "proveedor": proveedor,
            "modelo": rs[0]["modelo"],
            "corridas": len(rs),
            "score": promedio(r["score"] for r in rs),
            "por_lote": {lote: promedio(r["por_lote"][lote]["score"] for r in rs) for lote in LOTES},
            "min_categoria": min(d["score"] for r in rs for d in r["por_categoria"].values()),
            "plazos_vagos": sum(len(r["plazos_vagos"]) for r in rs),
            "errores": sorted({e["caso_id"] for r in rs for e in r["errores"]}),
            "inestables": inestables,
            "costo_por_acierto": promedio(r["costo_por_acierto"] for r in rs),
            "costo_por_acierto_proyectado": promedio(r["costo_por_acierto_proyectado"] for r in rs),
        })
    return sorted(filas, key=lambda f: (f["proveedor"], f["version_prompt"]))
