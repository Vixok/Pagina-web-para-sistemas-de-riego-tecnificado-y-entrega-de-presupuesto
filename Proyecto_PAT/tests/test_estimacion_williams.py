import unittest

import pandas as pd

from estimacion_costos import estimar_costo_bomba_williams


class TestEstimacionWilliams(unittest.TestCase):
    def test_estima_costo_y_rango_con_exponente_de_bombas(self):
        bombas = pd.DataFrame(
            [
                {
                    "modelo": "Referencia",
                    "caudal_max_lmin": 300,
                    "precio_ref_clp": 300000,
                }
            ]
        )

        resultado = estimar_costo_bomba_williams(10, bombas)

        self.assertEqual(resultado["modelo_referencia"], "Referencia")
        self.assertAlmostEqual(resultado["caudal_referencia_ls"], 5)
        self.assertAlmostEqual(resultado["costo_estimado_clp"], 300000 * 2**0.6)
        self.assertAlmostEqual(resultado["rango_min_clp"], 300000 * 2**0.52)
        self.assertAlmostEqual(resultado["rango_max_clp"], 300000 * 2**0.76)
        self.assertEqual(resultado["exponente_williams"], 0.6)

    def test_prefiere_precio_de_mercado_sobre_catalogo(self):
        bombas = pd.DataFrame(
            [
                {
                    "modelo": "Referencia",
                    "caudal_max_lmin": 300,
                    "precio_mercado_clp": 250000,
                    "precio_ref_clp": 300000,
                }
            ]
        )

        resultado = estimar_costo_bomba_williams(5, bombas)

        self.assertEqual(resultado["costo_estimado_clp"], 250000)
        self.assertEqual(
            resultado["fuente_precio_referencia"],
            "mediana de mercado reciente en SQL",
        )

    def test_no_estima_si_falta_referencia_utilizable(self):
        bombas = pd.DataFrame(
            [{"modelo": "Sin precio", "caudal_max_lmin": 300, "precio_ref_clp": 0}]
        )

        self.assertIsNone(estimar_costo_bomba_williams(5, bombas))
        self.assertIsNone(estimar_costo_bomba_williams(0, bombas))


if __name__ == "__main__":
    unittest.main()
