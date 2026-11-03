import unittest
from pathlib import Path

import app
from streamlit.testing.v1 import AppTest


class TestPresupuestoObraCivil(unittest.TestCase):
    @staticmethod
    def calcular_cantidades(**cambios):
        datos = {
            "longitud_zanja_m": 10,
            "ancho_zanja_m": 0.5,
            "profundidad_zanja_m": 0.6,
            "volumen_relleno_m3": 2.5,
            "precio_excavacion_clp_m3": 5000,
            "fuente_excavacion": "ONDAC, edición y partida de excavación",
            "precio_relleno_clp_m3": 3000,
            "fuente_relleno": "Educandus, documento metodológico de relleno",
            "volumen_hormigon_anclajes_m3": 0.4,
            "precio_hormigon_clp_m3": 200000,
            "fuente_hormigon": "ONDAC, edición y partida de hormigón",
            "incluye_mano_obra_excavacion": True,
            "incluye_mano_obra_relleno": False,
            "incluye_mano_obra_hormigon": True,
        }
        datos.update(cambios)
        return app.calcular_obra_civil_cantidades(**datos)

    def test_longitudes_confirmadas_solo_incluyen_tramos_enterrados(self):
        resultado = app.clasificar_longitudes_tuberia_obra_civil(
            100,
            500,
            "Enterrado",
            "Superficial",
        )

        self.assertEqual(resultado["longitud_enterrada_confirmada_m"], 100)
        self.assertEqual(resultado["longitud_superficial_confirmada_m"], 500)
        self.assertEqual(resultado["longitud_pendiente_validacion_m"], 0)

    def test_longitudes_mixtas_suman_solo_la_parte_enterrada(self):
        resultado = app.clasificar_longitudes_tuberia_obra_civil(
            100,
            500,
            "Mixto",
            "Pendiente de validar",
            longitud_matriz_enterrada_mixta=35,
        )

        self.assertEqual(resultado["longitud_enterrada_confirmada_m"], 35)
        self.assertEqual(resultado["longitud_superficial_confirmada_m"], 65)
        self.assertEqual(resultado["longitud_pendiente_validacion_m"], 500)

    def test_pendiente_de_validar_no_se_cuenta_como_excavacion(self):
        resultado = app.clasificar_longitudes_tuberia_obra_civil(
            100,
            500,
            "Pendiente de validar",
            "Superficial",
        )

        self.assertEqual(resultado["longitud_enterrada_confirmada_m"], 0)
        self.assertEqual(resultado["longitud_pendiente_validacion_m"], 100)
        self.assertEqual(resultado["longitud_superficial_confirmada_m"], 500)

    def test_rechaza_longitud_mixta_ausente_o_fuera_del_total(self):
        for longitud in (None, 0, 100, 101):
            with self.subTest(longitud=longitud):
                with self.assertRaises(ValueError):
                    app.clasificar_longitudes_tuberia_obra_civil(
                        100,
                        500,
                        "Mixto",
                        "Superficial",
                        longitud_matriz_enterrada_mixta=longitud,
                    )

    def test_rechaza_longitudes_no_finitas_y_clasificaciones_invalidas(self):
        with self.assertRaisesRegex(ValueError, "finito"):
            app.clasificar_longitudes_tuberia_obra_civil(
                float("inf"),
                500,
                "Enterrado",
                "Superficial",
            )
        with self.assertRaisesRegex(ValueError, "Clasificación no válida"):
            app.clasificar_longitudes_tuberia_obra_civil(
                100,
                500,
                "Automático",
                "Superficial",
            )

    def test_excavacion_cubicada_usa_longitud_confirmada(self):
        tramos = app.clasificar_longitudes_tuberia_obra_civil(
            100,
            500,
            "Mixto",
            "Superficial",
            longitud_matriz_enterrada_mixta=35,
        )
        cantidades = self.calcular_cantidades(
            longitud_zanja_m=tramos["longitud_enterrada_confirmada_m"],
            ancho_zanja_m=0.4,
            profundidad_zanja_m=0.5,
            volumen_relleno_m3=5,
        )

        self.assertEqual(tramos["longitud_enterrada_confirmada_m"], 35)
        self.assertEqual(cantidades["volumen_excavacion_m3"], 7)

    def test_streamlit_permite_clasificar_tramos_y_muestra_longitud(self):
        app_test = AppTest.from_file(
            str(Path(app.__file__)),
            default_timeout=60,
        )
        for clave, valor in {
            "m_prin": 100.0,
            "m_lat": 500.0,
            "diametro_matriz": 50.0,
            "tot_emi": 100,
            "tecnica_riego": "Goteo",
        }.items():
            app_test.session_state[clave] = valor

        app_test.run()
        self.assertFalse(app_test.exception)
        selectores = {
            selector.key: selector for selector in app_test.selectbox
        }
        selectores["presupuesto_clasificacion_matriz"].set_value("Enterrado")
        selectores["presupuesto_clasificacion_laterales"].set_value(
            "Superficial"
        )
        app_test.run()

        self.assertFalse(app_test.exception)
        self.assertEqual(
            app_test.session_state[
                "clasificacion_tramos_obra_civil"
            ]["longitud_enterrada_confirmada_m"],
            100,
        )
        self.assertTrue(
            any(
                metric.label == "Longitud de excavación confirmada"
                for metric in app_test.metric
            )
        )

    @staticmethod
    def calcular_presupuesto(**cambios):
        argumentos = {
            "p_matriz": 100000,
            "p_lateral": 50000,
            "p_emi": 10000,
            "costo_bombas": 20000,
            "caudal_total_ls": 0,
            "pct_accesorios": 10,
            "pct_obra_civil": 5,
            "pct_instalacion": 20,
            "costo_filtro_manual": 0,
            "incluir_iva": False,
        }
        argumentos.update(cambios)
        return app.calcular_presupuesto_detallado(**argumentos)

    def test_calcula_excavacion_por_dimensiones_y_relleno_independiente(self):
        resultado = self.calcular_cantidades()

        self.assertEqual(resultado["volumen_excavacion_m3"], 3)
        self.assertEqual(resultado["volumen_relleno_m3"], 2.5)
        self.assertEqual(resultado["total"], 102500)
        self.assertEqual(
            [partida["Subtotal (CLP)"] for partida in resultado["partidas"]],
            [15000, 7500, 80000],
        )
        self.assertEqual(
            resultado["partidas"][0]["Fuente"],
            "ONDAC, edición y partida de excavación",
        )

    def test_referencial_conserva_el_calculo_porcentual(self):
        resultado = self.calcular_presupuesto()

        self.assertEqual(resultado["p_obra_civil_referencial"], 7500)
        self.assertEqual(resultado["p_obra_civil"], 7500)
        self.assertEqual(resultado["total"], 243000)
        self.assertEqual(resultado["metodo_obra_civil"], "porcentaje")

    def test_solo_incluye_el_metodo_seleccionado_y_no_duplica_mano_de_obra(self):
        cantidades = self.calcular_cantidades()
        resultado = self.calcular_presupuesto(
            metodo_obra_civil="cantidades",
            obra_civil_cantidades=cantidades,
        )

        self.assertEqual(resultado["p_obra_civil"], 102500)
        self.assertEqual(resultado["p_obra_civil_referencial"], 7500)
        self.assertEqual(resultado["base_instalacion"], 202500)
        self.assertEqual(resultado["p_instalacion"], 40500)
        self.assertEqual(resultado["total"], 338000)
        nombres = [item["Ítem"] for item in resultado["items"]]
        self.assertIn("Excavación de zanjas", nombres)
        self.assertIn("Relleno y compactación", nombres)
        self.assertIn("Hormigón para anclajes", nombres)
        self.assertFalse(any("referencial" in nombre for nombre in nombres))

    def test_rechaza_cantidades_negativas_y_dimensiones_cero(self):
        with self.assertRaisesRegex(ValueError, "no negativo"):
            self.calcular_cantidades(volumen_relleno_m3=-0.1)
        with self.assertRaisesRegex(ValueError, "mayores que cero"):
            self.calcular_cantidades(ancho_zanja_m=0)
        with self.assertRaisesRegex(ValueError, "no puede superar"):
            self.calcular_cantidades(volumen_relleno_m3=3.1)

    def test_rechaza_precio_negativo_o_sin_fuente(self):
        with self.assertRaisesRegex(ValueError, "no negativo"):
            self.calcular_cantidades(precio_excavacion_clp_m3=-1)
        with self.assertRaisesRegex(ValueError, "fuente verificable"):
            self.calcular_cantidades(fuente_excavacion="")

    def test_rechaza_cantidades_incompletas_y_totales_inconsistentes(self):
        with self.assertRaisesRegex(ValueError, "Falta ingresar"):
            self.calcular_cantidades(volumen_hormigon_anclajes_m3=None)

        cantidades = self.calcular_cantidades()
        cantidades["total"] += 1
        with self.assertRaisesRegex(ValueError, "no coincide"):
            self.calcular_presupuesto(
                metodo_obra_civil="cantidades",
                obra_civil_cantidades=cantidades,
            )


if __name__ == "__main__":
    unittest.main()
