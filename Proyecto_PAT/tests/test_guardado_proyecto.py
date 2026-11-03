import json
import unittest
from decimal import Decimal
from unittest.mock import patch

import numpy as np

import database


class TestGuardadoProyecto(unittest.TestCase):
    def test_insertar_proyecto_y_serializar_datos(self):
        datos = {
            "area_m2": np.float64(12500),
            "temporada": "Verano",
            "presupuesto": {
                "total_clp": Decimal("123456.50"),
                "presupuesto_detallado": {
                    "metodo_obra_civil": "cantidades",
                    "partidas_obra_civil": [
                        {
                            "Ítem": "Excavación de zanjas",
                            "Cantidad": 3.0,
                            "Unidad": "m³",
                            "Precio unitario (CLP/m³)": 5000.0,
                            "Fuente": "ONDAC, edición y partida",
                            "Fecha del precio": "2025-03-01",
                            "Incluye mano de obra": True,
                            "Subtotal (CLP)": 15000.0,
                        }
                    ],
                    "clasificacion_tramos_tuberia": {
                        "longitud_enterrada_confirmada_m": 10.0,
                        "longitud_pendiente_validacion_m": 4.0,
                    },
                },
            },
        }

        with patch("database.ejecutar_escritura", return_value=17) as ejecutar:
            id_proyecto = database.guardar_proyecto_disenio("Predio norte", datos)

        self.assertEqual(id_proyecto, 17)
        query, parametros = ejecutar.call_args.args
        self.assertIn("INSERT INTO dbo.Proyectos", query)
        self.assertEqual(parametros[0], "Predio norte")
        self.assertEqual(parametros[5], np.float64(12500))
        self.assertEqual(parametros[6], 1.25)
        self.assertEqual(
            json.loads(parametros[9]),
            {
                "area_m2": 12500.0,
                "temporada": "Verano",
                "presupuesto": {
                    "total_clp": 123456.5,
                    "presupuesto_detallado": {
                        "metodo_obra_civil": "cantidades",
                        "partidas_obra_civil": [
                            {
                                "Ítem": "Excavación de zanjas",
                                "Cantidad": 3.0,
                                "Unidad": "m³",
                                "Precio unitario (CLP/m³)": 5000.0,
                                "Fuente": "ONDAC, edición y partida",
                                "Fecha del precio": "2025-03-01",
                                "Incluye mano de obra": True,
                                "Subtotal (CLP)": 15000.0,
                            }
                        ],
                        "clasificacion_tramos_tuberia": {
                            "longitud_enterrada_confirmada_m": 10.0,
                            "longitud_pendiente_validacion_m": 4.0,
                        },
                    },
                },
            },
        )
        self.assertTrue(ejecutar.call_args.kwargs["devolver_id"])

    def test_actualizar_proyecto_existente(self):
        with patch("database.ejecutar_escritura", return_value=23) as ejecutar:
            id_proyecto = database.guardar_proyecto_disenio(
                "Predio actualizado",
                {"tecnica_riego": "Goteo"},
                id_proyecto=23,
            )

        self.assertEqual(id_proyecto, 23)
        query, parametros = ejecutar.call_args.args
        self.assertIn("UPDATE dbo.Proyectos", query)
        self.assertEqual(parametros[0], "Predio actualizado")
        self.assertEqual(parametros[-1], 23)
        self.assertTrue(ejecutar.call_args.kwargs["devolver_id"])

    def test_no_guarda_json_con_valores_no_finitos(self):
        with patch("database.ejecutar_escritura") as ejecutar:
            with self.assertRaises(ValueError):
                database.guardar_proyecto_disenio(
                    "Predio inválido",
                    {"valor": float("nan")},
                )

        ejecutar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
