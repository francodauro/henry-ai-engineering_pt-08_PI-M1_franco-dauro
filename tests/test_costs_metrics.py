import json
import unittest
from pathlib import Path

from src.config import PROJECT_ROOT
from src.costs import Pricing, PricingError, format_usd
from src.metrics import MetricsLog
from tests.fakes import temp_dir, write_pricing


class TestPricing(unittest.TestCase):
    def setUp(self):
        self.tmp = temp_dir()
        self.pricing = Pricing(write_pricing(Path(self.tmp.name)))

    def tearDown(self):
        self.tmp.cleanup()

    def test_costo_tokens_por_precio(self):
        # 1000 tokens de entrada a USD 0.10/1M + 200 de salida a USD 0.50/1M = 0.0001 + 0.0001
        self.assertAlmostEqual(self.pricing.cost("paid-model", 1000, 200), 0.0002)

    def test_modelo_gratuito_cuesta_cero(self):
        self.assertEqual(self.pricing.cost("free-model", 5000, 900), 0.0)
        self.assertFalse(self.pricing.is_paid("free-model"))
        self.assertTrue(self.pricing.is_paid("paid-model"))

    def test_modelo_sin_precio_falla(self):
        with self.assertRaises(PricingError):
            self.pricing.cost("otro", 1, 1)

    def test_pricing_del_repo_tiene_los_dos_modelos(self):
        real = Pricing(PROJECT_ROOT / "config" / "pricing.json")
        self.assertEqual(real.price("gpt-6-luna"), {"input": 0.10, "output": 0.50})
        self.assertFalse(real.is_paid("gemini-3.5-flash-lite"))


class TestFormatUsd(unittest.TestCase):
    def test_sin_notacion_cientifica(self):
        self.assertEqual(str(0.000018), "1.8e-05")  # lo que haría Python solo
        self.assertEqual(format_usd(0.000018), "0.000018")
        self.assertEqual(format_usd(0.0), "0.000000")


class TestMetricsLog(unittest.TestCase):
    def setUp(self):
        self.tmp = temp_dir()
        self.log = MetricsLog(Path(self.tmp.name) / "data" / "metrics.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def test_append_una_linea_por_llamada_con_timestamp(self):
        self.log.append({"provider": "gemini", "cost_usd": 0.0})
        self.log.append({"provider": "openai", "cost_usd": 0.000018})
        lines = self.log.path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        first = json.loads(lines[0])
        self.assertEqual(list(first)[0], "timestamp")
        self.assertIn("+00:00", first["timestamp"])

    def test_costo_se_guarda_como_numero_y_suma(self):
        self.log.append({"cost_usd": 0.000018})
        self.log.append({"cost_usd": 0.000002})
        self.assertIsInstance(self.log.read_all()[0]["cost_usd"], float)
        self.assertAlmostEqual(self.log.total_cost(), 0.00002)

    def test_archivo_inexistente_gasto_cero(self):
        self.assertEqual(self.log.total_cost(), 0.0)


if __name__ == "__main__":
    unittest.main()
