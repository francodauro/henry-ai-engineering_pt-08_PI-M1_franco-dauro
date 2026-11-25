import unittest
from pathlib import Path

from src.config import PROJECT_ROOT
from src.contract import ACTIONS, CATEGORIES
from src.costs import Pricing
from src.llm.router import Router
from src.metrics import MetricsLog
from src.prompts import PromptError, load_prompt, render_system, render_user
from src.triage import ContractError, InvalidQueryError, triage
from tests.fakes import VALID, FakeProvider, temp_dir, write_pricing

PROMPTS = PROJECT_ROOT / "prompts"


class TestPrompts(unittest.TestCase):
    def test_v1_carga_y_se_completa(self):
        template = load_prompt("v1", PROMPTS)
        self.assertEqual(template.version, "triage_v1")
        system = render_system(template)
        self.assertIn("Nubbix", system)
        for name in list(CATEGORIES) + list(ACTIONS):
            self.assertIn(f"- {name}:", system)
        self.assertNotIn("{", system)  # no quedó ninguna variable sin completar
        self.assertEqual(render_user(template, "hola"), "<consulta>hola</consulta>")

    def test_v1_prohibe_plazos_vagos(self):
        self.assertIn("a la brevedad", load_prompt("triage_v1", PROMPTS).system)

    def test_version_inexistente(self):
        with self.assertRaises(PromptError):
            load_prompt("v99", PROMPTS)

    def test_variable_desconocida(self):
        with temp_dir() as tmp:
            folder = Path(tmp)
            (folder / "triage_v1.yaml").write_text(
                "version: triage_v1\nfecha: x\ntecnica: x\ndescripcion: x\n"
                "system: 'Sos {empresa} {categorias} {acciones} {categoria}'\nuser: '{consulta}'\n",
                encoding="utf-8")
            with self.assertRaises(PromptError):
                load_prompt("v1", folder)


class TestTriage(unittest.TestCase):
    def setUp(self):
        self.tmp = temp_dir()
        folder = Path(self.tmp.name)
        self.metrics = MetricsLog(folder / "metrics.jsonl")
        self.pricing = Pricing(write_pricing(folder))
        self.template = load_prompt("v1", PROMPTS)

    def tearDown(self):
        self.tmp.cleanup()

    def run_triage(self, provider, query="me cobraron dos veces"):
        router = Router([provider], self.pricing, self.metrics, budget_usd=4.5, max_retries=0, max_wait_s=10)
        return triage(query, router, self.template, max_attempts=3)

    def test_primer_intento_valido(self):
        outcome = self.run_triage(FakeProvider("gemini", "free-model", [VALID]))
        self.assertEqual((outcome.result.category, outcome.attempts), ("billing", 1))

    def test_reintento_informado_con_el_error_en_el_system(self):
        provider = FakeProvider("gemini", "free-model", [{**VALID, "category": "factura"}, VALID])
        outcome = self.run_triage(provider)
        self.assertEqual(outcome.attempts, 2)
        self.assertNotIn("inválida", provider.systems[0])
        self.assertIn("Tu respuesta anterior fue inválida: category:", provider.systems[1])

    def test_respuesta_de_texto_en_vez_de_tool_call(self):
        provider = FakeProvider("gemini", "free-model", ["texto libre", VALID])
        outcome = self.run_triage(provider)
        self.assertEqual(outcome.attempts, 2)
        self.assertIn("no llamaste a la función", provider.systems[1])

    def test_se_agotan_los_intentos(self):
        bad = {**VALID, "confidence": 47}
        provider = FakeProvider("gemini", "free-model", [bad, bad, bad])
        with self.assertRaises(ContractError):
            self.run_triage(provider)
        self.assertEqual(provider.calls, 3)

    def test_consulta_vacia_no_llama_al_modelo(self):
        provider = FakeProvider("gemini", "free-model", [VALID])
        with self.assertRaises(InvalidQueryError):
            self.run_triage(provider, query="   ")
        self.assertEqual(provider.calls, 0)

    def test_metricas_del_contrato_sin_texto(self):
        self.run_triage(FakeProvider("gemini", "free-model", [{**VALID, "category": "factura"}, VALID]))
        first, second = self.metrics.read_all()
        self.assertEqual(first["request_id"], second["request_id"])
        self.assertEqual((first["contract_attempt"], first["contract_valid"]), (1, False))
        self.assertEqual(first["contract_errors"], ["category:literal_error"])
        self.assertEqual((second["contract_attempt"], second["contract_valid"]), (2, True))
        self.assertEqual(second["prompt_version"], "triage_v1")
        raw = self.metrics.path.read_text(encoding="utf-8")
        self.assertNotIn("cobraron", raw)
        self.assertNotIn("factura", raw)


if __name__ == "__main__":
    unittest.main()
