import unittest

from src.llm.base import AuthError, RateLimitError, ServerError
from src.retry import backoff_seconds, call_with_backoff


class Script:
    """Función que falla con los errores dados y después responde "ok"."""

    def __init__(self, *errors):
        self.errors = list(errors)
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return "ok"


class TestBackoff(unittest.TestCase):
    def test_espera_crece_exponencial_mas_jitter(self):
        self.assertEqual(backoff_seconds(1, rand=lambda: 0.0), 1)
        self.assertEqual(backoff_seconds(2, rand=lambda: 0.0), 2)
        self.assertEqual(backoff_seconds(3, rand=lambda: 0.5), 4.5)


class TestCallWithBackoff(unittest.TestCase):
    def setUp(self):
        self.waits = []

    def run_fn(self, fn, max_retries=2, max_wait_s=10):
        return call_with_backoff(fn, max_retries=max_retries, max_wait_s=max_wait_s, sleep=self.waits.append)

    def test_sin_errores_un_intento(self):
        self.assertEqual(self.run_fn(Script()), ("ok", 1))
        self.assertEqual(self.waits, [])

    def test_reintenta_error_transitorio(self):
        result = self.run_fn(Script(ServerError("x", "503")))
        self.assertEqual(result, ("ok", 2))
        self.assertEqual(len(self.waits), 1)

    def test_respeta_retry_after(self):
        self.run_fn(Script(RateLimitError("x", "429", retry_after=3.0)))
        self.assertEqual(self.waits, [3.0])

    def test_no_reintenta_error_no_transitorio(self):
        fn = Script(AuthError("x", "401"))
        with self.assertRaises(AuthError):
            self.run_fn(fn)
        self.assertEqual(fn.calls, 1)
        self.assertEqual(self.waits, [])

    def test_corta_si_pide_esperar_demasiado(self):
        fn = Script(RateLimitError("x", "429", retry_after=60.0))
        with self.assertRaises(RateLimitError):
            self.run_fn(fn, max_wait_s=10)
        self.assertEqual(self.waits, [])

    def test_se_agotan_los_reintentos(self):
        fn = Script(*[ServerError("x", "500") for _ in range(5)])
        with self.assertRaises(ServerError) as ctx:
            self.run_fn(fn, max_retries=2)
        self.assertEqual(fn.calls, 3)  # el primero + 2 reintentos
        self.assertEqual(ctx.exception.attempts, 3)


if __name__ == "__main__":
    unittest.main()
