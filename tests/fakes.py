"""Proveedores falsos para los tests: responden o fallan según un guion, sin llamar a ninguna API."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from src.llm.base import LLMProvider, LLMResponse


class FakeProvider(LLMProvider):
    """Devuelve, en orden, los elementos de ``script``: un ``Exception`` se lanza, un texto se responde
    y un dict se entrega como argumentos de la tool call (como si el modelo llenara el formulario)."""

    def __init__(self, name: str, model: str, script: list, prompt_tokens: int = 100, completion_tokens: int = 20):
        super().__init__(model, max_tokens=100, temperature=0.0, timeout_s=5)
        self.name = name
        self.script = list(script)
        self.calls = 0
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.systems: list[str | None] = []  # el system de cada llamada, para revisar los reintentos

    def complete(self, prompt: str, system: str | None = None, tool=None) -> LLMResponse:
        self.calls += 1
        self.systems.append(system)
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        tool_args = step if isinstance(step, dict) else None
        tool_error = "sin_tool_call" if tool is not None and tool_args is None else None
        return LLMResponse(
            provider=self.name,
            model=self.model,
            text=json.dumps(step) if tool_args is not None else step,
            tool_args=tool_args,
            tool_error=tool_error,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            total_tokens=self.prompt_tokens + self.completion_tokens,
            latency_s=0.5,
        )


def write_pricing(folder: Path) -> Path:
    """Tabla de precios de prueba: un modelo gratuito y uno pago con los precios de gpt-6-luna."""
    path = folder / "pricing.json"
    path.write_text(json.dumps({"models": {
        "free-model": {"input": 0.0, "output": 0.0},
        "paid-model": {"input": 0.10, "output": 0.50},
    }}), encoding="utf-8")
    return path


VALID = {"answer": "Revisaremos el cobro duplicado.", "confidence": 0.95, "category": "billing", "actions": ["review_charge"]}


def temp_dir() -> tempfile.TemporaryDirectory:
    return tempfile.TemporaryDirectory()
