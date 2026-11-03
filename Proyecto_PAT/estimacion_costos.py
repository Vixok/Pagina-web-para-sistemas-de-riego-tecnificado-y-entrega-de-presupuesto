"""Estimaciones referenciales de costos de equipos."""
from __future__ import annotations

import math

import pandas as pd


EXPONENTE_WILLIAMS = 0.6
RANGO_EXPONENTE_BOMBAS = (0.52, 0.76)


def estimar_costo_bomba_williams(caudal_objetivo_ls: float, bombas: pd.DataFrame):
    """Estima costo por caudal usando una bomba del catálogo como referencia.

    El precio de mercado reciente tiene prioridad sobre el precio de catálogo.
    Retorna None si no existe una referencia con caudal y costo positivos.
    """
    try:
        q_objetivo = float(caudal_objetivo_ls)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(q_objetivo) or q_objetivo <= 0:
        return None
    if bombas is None or bombas.empty:
        return None

    referencias = []
    for _, fila in bombas.iterrows():
        try:
            q_referencia = float(fila.get("caudal_max_lmin")) / 60.0
        except (TypeError, ValueError):
            continue
        if not math.isfinite(q_referencia) or q_referencia <= 0:
            continue

        precio = None
        fuente_precio = None
        for columna, fuente in (
            ("precio_mercado_clp", "mediana de mercado reciente en SQL"),
            ("precio_ref_clp", "precio de referencia del catálogo SQL"),
        ):
            try:
                candidato = float(fila.get(columna))
            except (TypeError, ValueError):
                continue
            if math.isfinite(candidato) and candidato > 0:
                precio = candidato
                fuente_precio = fuente
                break
        if precio is None:
            continue

        referencias.append(
            {
                "modelo_referencia": str(
                    fila.get("modelo") or fila.get("codigo_bomba") or "Bomba catálogo"
                ),
                "caudal_referencia_ls": q_referencia,
                "precio_referencia_clp": precio,
                "fuente_precio_referencia": fuente_precio,
                "distancia_capacidad": abs(math.log(q_objetivo / q_referencia)),
            }
        )

    if not referencias:
        return None

    referencia = min(referencias, key=lambda item: item["distancia_capacidad"])
    razon_caudales = q_objetivo / referencia["caudal_referencia_ls"]
    precio_base = referencia["precio_referencia_clp"]
    estimacion = precio_base * razon_caudales**EXPONENTE_WILLIAMS
    extremos = [
        precio_base * razon_caudales**n
        for n in RANGO_EXPONENTE_BOMBAS
    ]
    referencia.pop("distancia_capacidad")
    return {
        **referencia,
        "caudal_objetivo_ls": q_objetivo,
        "exponente_williams": EXPONENTE_WILLIAMS,
        "costo_estimado_clp": estimacion,
        "rango_min_clp": min(extremos),
        "rango_max_clp": max(extremos),
        "metodo": "Williams (exponente central 0,6; rango bombas 0,52–0,76)",
    }
