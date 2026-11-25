import io
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest import mock

from src import main as cli
from src.config import ConfigError, load_settings
from src.llm.gemini_provider import find_retry_delay
from tests.fakes import FakeProvider, temp_dir, write_pricing

NO_ENV = Path("no-existe.env")


class TestConfig(unittest.TestCase):
    def test_valores_por_defecto(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            s = load_settings(NO_ENV)
        self.assertEqual(s.provider_order, ["gemini", "openai"])
        self.assertEqual(s.providers["gemini"].model, "gemini-3.5-flash-lite")
        self.assertEqual(s.providers["openai"].model, "gpt-6-luna")
        self.assertEqual(s.providers["openai"].reasoning_effort, "none")
        self.assertEqual((s.temperature, s.budget_usd), (0.0, 4.5))

    def test_proveedor_desconocido(self):
        with mock.patch.dict(os.environ, {"LLM_PROVIDER_ORDER": "gemini,anthropic"}, clear=True):
            with self.assertRaises(ConfigError):
                load_settings(NO_ENV)

    def test_numero_invalido(self):
        with mock.patch.dict(os.environ, {"BUDGET_USD": "mucho"}, clear=True):
            with self.assertRaises(ConfigError):
                load_settings(NO_ENV)


class TestGeminiRetryDelay(unittest.TestCase):
    def test_lee_retry_delay_del_cuerpo_del_error(self):
        details = {"error": {"details": [{"@type": "RetryInfo", "retryDelay": "34s"}]}}
        self.assertEqual(find_retry_delay(details), 34.0)
        self.assertIsNone(find_retry_delay({"error": {}}))


class TestCli(unittest.TestCase):
    def setUp(self):
        self.tmp = temp_dir()
        folder = Path(self.tmp.name)
        with mock.patch.dict(os.environ, {}, clear=True):
            base = load_settings(NO_ENV)
        self.settings = replace(base, pricing_path=write_pricing(folder), metrics_path=folder / "metrics.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, argv, providers):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(cli, "load_settings", return_value=self.settings), \
                mock.patch.object(cli, "build_providers", return_value=providers), \
                redirect_stdout(out), redirect_stderr(err):
            code = cli.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_responde_y_registra_metricas(self):
        code, out, err = self.run_cli(["hola"], [FakeProvider("gemini", "free-model", ["respuesta"])])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertEqual(out.strip(), "respuesta")
        self.assertEqual(err, "")
        self.assertTrue(self.settings.metrics_path.exists())

    def test_detalle_con_costo_en_6_decimales(self):
        provider = FakeProvider("openai", "paid-model", ["respuesta"], prompt_tokens=60, completion_tokens=24)
        code, out, err = self.run_cli(["--detalle", "--proveedor", "openai", "hola"], [provider])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertEqual(out.strip(), "respuesta")  # el detalle no ensucia la salida estándar
        self.assertIn("USD 0.000018", err)  # 60 × 0.10/1M + 24 × 0.50/1M
        self.assertNotIn("e-05", err)

    def test_consulta_vacia(self):
        code, _, err = self.run_cli(["   "], [])
        self.assertEqual(code, cli.EXIT_EMPTY_QUERY)
        self.assertIn("vacía", err)

    def test_fallan_todos(self):
        from src.llm.base import AuthError
        code, out, err = self.run_cli(["hola"], [FakeProvider("gemini", "free-model", [AuthError("gemini", "x")])])
        self.assertEqual(code, cli.EXIT_ALL_FAILED)
        self.assertEqual(out, "")
        self.assertIn("Aviso: gemini", err)

    def test_modelo_sin_precio_es_error_de_configuracion(self):
        code, _, err = self.run_cli(["hola"], [FakeProvider("gemini", "sin-precio", ["x"])])
        self.assertEqual(code, cli.EXIT_CONFIG)
        self.assertIn("pricing.json", err)


if __name__ == "__main__":
    unittest.main()
