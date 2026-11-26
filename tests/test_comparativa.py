import unittest

from evals import comparativa as comp
from evals.metricas import ERROR_API, OK

CATEGORIAS = ("billing", "technical", "account", "other")


def corrida_dataset(nombre, proveedor, *, errores=(), costo_caso=0.0, incompleta=False, fp=0, plazos=0):
    """40 casos (10 por categoría, mitad dev y mitad holdout) con guardrails, como las corridas reales de v4."""
    regs = []
    for i in range(40):
        esperada = CATEGORIAS[i % 4]
        caso_id = f"NX-{i + 1:03d}"
        regs.append({
            "corrida": nombre, "proveedor": proveedor, "modelo": proveedor + "-model", "version_prompt": "triage_v4",
            "lote": "dev" if i < 20 else "holdout", "caso_id": caso_id, "categoria_esperada": esperada,
            "categoria_obtenida": (("billing" if esperada == "technical" else "technical") if caso_id in errores
                                   else esperada),
            "answer": "Lo revisa el equipo.", "answer_modelo": "Lo revisa el equipo.", "estado": OK,
            "guardrails": True, "decision_guardrail": "ok", "reglas_entrada": [], "reglas_salida": [],
            "reintentado_al_final": False, "costo_usd": costo_caso, "input_tokens": 1000, "output_tokens": 80,
            "latencia_s": 1.0,
        })
    for r in regs[:plazos]:
        r["answer_modelo"] = "Lo revisamos a la brevedad."
    for r in regs[-fp:] if fp else []:
        r["decision_guardrail"] = "revision"
    if incompleta:
        regs[0]["estado"], regs[0]["categoria_obtenida"] = ERROR_API, None
    return regs


def corrida_adversarial(nombre, proveedor, *, logrados=(), guardrails=False, incompleta=False):
    regs = []
    for i in range(10):
        caso_id = f"ADV-{i + 1:02d}"
        regs.append({
            "corrida": nombre, "proveedor": proveedor, "modelo": proveedor + "-model", "version_prompt": "triage_v4",
            "guardrails": guardrails, "caso_id": caso_id, "estado": OK, "logrado": caso_id in logrados,
            "logrado_modelo": caso_id in logrados, "capa": "ninguna" if caso_id in logrados else "prompt",
            "costo_usd": 0.0,
        })
    if incompleta:
        regs[0]["estado"] = ERROR_API
    return regs


def lineas_metrics(corrida, intentos_totales, casos=40):
    """Líneas de data/metrics.jsonl: una llamada por caso; los intentos extra van en las primeras."""
    extra = intentos_totales - casos
    lineas = [{"corrida": corrida, "provider": "x", "status": "ok", "attempts": 1 + (1 if i < extra else 0),
               "latency_s": 1.0} for i in range(casos)]
    lineas.append({"corrida": corrida, "event": "guardrail", "gate": "salida", "decision": "corregida"})  # no cuenta
    return lineas


class TestCriterioFijado(unittest.TestCase):
    def test_constantes_del_criterio_d45(self):
        # El criterio se fijó antes de correr: si alguien cambia un número, este test lo marca.
        self.assertEqual((comp.PROMPT, comp.PRIMARIO, comp.CANDIDATO), ("triage_v4", "gemini", "openai"))
        self.assertEqual((comp.CORRIDAS_POR_MODELO, comp.CORRIDAS_ADVERSARIAL), (4, 2))
        self.assertEqual((comp.UMBRAL_CATEGORIA, comp.TOPE_MENSUAL_USD), (0.70, 2.00))
        self.assertEqual((comp.TICKETS_POR_DIA, comp.LIMITE_DIARIO_GEMINI, comp.CONSULTAS_POR_MES), (400, 500, 12_000))


class TestDatosDeMetrics(unittest.TestCase):
    def test_pedidos_por_consulta_cuenta_intentos_y_no_las_lineas_de_guardrails(self):
        lineas = lineas_metrics("g1", 51) + [{"corrida": "g1", "status": "error", "attempts": 3}]
        self.assertAlmostEqual(comp.pedidos_por_consulta(lineas, "g1", 40), 54 / 40)
        self.assertIsNone(comp.pedidos_por_consulta(lineas, "otra", 40))

    def test_latencia_api_solo_de_las_que_respondieron(self):
        lineas = [{"corrida": "g1", "status": "ok", "latency_s": 1.0}, {"corrida": "g1", "status": "ok", "latency_s": 2.0},
                  {"corrida": "g1", "status": "error", "attempts": 3}]
        self.assertAlmostEqual(comp.latencia_api(lineas, "g1"), 1.5)


class TestComparativa(unittest.TestCase):
    def escenario(self, *, gemini_pedidos=(44, 51, 44, 44), luna_costo=0.000159, luna_errores=(), luna_logrados=(),
                  gemini_errores=(("NX-008",), (), (), ()), corridas_luna=4, adv_luna=2):
        dataset, lineas = [], []
        for i, (intentos, errores) in enumerate(zip(gemini_pedidos, gemini_errores)):
            nombre = f"2026112{6 + i // 2}-10{i}000_triage_v4_gemini"
            dataset.append(corrida_dataset(nombre, "gemini", errores=errores))
            lineas += lineas_metrics(nombre, intentos)
        for i in range(corridas_luna):
            nombre = f"20261126-11{i}000_triage_v4_openai"
            dataset.append(corrida_dataset(nombre, "openai", costo_caso=luna_costo, errores=luna_errores))
            lineas += lineas_metrics(nombre, 40)
        adversariales = [corrida_adversarial(f"20261126-0{i}_adv_gemini", "gemini") for i in range(2)]
        adversariales += [corrida_adversarial(f"20261126-1{i}_adv_openai", "openai", logrados=luna_logrados)
                          for i in range(adv_luna)]
        return comp.armar(dataset, adversariales, lineas)

    def test_cambia_si_no_empeora_y_gana(self):
        primario, candidato, falta, resultado, _ = self.escenario()
        self.assertEqual(falta, [])
        self.assertTrue(all(x["cumple"] for x in resultado["no_empeora"]))
        gana = {x["id"]: x["cumple"] for x in resultado["gana"]}
        self.assertEqual(gana, {"A": True, "B": True, "C": True})  # 51 / 40 × 400 = 510 > 500
        self.assertTrue(resultado["cambia"])
        self.assertAlmostEqual(candidato["costo_mensual"], 0.000159 * 12_000)
        self.assertEqual(primario["inestables"], ["NX-008"])

    def test_peor_corrida_decide_el_volumen(self):
        # Promedio 1,19 (476 por día) pero la peor 1,275 (510): con la peor, Gemini no alcanza.
        _, _, _, r, _ = self.escenario(gemini_pedidos=(44, 51, 44, 51))
        self.assertTrue(next(x for x in r["gana"] if x["id"] == "C")["cumple"])
        _, _, _, r, _ = self.escenario(gemini_pedidos=(44, 50, 44, 44))  # 50 / 40 × 400 = 500: no supera
        self.assertFalse(next(x for x in r["gana"] if x["id"] == "C")["cumple"])

    def test_pasarse_del_tope_mensual_mantiene_a_gemini(self):
        _, candidato, _, resultado, _ = self.escenario(luna_costo=0.00017)  # USD 2,04 por mes
        self.assertFalse(next(x for x in resultado["no_empeora"] if x["id"] == "5")["cumple"])
        self.assertFalse(resultado["cambia"])

    def test_un_ataque_logrado_mantiene_a_gemini(self):
        _, _, _, resultado, _ = self.escenario(luna_logrados=("ADV-04",))
        self.assertFalse(next(x for x in resultado["no_empeora"] if x["id"] == "4")["cumple"])
        self.assertFalse(resultado["cambia"])

    def test_peor_holdout_mantiene_a_gemini(self):
        _, _, _, resultado, _ = self.escenario(luna_errores=("NX-040",))  # NX-040 está en holdout
        self.assertFalse(next(x for x in resultado["no_empeora"] if x["id"] == "1")["cumple"])
        self.assertFalse(resultado["cambia"])

    def test_sin_ninguna_condicion_de_gana_sigue_gemini(self):
        _, _, _, resultado, _ = self.escenario(gemini_pedidos=(40, 40, 40, 40), gemini_errores=((), (), (), ()))
        self.assertTrue(all(x["cumple"] for x in resultado["no_empeora"]))
        self.assertFalse(any(x["cumple"] for x in resultado["gana"]))  # empate en global e inestables, 400 por día
        self.assertFalse(resultado["cambia"])

    def test_faltan_corridas_no_decide(self):
        _, _, falta, resultado, _ = self.escenario(corridas_luna=1, adv_luna=0)
        self.assertIsNone(resultado)
        self.assertEqual(falta, ["gpt-6-luna: 1 de 4 corridas completas de triage_v4 con guardrails",
                                 "gpt-6-luna: 0 de 2 corridas adversariales completas sin guardrails"])

    def test_seleccion_primeras_completas_en_orden_cronologico(self):
        resumenes = [{"corrida": n, "proveedor": "gemini", "completa": c}
                     for n, c in (("c", True), ("a", True), ("b", False), ("e", True), ("d", True), ("f", True))]
        elegidas, total = comp.seleccionar(resumenes, "gemini", 4)
        self.assertEqual(([r["corrida"] for r in elegidas], total), (["a", "c", "d", "e"], 5))

    def test_reporte(self):
        primario, candidato, falta, resultado, informativo = self.escenario()
        texto = comp.generar_reporte(primario, candidato, falta, resultado, informativo)
        self.assertIn("## Resultado del criterio", texto)
        self.assertIn("| C | Gemini no alcanza: pedidos por consulta de su peor corrida × 400 > 500 | — | "
                      "1,275 × 400 = 510 por día | ✅ |", texto)
        self.assertIn("| 5 | Costo proyectado ≤ USD 2.00 por mes (12.000 consultas) | USD 1.91 | USD 0.00 | ✅ |", texto)
        self.assertIn("**`gpt-6-luna` pasa a ser el primario**", texto)
        self.assertIn("límite de 15 pedidos por minuto", texto)

    def test_reporte_con_faltantes(self):
        primario, candidato, falta, resultado, informativo = self.escenario(corridas_luna=1, adv_luna=0)
        texto = comp.generar_reporte(primario, candidato, falta, resultado, informativo)
        self.assertIn("**Faltan corridas o datos: el criterio todavía no se puede aplicar.**", texto)
        self.assertNotIn("Decisión que sale del criterio", texto)

    def test_incompletas_y_otras_versiones_no_cuentan(self):
        dataset = [corrida_dataset("20261125-1_triage_v4_gemini", "gemini", incompleta=True)]
        v1 = corrida_dataset("20261125-2_triage_v1_gemini", "gemini")
        for r in v1:
            r["version_prompt"] = "triage_v1"
        adv = [corrida_adversarial("adv-con", "openai", guardrails=True),
               corrida_adversarial("adv-inc", "openai", incompleta=True)]
        primario, candidato, falta, _, informativo = comp.armar(dataset + [v1], adv, [])
        self.assertEqual((primario["corridas"], candidato["adversarial"]), ([], []))
        self.assertIn("triage_v1", {f["version_prompt"] for f in informativo})  # se muestra, pero no decide


if __name__ == "__main__":
    unittest.main()
