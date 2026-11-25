import unittest

from pydantic import ValidationError

from src.contract import ACTIONS, CATEGORIES, TRIAGE_TOOL, TriageResult, describe_errors, error_codes
from src.llm.openai_provider import parse_arguments
from tests.fakes import VALID


def errors_for(data: dict) -> ValidationError:
    """Valida ``data`` y devuelve el ValidationError (falla si el contrato lo acepta)."""
    try:
        TriageResult.model_validate(data)
    except ValidationError as exc:
        return exc
    raise AssertionError(f"el contrato aceptó un dato inválido: {data}")


class TestContrato(unittest.TestCase):
    def test_contrato_valido(self):
        result = TriageResult.model_validate(VALID)
        self.assertEqual(result.category, "billing")

    def test_ejemplo_del_video_de_henry_falla_en_los_tres_campos(self):
        # M1L3, video 2: confianza 47.0, categoría "factura", acción "bailar" → 3 errores, uno por campo.
        exc = errors_for({**VALID, "confidence": 47.0, "category": "factura", "actions": ["bailar"]})
        fields = {e["loc"][0] for e in exc.errors()}
        self.assertEqual(fields, {"confidence", "category", "actions"})

    def test_dominio_de_cada_campo(self):
        invalid = [
            {**VALID, "answer": "   "},                              # vacío después de recortar
            {**VALID, "answer": "x" * 501},                          # más de 500 caracteres
            {**VALID, "confidence": -0.1},
            {**VALID, "confidence": "0.9"},                          # texto, no número
            {**VALID, "category": "Billing"},                        # mayúscula: no está en la lista
            {**VALID, "actions": []},
            {**VALID, "actions": ["review_charge", "review_charge"]},
            {**VALID, "actions": ["no_action", "review_charge"]},
            {**VALID, "extra": "campo de más"},
            {k: v for k, v in VALID.items() if k != "answer"},       # falta un campo
        ]
        for data in invalid:
            with self.subTest(data=data):
                with self.assertRaises(ValidationError):
                    TriageResult.model_validate(data)

    def test_mensajes_dicen_el_campo_sin_el_valor(self):
        exc = errors_for({**VALID, "category": "factura"})
        self.assertTrue(describe_errors(exc).startswith("category:"))
        self.assertNotIn("factura", describe_errors(exc))
        self.assertEqual(error_codes(exc), ["category:literal_error"])

    def test_schema_de_la_tool_sale_del_contrato(self):
        props = TRIAGE_TOOL.parameters["properties"]
        self.assertEqual(set(props), {"answer", "confidence", "category", "actions"})
        self.assertEqual(props["category"]["enum"], list(CATEGORIES))
        self.assertEqual(props["actions"]["items"]["enum"], list(ACTIONS))
        self.assertEqual(TRIAGE_TOOL.parameters["required"], ["answer", "confidence", "category", "actions"])


class TestArgumentosOpenAI(unittest.TestCase):
    def test_texto_json_a_dict(self):
        self.assertEqual(parse_arguments('{"a": 1}'), ({"a": 1}, None))
        self.assertEqual(parse_arguments('{"a": '), (None, "json_invalido"))
        self.assertEqual(parse_arguments("[1, 2]"), (None, "args_no_objeto"))


if __name__ == "__main__":
    unittest.main()
