import unittest
import pandas as pd

from optimizador_bombeo import (
    ParametrosOptimizacion,
    construir_curva_sistema,
    optimizar_estacion_bombeo,
)


class TestOptimizadorBombeo(unittest.TestCase):
    def setUp(self):
        self.bombas = pd.DataFrame([{
            "id_bomba": 1,
            "codigo_bomba": "TEST-01",
            "modelo": "TEST-01",
            "tipo": "Centrifuga",
            "caudal_max_lmin": 20 * 60,
            "altura_max_mca": 60,
            "potencia_hp": 10,
            "eficiencia_pct": 75,
            "precio_ref_clp": 100000,
        }])
        # Curva real sintética SOLO para pruebas: H = 60 - 2Q, Q en L/s.
        # No se carga en producción ni SQL.
        self.curvas = pd.DataFrame([
            {"id_bomba": 1, "caudal_lmin": q * 60, "altura_mca": 60 - 2*q, "eficiencia_pct": 75}
            for q in [0, 5, 10, 15, 20]
        ])
        self.p = ParametrosOptimizacion(
            max_paralelo=5, max_serie=2, max_total_bombas=12,
            margen_caudal=1.0, margen_altura=1.0,
        )

    def _opt(self, q_req, h0):
        hs = construir_curva_sistema(q_req, h0, 0, 0, 0)
        return optimizar_estacion_bombeo(
            q_req, h0, self.bombas, self.curvas, hs,
            criterio="menor_numero", parametros=self.p,
        )["mejor"]

    def test_1p_1s(self):
        r = self._opt(5, 20)
        self.assertEqual((r["n_paralelo"], r["n_serie"]), (1, 1))
        self.assertTrue(r["curva_validada"])

    def test_paralelo(self):
        r = self._opt(25, 20)
        self.assertEqual((r["n_paralelo"], r["n_serie"]), (2, 1))

    def test_serie(self):
        r = self._opt(5, 80)
        self.assertEqual((r["n_paralelo"], r["n_serie"]), (1, 2))

    def test_mixto(self):
        r = self._opt(18, 80)
        self.assertEqual((r["n_paralelo"], r["n_serie"]), (2, 2))


if __name__ == "__main__":
    unittest.main()
