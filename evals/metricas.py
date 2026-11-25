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


def resumir(registros: list[dict]) -> dict:
    """Resume una corrida: qué se corrió, scores, umbrales, plazos vagos, costo y latencia."""
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
    return {
        "corrida": primero["corrida"],
        "proveedor": primero["proveedor"],
        "modelo": primero["modelo"],
        "version_prompt": primero["version_prompt"],
        "n": n,
        "aciertos": aciertos,
        "score": aciertos / n,
        "por_categoria": por_categoria,
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
        "input_tokens": sum(int(r.get("input_tokens") or 0) for r in registros),
        "output_tokens": sum(int(r.get("output_tokens") or 0) for r in registros),
        "latencia_promedio": (sum(float(r.get("latencia_s") or 0.0) for r in respondidos) / len(respondidos)
                              if respondidos else 0.0),
    }
