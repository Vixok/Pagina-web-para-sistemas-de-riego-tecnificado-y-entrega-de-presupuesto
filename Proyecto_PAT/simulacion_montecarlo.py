"""Simulación Monte Carlo para costo del proyecto y, opcionalmente, desempeño."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional
import numpy as np
import pandas as pd


@dataclass
class ParametrosMonteCarlo:
    n_iteraciones: int = 5000
    seed: int = 42
    variacion_tuberias_pct: float = 10.0
    variacion_emisores_pct: float = 10.0
    variacion_instalacion_pct: float = 15.0
    variacion_obra_civil_pct: float = 20.0
    variacion_otros_pct: float = 10.0


def _triangular_factor(rng, pct, n):
    p = max(float(pct), 0.0) / 100.0
    return rng.triangular(1.0 - p, 1.0, 1.0 + p, size=n)


def _bootstrap_precios_bomba(rng, historial_precios, n, fallback):
    if historial_precios is None:
        return np.full(n, float(fallback))
    serie = pd.to_numeric(pd.Series(historial_precios), errors="coerce").dropna()
    serie = serie[serie > 0]
    if len(serie) < 3:
        return np.full(n, float(fallback))
    return rng.choice(serie.to_numpy(dtype=float), size=n, replace=True)


def simular_costos(componentes: dict, parametros: Optional[ParametrosMonteCarlo] = None,
                   historial_bomba=None, presupuesto_objetivo: Optional[float] = None):
    """Simula costos. Las distribuciones no ocultas quedan explicitadas en ``supuestos``.

    Para precio de bomba usa bootstrap empírico si hay >=3 observaciones válidas;
    en caso contrario mantiene el valor determinista.
    """
    p = parametros or ParametrosMonteCarlo()
    n = int(p.n_iteraciones)
    if n not in {1000, 5000, 10000}:
        n = max(100, n)
    rng = np.random.default_rng(int(p.seed))

    matriz = float(componentes.get("matriz", 0.0)) * _triangular_factor(rng, p.variacion_tuberias_pct, n)
    laterales = float(componentes.get("laterales", 0.0)) * _triangular_factor(rng, p.variacion_tuberias_pct, n)
    emisores = float(componentes.get("emisores", 0.0)) * _triangular_factor(rng, p.variacion_emisores_pct, n)
    bomba = _bootstrap_precios_bomba(rng, historial_bomba, n, componentes.get("bombeo", 0.0))
    filtracion = float(componentes.get("filtracion", 0.0)) * _triangular_factor(rng, p.variacion_otros_pct, n)
    accesorios = float(componentes.get("accesorios", 0.0)) * _triangular_factor(rng, p.variacion_otros_pct, n)
    obra = float(componentes.get("obra_civil", 0.0)) * _triangular_factor(rng, p.variacion_obra_civil_pct, n)
    instalacion = float(componentes.get("instalacion", 0.0)) * _triangular_factor(rng, p.variacion_instalacion_pct, n)
    iva = float(componentes.get("iva", 0.0)) * _triangular_factor(rng, 2.0, n)

    total = matriz + laterales + emisores + bomba + filtracion + accesorios + obra + instalacion + iva
    objetivo = float(presupuesto_objetivo) if presupuesto_objetivo is not None else None
    resumen = {
        "media": float(np.mean(total)),
        "desviacion": float(np.std(total, ddof=1)),
        "p05": float(np.percentile(total, 5)),
        "p10": float(np.percentile(total, 10)),
        "p50": float(np.percentile(total, 50)),
        "p80": float(np.percentile(total, 80)),
        "p90": float(np.percentile(total, 90)),
        "p95": float(np.percentile(total, 95)),
        "presupuesto_objetivo": objetivo,
        "prob_excedencia_pct": float(np.mean(total > objetivo) * 100.0) if objetivo is not None else None,
    }
    supuestos = {
        "tuberias": f"Triangular ±{p.variacion_tuberias_pct:.1f}%",
        "emisores": f"Triangular ±{p.variacion_emisores_pct:.1f}%",
        "instalacion": f"Triangular ±{p.variacion_instalacion_pct:.1f}%",
        "obra_civil": f"Triangular ±{p.variacion_obra_civil_pct:.1f}%",
        "otros": f"Triangular ±{p.variacion_otros_pct:.1f}%",
        "bombeo": "Bootstrap histórico si hay >=3 observaciones; si no, valor determinista",
        "seed": p.seed,
    }
    return {
        "muestras": total,
        "resumen": resumen,
        "parametros": asdict(p),
        "supuestos": supuestos,
    }
