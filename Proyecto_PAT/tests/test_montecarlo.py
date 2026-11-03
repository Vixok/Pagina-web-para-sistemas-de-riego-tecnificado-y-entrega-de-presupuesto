import unittest
import numpy as np
from simulacion_montecarlo import ParametrosMonteCarlo, simular_costos


class TestMonteCarlo(unittest.TestCase):
    def test_reproducible(self):
        comp = {"matriz": 100, "laterales": 200, "emisores": 300, "bombeo": 400,
                "filtracion": 50, "accesorios": 40, "obra_civil": 30, "instalacion": 100, "iva": 0}
        p = ParametrosMonteCarlo(n_iteraciones=1000, seed=123)
        a = simular_costos(comp, p)["muestras"]
        b = simular_costos(comp, p)["muestras"]
        self.assertTrue(np.array_equal(a, b))


if __name__ == "__main__":
    unittest.main()
