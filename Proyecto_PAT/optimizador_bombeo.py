"""Motor determinista de selección hidráulica/económica de bombas.

Reglas:
- Nunca asume que Qmax y Hmax ocurren simultáneamente.
- Si existe curva Q-H validada, calcula el punto de operación contra la curva del sistema.
- Si no existe curva, solo genera una estimación preliminar usando límites de catálogo.
- Evalúa explícitamente configuraciones serie/paralelo.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Callable, Iterable, Optional
import math
import numpy as np
import pandas as pd


@dataclass
class ParametrosOptimizacion:
    max_paralelo: int = 10
    max_serie: int = 5
    max_total_bombas: int = 20
    margen_caudal: float = 1.10
    margen_altura: float = 1.00
    w_costo: float = 0.45
    w_numero: float = 0.15
    w_sobredim_q: float = 0.15
    w_sobredim_h: float = 0.15
    w_eficiencia: float = 0.10


@dataclass
class PuntoOperacion:
    caudal_ls: Optional[float]
    altura_mca: Optional[float]
    estado: str


def construir_curva_sistema(
    q_ref_ls: float,
    altura_estatica_m: float,
    presion_emisor_mca: float,
    perdida_friccion_ref_mca: float,
    perdida_accesorios_ref_mca: float,
) -> Callable[[float | np.ndarray], float | np.ndarray]:
    """Devuelve H_sistema(Q).

    La fricción distribuida se escala con Q^1.852 (Hazen-Williams) y
    las pérdidas menores con Q^2. En Q=q_ref reproduce el TDH de diseño.
    """
    q_ref_ls = max(float(q_ref_ls), 1e-9)
    h0 = max(float(altura_estatica_m), 0.0) + max(float(presion_emisor_mca), 0.0)
    hf_ref = max(float(perdida_friccion_ref_mca), 0.0)
    ha_ref = max(float(perdida_accesorios_ref_mca), 0.0)

    def h_sistema(q):
        q_arr = np.asarray(q, dtype=float)
        ratio = np.maximum(q_arr, 0.0) / q_ref_ls
        h = h0 + hf_ref * np.power(ratio, 1.852) + ha_ref * np.power(ratio, 2.0)
        if np.ndim(q) == 0:
            return float(h)
        return h

    return h_sistema


def _normalizar_curva(curva: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, Optional[np.ndarray]]:
    if curva is None or curva.empty:
        return np.array([]), np.array([]), None

    posibles_q = ["caudal_ls", "caudal_lmin", "q_ls", "q_lmin"]
    posibles_h = ["altura_mca", "h_mca", "altura"]
    posibles_eta = ["eficiencia_pct", "eficiencia"]

    q_col = next((c for c in posibles_q if c in curva.columns), None)
    h_col = next((c for c in posibles_h if c in curva.columns), None)
    eta_col = next((c for c in posibles_eta if c in curva.columns), None)
    if not q_col or not h_col:
        return np.array([]), np.array([]), None

    tmp = curva[[q_col, h_col] + ([eta_col] if eta_col else [])].copy()
    tmp[q_col] = pd.to_numeric(tmp[q_col], errors="coerce")
    tmp[h_col] = pd.to_numeric(tmp[h_col], errors="coerce")
    tmp = tmp.dropna(subset=[q_col, h_col]).sort_values(q_col)
    if tmp.empty:
        return np.array([]), np.array([]), None

    q = tmp[q_col].to_numpy(dtype=float)
    if q_col.endswith("lmin"):
        q = q / 60.0
    h = tmp[h_col].to_numpy(dtype=float)
    eta = None
    if eta_col:
        tmp[eta_col] = pd.to_numeric(tmp[eta_col], errors="coerce")
        eta = tmp[eta_col].to_numpy(dtype=float)
    return q, h, eta


def altura_configuracion(curva: pd.DataFrame, q_total_ls: float | np.ndarray, n_paralelo: int, n_serie: int):
    """H_config(Q) = n_serie * H_bomba(Q / n_paralelo).

    Fuera del rango de la curva devuelve NaN para evitar extrapolación agresiva.
    """
    q, h, _ = _normalizar_curva(curva)
    if len(q) < 2:
        if np.ndim(q_total_ls) == 0:
            return float("nan")
        return np.full_like(np.asarray(q_total_ls, dtype=float), np.nan)

    x = np.asarray(q_total_ls, dtype=float) / max(int(n_paralelo), 1)
    salida = np.interp(x, q, h, left=np.nan, right=np.nan) * max(int(n_serie), 1)
    if np.ndim(q_total_ls) == 0:
        return float(salida)
    return salida


def eficiencia_configuracion(curva: pd.DataFrame, q_total_ls: float, n_paralelo: int) -> Optional[float]:
    q, _, eta = _normalizar_curva(curva)
    if eta is None or len(q) < 2 or np.all(np.isnan(eta)):
        return None
    x = float(q_total_ls) / max(int(n_paralelo), 1)
    valid = ~np.isnan(eta)
    if valid.sum() < 2 or x < q[valid].min() or x > q[valid].max():
        return None
    return float(np.interp(x, q[valid], eta[valid]))


def buscar_punto_operacion(
    curva: pd.DataFrame,
    n_paralelo: int,
    n_serie: int,
    h_sistema: Callable[[float | np.ndarray], float | np.ndarray],
    n_muestras: int = 1500,
) -> PuntoOperacion:
    q, _, _ = _normalizar_curva(curva)
    if len(q) < 2:
        return PuntoOperacion(None, None, "SIN_CURVA")

    q_max_total = float(np.nanmax(q)) * max(int(n_paralelo), 1)
    if q_max_total <= 0:
        return PuntoOperacion(None, None, "CURVA_INVALIDA")

    qs = np.linspace(0.0, q_max_total, max(int(n_muestras), 100))
    hb = altura_configuracion(curva, qs, n_paralelo, n_serie)
    hs = np.asarray(h_sistema(qs), dtype=float)
    diff = hb - hs
    valid = np.isfinite(diff)
    if valid.sum() < 2:
        return PuntoOperacion(None, None, "SIN_INTERSECCION")

    idxs = np.where(valid[:-1] & valid[1:] & (diff[:-1] * diff[1:] <= 0))[0]
    if len(idxs) == 0:
        return PuntoOperacion(None, None, "SIN_INTERSECCION")

    # Para una curva centrífuga típica habrá una sola intersección.
    i = int(idxs[-1])
    q1, q2 = qs[i], qs[i + 1]
    d1, d2 = diff[i], diff[i + 1]
    if abs(d2 - d1) < 1e-12:
        q_op = (q1 + q2) / 2.0
    else:
        q_op = q1 - d1 * (q2 - q1) / (d2 - d1)

    h_op = float(h_sistema(q_op))
    return PuntoOperacion(float(q_op), h_op, "OK")


def _precio_fila(fila: pd.Series) -> Optional[float]:
    for c in ["precio_seleccion_clp", "precio_mercado_clp", "precio_ref_clp", "precio_clp"]:
        if c in fila.index and pd.notna(fila[c]):
            try:
                v = float(fila[c])
                if v > 0:
                    return v
            except (TypeError, ValueError):
                pass
    return None


def _curva_de_bomba(curvas: pd.DataFrame, id_bomba) -> pd.DataFrame:
    if curvas is None or curvas.empty or id_bomba is None or "id_bomba" not in curvas.columns:
        return pd.DataFrame()
    df = curvas[curvas["id_bomba"].astype(str) == str(id_bomba)].copy()
    if "validada" in df.columns:
        df = df[pd.to_numeric(df["validada"], errors="coerce").fillna(0).astype(int) == 1]
    if "activo" in df.columns:
        df = df[pd.to_numeric(df["activo"], errors="coerce").fillna(0).astype(int) == 1]
    return df


def _normalizar_scores(candidatos: list[dict], p: ParametrosOptimizacion) -> None:
    if not candidatos:
        return
    costos = [c["costo_total"] for c in candidatos if c.get("costo_total") not in (None, 0)]
    min_c, max_c = (min(costos), max(costos)) if costos else (None, None)
    max_n = max(c["n_total"] for c in candidatos) or 1

    for c in candidatos:
        if min_c is None or c.get("costo_total") is None:
            c_norm = 1.0
        else:
            rango = max(max_c - min_c, 1.0)
            c_norm = (c["costo_total"] - min_c) / rango
        n_norm = (c["n_total"] - 1) / max(max_n - 1, 1)
        sq = min(max(c.get("exceso_q_pct", 0.0), 0.0) / 100.0, 2.0)
        sh = min(max(c.get("exceso_h_pct", 0.0), 0.0) / 100.0, 2.0)
        eta = c.get("eficiencia_operacion_pct")
        if eta is None:
            eta_pen = 0.5
        else:
            eta_pen = max(0.0, min(1.0, (80.0 - float(eta)) / 40.0))
        c["score_balanceado"] = (
            p.w_costo * c_norm
            + p.w_numero * n_norm
            + p.w_sobredim_q * sq
            + p.w_sobredim_h * sh
            + p.w_eficiencia * eta_pen
        )


def optimizar_estacion_bombeo(
    caudal_requerido_ls: float,
    tdh_requerido_mca: float,
    df_bombas: pd.DataFrame,
    curvas: Optional[pd.DataFrame] = None,
    h_sistema: Optional[Callable[[float | np.ndarray], float | np.ndarray]] = None,
    criterio: str = "balanceado",
    parametros: Optional[ParametrosOptimizacion] = None,
) -> dict:
    """Evalúa todas las configuraciones serie/paralelo permitidas.

    Retorna un dict con ``mejor``, ``candidatos``, ``hay_validada`` y ``hay_preliminar``.
    """
    p = parametros or ParametrosOptimizacion()
    q_req = float(caudal_requerido_ls)
    h_req = float(tdh_requerido_mca)
    q_obj = q_req * p.margen_caudal
    h_obj = h_req * p.margen_altura
    candidatos: list[dict] = []

    if df_bombas is None or df_bombas.empty:
        return {"mejor": None, "candidatos": [], "hay_validada": False, "hay_preliminar": False}

    for _, fila in df_bombas.iterrows():
        try:
            id_bomba = int(fila["id_bomba"]) if pd.notna(fila.get("id_bomba")) else None
            modelo = str(fila.get("modelo") or fila.get("codigo_bomba") or "Bomba")
            qmax_ls = float(fila.get("caudal_max_lmin", 0) or 0) / 60.0
            hmax = float(fila.get("altura_max_mca", 0) or 0)
            hp = float(fila.get("potencia_hp", 0) or 0)
        except (TypeError, ValueError):
            continue
        if qmax_ls <= 0 or hmax <= 0 or hp <= 0:
            continue

        curva = _curva_de_bomba(curvas, id_bomba)
        curva_valida = len(_normalizar_curva(curva)[0]) >= 3 and h_sistema is not None
        precio = _precio_fila(fila)
        eta_catalogo = None
        try:
            if pd.notna(fila.get("eficiencia_pct")):
                eta_catalogo = float(fila.get("eficiencia_pct"))
        except (TypeError, ValueError):
            pass

        for np_ in range(1, p.max_paralelo + 1):
            for ns_ in range(1, p.max_serie + 1):
                n_total = np_ * ns_
                if n_total > p.max_total_bombas:
                    continue

                base = {
                    "id_bomba": id_bomba,
                    "modelo": modelo,
                    "tipo": str(fila.get("tipo") or "Bomba"),
                    "n_paralelo": np_,
                    "n_serie": ns_,
                    "n_total": n_total,
                    "hp_unitario": hp,
                    "hp_total": hp * n_total,
                    "precio_unitario": precio,
                    "costo_total": precio * n_total if precio is not None else None,
                    "precio_mercado_clp": float(fila.get("precio_mercado_clp")) if pd.notna(fila.get("precio_mercado_clp")) else None,
                    "precio_ref_clp": float(fila.get("precio_ref_clp")) if pd.notna(fila.get("precio_ref_clp")) else None,
                    "n_cotizaciones": int(fila.get("n_cotizaciones") or 0) if pd.notna(fila.get("n_cotizaciones")) else 0,
                    "ultima_actualizacion": fila.get("ultima_actualizacion"),
                    "eficiencia_catalogo_pct": eta_catalogo,
                }

                if curva_valida:
                    po = buscar_punto_operacion(curva, np_, ns_, h_sistema)
                    if po.estado != "OK" or po.caudal_ls is None:
                        continue
                    eta_op = eficiencia_configuracion(curva, po.caudal_ls, np_)
                    cumple = po.caudal_ls >= q_obj and po.altura_mca >= h_obj
                    exceso_q = max(0.0, (po.caudal_ls - q_obj) / max(q_obj, 1e-9) * 100)
                    exceso_h = max(0.0, (po.altura_mca - h_obj) / max(h_obj, 1e-9) * 100)
                    estado = "VALIDADA" if cumple else "NO_FACTIBLE"
                    base.update({
                        "curva_validada": True,
                        "estado_validacion": estado,
                        "q_operacion_ls": po.caudal_ls,
                        "h_operacion_mca": po.altura_mca,
                        "q_capacidad_preliminar_ls": qmax_ls * np_,
                        "h_capacidad_preliminar_mca": hmax * ns_,
                        "exceso_q_pct": exceso_q,
                        "exceso_h_pct": exceso_h,
                        "eficiencia_operacion_pct": eta_op if eta_op is not None else eta_catalogo,
                    })
                    if cumple:
                        candidatos.append(base)
                else:
                    q_cap = qmax_ls * np_
                    h_cap = hmax * ns_
                    cumple = q_cap >= q_obj and h_cap >= h_obj
                    if not cumple:
                        continue
                    base.update({
                        "curva_validada": False,
                        "estado_validacion": "ESTIMACION_PRELIMINAR",
                        "q_operacion_ls": None,
                        "h_operacion_mca": None,
                        "q_capacidad_preliminar_ls": q_cap,
                        "h_capacidad_preliminar_mca": h_cap,
                        "exceso_q_pct": max(0.0, (q_cap - q_obj) / max(q_obj, 1e-9) * 100),
                        "exceso_h_pct": max(0.0, (h_cap - h_obj) / max(h_obj, 1e-9) * 100),
                        "eficiencia_operacion_pct": eta_catalogo,
                    })
                    candidatos.append(base)

    if not candidatos:
        return {"mejor": None, "candidatos": [], "hay_validada": False, "hay_preliminar": False}

    _normalizar_scores(candidatos, p)
    validados = [c for c in candidatos if c["curva_validada"]]
    pool = validados if validados else candidatos

    if criterio == "menor_costo":
        key = lambda c: (c["costo_total"] if c["costo_total"] is not None else float("inf"), c["n_total"], c["score_balanceado"])
    elif criterio == "menor_numero":
        key = lambda c: (c["n_total"], c["costo_total"] if c["costo_total"] is not None else float("inf"), c["score_balanceado"])
    else:
        key = lambda c: (c["score_balanceado"], c["costo_total"] if c["costo_total"] is not None else float("inf"))

    pool.sort(key=key)
    mejor = dict(pool[0])
    if mejor["n_serie"] > 1 and mejor["n_paralelo"] > 1:
        mejor["config_texto"] = f"{mejor['n_paralelo']} ramas en PARALELO × {mejor['n_serie']} bombas en SERIE"
    elif mejor["n_serie"] > 1:
        mejor["config_texto"] = f"{mejor['n_serie']} bombas en SERIE"
    elif mejor["n_paralelo"] > 1:
        mejor["config_texto"] = f"{mejor['n_paralelo']} bombas en PARALELO"
    else:
        mejor["config_texto"] = "1 sola bomba"

    return {
        "mejor": mejor,
        "candidatos": sorted(candidatos, key=lambda c: (not c["curva_validada"], c["score_balanceado"])),
        "hay_validada": bool(validados),
        "hay_preliminar": bool(candidatos),
        "parametros": asdict(p),
    }


def datos_grafico_operacion(
    curva: pd.DataFrame,
    n_paralelo: int,
    n_serie: int,
    h_sistema: Callable[[float | np.ndarray], float | np.ndarray],
    n_puntos: int = 200,
) -> pd.DataFrame:
    q, _, _ = _normalizar_curva(curva)
    if len(q) < 2:
        return pd.DataFrame()
    qmax = float(np.nanmax(q)) * max(int(n_paralelo), 1)
    qs = np.linspace(0, qmax, n_puntos)
    hb = altura_configuracion(curva, qs, n_paralelo, n_serie)
    hs = h_sistema(qs)
    return pd.DataFrame({"caudal_ls": qs, "bomba_mca": hb, "sistema_mca": hs})
