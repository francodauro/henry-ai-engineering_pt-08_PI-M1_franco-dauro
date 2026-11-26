"""Registro de métricas en ``data/metrics.jsonl``: una línea JSON por llamada, solo se agrega (append-only).

Cada línea responde preguntas de costo (``cost_usd``), latencia (``latency_s``) y consumo (tokens).
Por privacidad no se guarda el texto de la consulta ni de la respuesta.
``cost_usd`` se guarda como número: un número chico puede verse como ``1.8e-05``, que es JSON válido
y se suma bien. Los 6 decimales son solo para mostrarlo en pantalla.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class MetricsLog:
    def __init__(self, path: Path):
        self.path = path

    def append(self, record: dict[str, Any]) -> dict[str, Any]:
        """Agrega una línea con el timestamp UTC (ISO 8601) al principio y la devuelve."""
        line = {"timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"), **record}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # newline="\n": en Windows, Python escribiría "\r\n" (CRLF); así el archivo queda igual en todos los sistemas.
        with open(self.path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
        return line

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with open(self.path, encoding="utf-8") as f:
            return [json.loads(raw) for raw in f if raw.strip()]

    def total_cost(self) -> float:
        """Gasto acumulado en USD de todas las llamadas registradas (las gratuitas suman 0)."""
        return sum(float(r.get("cost_usd") or 0.0) for r in self.read_all())
