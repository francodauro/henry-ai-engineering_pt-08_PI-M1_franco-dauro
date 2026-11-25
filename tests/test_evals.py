import json
import unittest
from collections import Counter
from datetime import datetime
from pathlib import Path

from evals import runner
from evals.metricas import CONTRATO_INVALIDO, ERROR_API, OK, comparar_versiones, costo_por_acierto, exact_match, resumir
from evals.reporte import generar_reporte
from src.config import PROJECT_ROOT
from src.costs import Pricing
from src.llm.base import AuthError, ServerError
from src.llm.router import Router
from src.metrics import MetricsLog
from src.prompts import load_prompt, render_system
from src.vague_timing import find_vague_timing
from tests.fakes import FakeProvider, temp_dir, write_pricing

PROMPTS = PROJECT_ROOT / "prompts"


def contrato(category, answer="Lo deriva el equipo de facturación."):
    return {"answer": answer, "confidence": 0.9, "category": category, "actions": ["escalate_to_human"]}


def caso(id_, categoria, texto="consulta de prueba"):
    return {"id": id_, "texto": texto, "categoria_esperada": categoria, "dificultad": "facil", "lote": "dev", "nota": "x"}


def registro(caso_id, esperada, obtenida, answer="Lo revisa el equipo.", estado=OK, costo=0.0, lote="dev"):
    return {"corrida": "c1", "proveedor": "gemini", "modelo": "free-model", "version_prompt": "triage_v1", "lote": lote,
            "caso_id": caso_id, "categoria_esperada": esperada, "categoria_obtenida": obtenida, "answer": answer,
            "estado": estado, "costo_usd": costo, "input_tokens": 10, "output_tokens": 5, "latencia_s": 1.0}


class TestDataset(unittest.TestCase):
    def test_dataset_real_cumple_el_pi(self):
        casos = runner.cargar_dataset()
        self.assertGreaterEqual(len(casos), 30)  # el PI pide al menos 30
        self.assertEqual(len(casos), 40)
        self.assertEqual(Counter(c["categoria_esperada"] for c in casos),
                         {"billing": 10, "technical": 10, "account": 10, "other": 10})
        self.assertEqual(Counter(c["lote"] for c in casos), {"dev": 20, "holdout": 20})
        self.assertEqual(sum(c["dificultad"] != "facil" for c in casos), 28)
        for c in casos:
            self.assertEqual(set(c), set(runner.CAMPOS))

    def _escribir(self, folder, lineas):
        path = Path(folder) / "dataset.jsonl"
        path.write_text("\n".join(lineas) + "\n", encoding="utf-8")
        return path

    def test_error_dice_la_linea(self):
        with temp_dir() as tmp:
            bueno = json.dumps(caso("A", "billing"))
            path = self._escribir(tmp, [bueno, '{"id": "B", "texto": "x", "lote": si}'])
            with self.assertRaisesRegex(runner.EvalError, "línea 2"):
                runner.cargar_dataset(path)

    def test_rechaza_categoria_id_repetido_y_campo_faltante(self):
        with temp_dir() as tmp:
            for lineas, mensaje in (
                ([json.dumps(caso("A", "factura"))], "categoria_esperada"),
                ([json.dumps(caso("A", "billing")), json.dumps(caso("A", "other"))], "repetido"),
                ([json.dumps({**caso("A", "billing"), "nota": ""})], "nota"),
            ):
                with self.assertRaisesRegex(runner.EvalError, mensaje):
                    runner.cargar_dataset(self._escribir(tmp, lineas))


class TestPlazosVagos(unittest.TestCase):
    def test_detecta_variantes(self):
        self.assertEqual(find_vague_timing("Le responderemos a la brevedad."), ["a la brevedad"])
        self.assertEqual(find_vague_timing("Lo vemos A LA MAYOR BREVEDAD POSIBLE"), ["a la mayor brevedad posible"])
        self.assertEqual(find_vague_timing("en breve y lo mas antes posible"), ["en breve", "lo mas antes posible"])
        self.assertEqual(find_vague_timing("en los próximos días hábiles"), ["en los próximos días hábiles"])

    def test_no_marca_texto_normal(self):
        self.assertEqual(find_vague_timing("El equipo de facturación revisará el cobro."), [])
        self.assertEqual(find_vague_timing("Breve consulta: ¿cuánto antes de vencer avisan?"), [])
        self.assertEqual(find_vague_timing(None), [])


class TestMetricas(unittest.TestCase):
    def test_exact_match(self):
        self.assertTrue(exact_match(" Billing ", "billing"))
        self.assertFalse(exact_match(None, "billing"))
        self.assertFalse(exact_match("other", "billing"))

    def test_costo_por_acierto(self):
        self.assertAlmostEqual(costo_por_acierto(0.004, 40), 0.0001)
        self.assertIsNone(costo_por_acierto(0.004, 0))

    def test_score_global_por_categoria_y_umbral(self):
        regs = ([registro(f"B{i}", "billing", "billing") for i in range(7)]
                + [registro(f"B{i}", "billing", "other") for i in range(7, 10)]
                + [registro(f"T{i}", "technical", "technical") for i in range(6)]
                + [registro(f"T{i}", "technical", None, estado=CONTRATO_INVALIDO) for i in range(6, 10)]
                + [registro(f"A{i}", "account", "account") for i in range(10)]
                + [registro(f"O{i}", "other", "other") for i in range(10)])
        r = resumir(regs)
        self.assertEqual((r["n"], r["aciertos"]), (40, 33))
        self.assertEqual(r["por_categoria"]["billing"]["score"], 0.7)
        self.assertFalse(r["por_categoria"]["billing"]["bajo_umbral"])  # 0.70 justo pasa
        self.assertTrue(r["por_categoria"]["technical"]["bajo_umbral"])
        self.assertEqual(r["regresiones"], ["technical 60% < 70%"])
        self.assertEqual(r["contrato_invalido"], ["T6", "T7", "T8", "T9"])
        self.assertTrue(r["completa"])

    def test_categoria_sin_casos_no_pasa(self):
        r = resumir([registro("B1", "billing", "billing")])
        self.assertTrue(r["por_categoria"]["other"]["bajo_umbral"])

    def test_un_plazo_vago_es_regresion(self):
        regs = [registro(f"{c}{i}", c, c) for c in ("billing", "technical", "account", "other") for i in range(2)]
        regs[0]["answer"] = "Lo revisamos a la brevedad."
        r = resumir(regs)
        self.assertEqual(r["plazos_vagos"], [{"caso_id": "billing0", "categoria": "billing", "frases": ["a la brevedad"]}])
        self.assertEqual(r["plazos_por_categoria"]["billing"], 1)
        self.assertEqual(r["regresiones"], ["plazos vagos en 1 respuesta (máximo 0)"])

    def test_error_api_deja_incompleta(self):
        r = resumir([registro("B1", "billing", "billing"), registro("B2", "billing", None, answer=None, estado=ERROR_API)])
        self.assertFalse(r["completa"])
        self.assertEqual(r["errores_api"], ["B2"])

    def test_costo(self):
        r = resumir([registro("B1", "billing", "billing", costo=0.002), registro("B2", "billing", "other", costo=0.001)])
        self.assertAlmostEqual(r["costo_total"], 0.003)
        self.assertAlmostEqual(r["costo_por_acierto"], 0.003)


class TestPaso4(unittest.TestCase):
    PRECIO_REF = {"input": 0.10, "output": 0.50}

    def corrida(self, nombre, version, obtenida_b0="billing"):
        regs = [registro(f"{c}{i}", c, c, lote="dev" if i == 0 else "holdout")
                for c in ("billing", "technical", "account", "other") for i in range(2)]
        regs[0]["categoria_obtenida"] = obtenida_b0
        for r in regs:
            r.update(corrida=nombre, version_prompt=version)
        return regs

    def test_score_por_lote_y_costo_proyectado(self):
        r = resumir(self.corrida("a", "triage_v1", obtenida_b0="other"), self.PRECIO_REF)
        self.assertEqual(r["por_lote"]["dev"], {"n": 4, "aciertos": 3, "score": 0.75})
        self.assertEqual(r["por_lote"]["holdout"]["score"], 1.0)
        # 8 casos × (10 tokens de entrada, 5 de salida) con los precios de gpt-6-luna
        self.assertAlmostEqual(r["costo_proyectado"], 80 / 1e6 * 0.10 + 40 / 1e6 * 0.50)
        self.assertAlmostEqual(r["costo_por_acierto_proyectado"], r["costo_proyectado"] / 7)
        self.assertIsNone(resumir(self.corrida("a", "triage_v1"))["costo_proyectado"])

    def test_comparar_versiones_promedia_y_marca_inestables(self):
        resumenes = [resumir(self.corrida("v1a", "triage_v1", "other"), self.PRECIO_REF),
                     resumir(self.corrida("v1b", "triage_v1", "other"), self.PRECIO_REF),
                     resumir(self.corrida("v2a", "triage_v2", "billing"), self.PRECIO_REF),
                     resumir(self.corrida("v2b", "triage_v2", "other"), self.PRECIO_REF)]
        v1, v2 = comparar_versiones(resumenes)
        self.assertEqual((v1["version_prompt"], v1["corridas"], v1["inestables"]), ("triage_v1", 2, []))
        self.assertEqual(v1["por_lote"]["dev"], 0.75)
        self.assertEqual(v1["errores"], ["billing0"])
        self.assertEqual(v2["inestables"], ["billing0"])  # acertó en una corrida y no en la otra: azar
        self.assertEqual(v2["por_lote"]["dev"], 0.875)

    def test_comparar_ignora_incompletas(self):
        regs = self.corrida("x", "triage_v1")
        regs[0]["estado"] = ERROR_API
        self.assertEqual(comparar_versiones([resumir(regs)]), [])

    def test_reporte_tiene_lotes_y_comparacion(self):
        resumenes = [resumir(self.corrida("v1a", "triage_v1", "other"), self.PRECIO_REF),
                     resumir(self.corrida("v2a", "triage_v2"), self.PRECIO_REF)]
        texto = generar_reporte(resumenes, TestReporte.DATASET, {})
        self.assertIn("| dev | holdout |", texto)
        self.assertIn("## 4. Comparación por versión y proveedor", texto)
        self.assertIn("| triage_v2 | gemini | 1 | 100% | 100% | 100% |", texto)
        self.assertIn("Costo por acierto proyectado con gpt-6-luna", texto)

    def test_v2_es_v1_mas_el_par_de_contraste(self):
        v1, v2 = load_prompt("v1", PROMPTS), load_prompt("v2", PROMPTS)
        self.assertEqual(v2.version, "triage_v2")
        self.assertEqual(v2.user, v1.user)
        self.assertIn('"billing"', render_system(v2))
        self.assertIn("¿Qué precio tiene el módulo de facturación?", v2.system)
        # Un solo cambio: quitando el bloque de ejemplos, v2 es igual a v1.
        bloque = v2.system[v2.system.index("Ejemplos del límite"):v2.system.index("Respuesta para el cliente:")]
        self.assertEqual(v2.system.replace(bloque, ""), v1.system)

    def test_ejemplos_no_son_casos_del_dataset(self):
        system = load_prompt("v2", PROMPTS).system
        for c in runner.cargar_dataset():
            self.assertNotIn(c["texto"], system)


class TestRunner(unittest.TestCase):
    def setUp(self):
        self.tmp = temp_dir()
        self.folder = Path(self.tmp.name)
        self.metrics = MetricsLog(self.folder / "metrics.jsonl")
        self.pricing = Pricing(write_pricing(self.folder))
        self.template = load_prompt("v1", PROMPTS)
        self.casos = [caso("B1", "billing"), caso("T1", "technical"), caso("A1", "account"), caso("O1", "other")]
        self.pausas = []

    def tearDown(self):
        self.tmp.cleanup()

    def correr(self, provider, casos=None):
        router = Router([provider], self.pricing, self.metrics, budget_usd=4.5, max_retries=0, max_wait_s=10)
        return runner.correr(casos or self.casos, router, self.template, corrida="c1", proveedor=provider.name,
                             modelo=provider.model, temperature=0.0, max_attempts=3, pausa=6,
                             pausa_reintento=30, sleep=self.pausas.append, avisar=lambda m: None)

    def test_corrida_completa(self):
        provider = FakeProvider("openai", "paid-model", [contrato("billing"), contrato("technical"),
                                                           contrato("account"), contrato("billing")])
        regs = self.correr(provider)
        self.assertEqual([r["acierto"] for r in regs], [True, True, True, False])
        self.assertEqual(self.pausas, [6, 6, 6])  # pausa entre casos, no antes del primero
        r0 = regs[0]
        self.assertEqual((r0["texto"], r0["answer"], r0["estado"], r0["intentos_contrato"]),
                         ("consulta de prueba", "Lo deriva el equipo de facturación.", OK, 1))
        self.assertAlmostEqual(r0["costo_usd"], 100 / 1e6 * 0.10 + 20 / 1e6 * 0.50)
        # Cada línea de metrics.jsonl lleva el nombre de la corrida y el costo coincide.
        lineas = self.metrics.read_all()
        self.assertTrue(all(l["corrida"] == "c1" for l in lineas))
        self.assertAlmostEqual(runner.costos_en_metrics(self.metrics, ["c1"])["c1"], sum(r["costo_usd"] for r in regs))

    def test_contrato_invalido_cuenta_como_error_y_suma_todos_los_intentos(self):
        malo = {"category": "factura"}
        provider = FakeProvider("openai", "paid-model", [malo, malo, malo, contrato("technical"),
                                                           contrato("account"), contrato("other")])
        regs = self.correr(provider)
        self.assertEqual((regs[0]["estado"], regs[0]["categoria_obtenida"], regs[0]["acierto"]),
                         (CONTRATO_INVALIDO, None, False))
        self.assertEqual((regs[0]["intentos_contrato"], regs[0]["input_tokens"]), (3, 300))
        self.assertTrue(all(r["acierto"] for r in regs[1:]))

    def test_error_transitorio_se_reintenta_al_final(self):
        provider = FakeProvider("gemini", "free-model", [
            ServerError("gemini", "high demand"), contrato("technical"), contrato("account"), contrato("other"),
            contrato("billing"),  # el reintento de B1, al final
        ])
        regs = self.correr(provider)
        self.assertEqual(regs[0]["caso_id"], "B1")  # conserva el orden del dataset
        self.assertTrue(regs[0]["reintentado_al_final"])
        self.assertTrue(regs[0]["acierto"])
        self.assertTrue(resumir(regs)["completa"])
        self.assertEqual(self.pausas, [6, 6, 6, 30])

    def test_si_el_reintento_falla_queda_incompleta(self):
        caida = ServerError("gemini", "high demand")
        provider = FakeProvider("gemini", "free-model", [caida, contrato("technical"), contrato("account"),
                                                           contrato("other"), caida])
        regs = self.correr(provider)
        r = resumir(regs)
        self.assertFalse(r["completa"])
        self.assertEqual(r["errores_api"], ["B1"])
        self.assertEqual(runner.codigo_salida([r]), runner.EXIT_INCOMPLETA)

    def test_error_no_transitorio_cancela_la_corrida(self):
        provider = FakeProvider("openai", "paid-model", [AuthError("openai", "clave inválida")])
        with self.assertRaises(runner.CorridaAbortada):
            self.correr(provider)
        self.assertEqual(provider.calls, 1)

    def test_guardar_no_pisa_una_corrida(self):
        regs = [registro("B1", "billing", "billing")]
        path = runner.guardar_corrida(regs, "c1", self.folder)
        self.assertEqual(runner.leer_corrida(path), regs)
        with self.assertRaises(FileExistsError):
            runner.guardar_corrida(regs, "c1", self.folder)

    def test_nombre_corrida(self):
        self.assertEqual(runner.nombre_corrida("triage_v1", "gemini", datetime(2026, 11, 25, 13, 5, 9)),
                         "20261125-130509_triage_v1_gemini")

    def test_expandir_comodines(self):
        for nombre in ("a_gemini.jsonl", "b_openai.jsonl"):
            (self.folder / nombre).write_text("{}\n", encoding="utf-8")
        self.assertEqual([p.name for p in runner.expandir([str(self.folder / "*.jsonl")])],
                         ["a_gemini.jsonl", "b_openai.jsonl"])
        with self.assertRaises(runner.EvalError):
            runner.expandir([str(self.folder / "*.txt")])


class TestReporte(unittest.TestCase):
    DATASET = {"ruta": "evals/dataset.jsonl", "n": 8, "por_categoria": {"billing": 2, "technical": 2, "account": 2, "other": 2}}

    def corrida(self, nombre, proveedor, costo, fallar=False, plazo=False):
        regs = [registro(f"{c}{i}", c, c, costo=costo) for c in ("billing", "technical", "account", "other") for i in range(2)]
        for r in regs:
            r.update(corrida=nombre, proveedor=proveedor)
        if fallar:
            regs[0]["categoria_obtenida"] = "other"
        if plazo:
            regs[1]["answer"] = "Le escribimos en breve."
        return resumir(regs)

    def test_responde_las_tres_preguntas(self):
        gemini = self.corrida("g", "gemini", 0.0, fallar=True, plazo=True)
        openai = self.corrida("o", "openai", 0.0001)
        texto = generar_reporte([gemini, openai], self.DATASET, {"g": 0.0, "o": 0.0008}, ahora=datetime(2026, 11, 25))
        for titulo in ("## 1. Qué se evaluó", "## 2. ¿Alguna categoría quedó bajo el umbral?",
                       "## 3. ¿El score y el costo por acierto cuentan la misma historia?"):
            self.assertIn(titulo, texto)
        self.assertIn("billing 50% < 70%", texto)
        self.assertIn("plazos vagos en 1 respuesta ", texto)
        self.assertIn('Plazo vago: billing1 (billing): "en breve"', texto)
        self.assertIn("billing0 esperaba `billing`, obtuvo `other`", texto)
        self.assertIn("USD 0.000800 ✓", texto)
        # Gemini tiene mejor costo por acierto (0) y OpenAI mejor score: no cuentan la misma historia.
        self.assertIn("**No cuentan la misma historia**", texto)
        self.assertIn("Ojo: g tiene regresiones", texto)

    def test_empate_en_score_y_regresion_del_mas_barato(self):
        # Como la corrida real del paso 3: mismo score, Gemini gratis pero con un plazo vago.
        gemini = self.corrida("g", "gemini", 0.0, plazo=True)
        openai = self.corrida("o", "openai", 0.0001)
        texto = generar_reporte([gemini, openai], self.DATASET, {"g": 0.0, "o": 0.0008})
        self.assertIn("**Cuentan la misma historia**", texto)
        self.assertIn("Ojo: g tiene regresiones (sección 2)", texto)

    def test_incompleta_no_se_compara(self):
        incompleta = self.corrida("g", "gemini", 0.0)
        incompleta["completa"], incompleta["errores_api"] = False, ["billing0"]
        texto = generar_reporte([incompleta], self.DATASET, {"g": None})
        self.assertIn("Incompleta (no se compara)", texto)
        self.assertIn("No hay corridas completas", texto)
        self.assertIn("sin líneas", texto)


if __name__ == "__main__":
    unittest.main()
