import unittest
from pathlib import Path

from src.costs import Pricing
from src.llm.base import AllProvidersFailedError, AuthError, RateLimitError, ServerError
from src.llm.router import Router
from src.metrics import MetricsLog
from tests.fakes import FakeProvider, temp_dir, write_pricing


class TestRouter(unittest.TestCase):
    def setUp(self):
        self.tmp = temp_dir()
        folder = Path(self.tmp.name)
        self.pricing = Pricing(write_pricing(folder))
        self.metrics = MetricsLog(folder / "metrics.jsonl")
        self.failures = []

    def tearDown(self):
        self.tmp.cleanup()

    def router(self, *providers, budget=4.5):
        return Router(
            list(providers), self.pricing, self.metrics,
            budget_usd=budget, max_retries=2, max_wait_s=10,
            sleep=lambda s: None, on_failure=lambda name, exc: self.failures.append(name),
        )

    def test_responde_el_primario(self):
        primary = FakeProvider("gemini", "free-model", ["hola"])
        backup = FakeProvider("openai", "paid-model", ["no debería"])
        response = self.router(primary, backup).ask("consulta")
        self.assertEqual((response.provider, response.text, response.cost_usd), ("gemini", "hola", 0.0))
        self.assertEqual(backup.calls, 0)
        [line] = self.metrics.read_all()
        self.assertEqual(line["status"], "ok")
        self.assertFalse(line["fallback"])
        for field in ("timestamp", "prompt_tokens", "completion_tokens", "total_tokens", "latency_s", "cost_usd"):
            self.assertIn(field, line)

    def test_reintenta_y_despues_responde(self):
        primary = FakeProvider("gemini", "free-model", [ServerError("gemini", "503"), "hola"])
        response = self.router(primary).ask("consulta")
        self.assertEqual(response.text, "hola")
        self.assertEqual(self.metrics.read_all()[0]["attempts"], 2)

    def test_fallback_al_respaldo_y_costo(self):
        primary = FakeProvider("gemini", "free-model", [AuthError("gemini", "clave inválida")])
        backup = FakeProvider("openai", "paid-model", ["respuesta"], prompt_tokens=1000, completion_tokens=200)
        response = self.router(primary, backup).ask("consulta")
        self.assertEqual(response.provider, "openai")
        self.assertAlmostEqual(response.cost_usd, 0.0002)
        self.assertEqual(self.failures, ["gemini"])
        error_line, ok_line = self.metrics.read_all()
        self.assertEqual((error_line["status"], error_line["error_kind"]), ("error", "auth_error"))
        self.assertTrue(ok_line["fallback"])
        self.assertAlmostEqual(ok_line["cost_usd"], 0.0002)

    def test_retry_after_largo_pasa_directo_al_respaldo(self):
        primary = FakeProvider("gemini", "free-model", [RateLimitError("gemini", "429", retry_after=60)])
        backup = FakeProvider("openai", "paid-model", ["respuesta"])
        self.assertEqual(self.router(primary, backup).ask("consulta").provider, "openai")
        self.assertEqual(primary.calls, 1)

    def test_tope_de_gasto_no_llama_al_pago(self):
        self.metrics.append({"cost_usd": 4.6})
        primary = FakeProvider("gemini", "free-model", [AuthError("gemini", "x")])
        backup = FakeProvider("openai", "paid-model", ["no debería"])
        with self.assertRaises(AllProvidersFailedError):
            self.router(primary, backup, budget=4.5).ask("consulta")
        self.assertEqual(backup.calls, 0)
        self.assertEqual(self.metrics.read_all()[-1]["error_kind"], "budget_exceeded")

    def test_fallan_todos(self):
        primary = FakeProvider("gemini", "free-model", [AuthError("gemini", "x")])
        backup = FakeProvider("openai", "paid-model", [AuthError("openai", "y")])
        with self.assertRaises(AllProvidersFailedError) as ctx:
            self.router(primary, backup).ask("consulta")
        self.assertEqual(len(ctx.exception.errors), 2)

    def test_metricas_sin_texto_de_consulta_ni_respuesta(self):
        primary = FakeProvider("gemini", "free-model", ["respuesta secreta"])
        self.router(primary).ask("consulta privada")
        raw = self.metrics.path.read_text(encoding="utf-8")
        self.assertNotIn("consulta privada", raw)
        self.assertNotIn("respuesta secreta", raw)


if __name__ == "__main__":
    unittest.main()
