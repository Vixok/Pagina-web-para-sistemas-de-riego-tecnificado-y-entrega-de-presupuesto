"""Capa de mercado: Tavily / Mercado Libre -> validación -> SQL -> resumen estadístico."""
from __future__ import annotations

import math
import re
from datetime import datetime
import pandas as pd

from proveedor_tavily import buscar_precios_tavily
try:
    from proveedor_mercadolibre import buscar_productos_ml
except ImportError:
    buscar_productos_ml = None

from database import (
    guardar_cotizaciones_bomba,
    cotizacion_bomba_reciente,
    cargar_cotizaciones_bombas,
    guardar_candidato_web,
)

PALABRAS_DESCARTE = {
    "impulsor", "repuesto", "rodamiento", "sello mecanico", "sello mecánico",
    "motor solo", "motor electrico", "motor eléctrico", "carcasa", "eje",
    "etf", "acciones", "stock", "tokenized", "token", "fondo", "bomba de bicicleta",
}


def construir_consulta_bomba(candidato, caudal_requerido_ls, tdh_requerida_mca):
    hp = float(candidato.get("hp_unitario", candidato.get("potencia_hp", 0)) or 0)
    n_paralelo = max(1, int(candidato.get("n_paralelo", 1) or 1))
    n_serie = max(1, int(candidato.get("n_serie", 1) or 1))
    q_unidad = float(caudal_requerido_ls) / n_paralelo
    h_unidad = float(tdh_requerida_mca) / n_serie
    tipo = str(candidato.get("tipo", "bomba centrífuga"))
    voltaje = candidato.get("voltaje_v")
    voltaje_txt = f" {float(voltaje):g} V" if voltaje is not None else ""
    return (
        f"bomba {tipo} {hp:g} HP{voltaje_txt} "
        f"caudal aproximado {q_unidad:.1f} L/s altura aproximada {h_unidad:.1f} mca Chile"
    )


def _texto_resultado(resultado):
    return (str(resultado.get("Producto", "")) + " " + str(resultado.get("Contenido", ""))).lower()


def _extraer_hp(texto):
    patrones = [r"(\d+(?:[\.,]\d+)?)\s*hp\b", r"(\d+(?:[\.,]\d+)?)\s*cv\b"]
    for patron in patrones:
        m = re.search(patron, texto, re.I)
        if m:
            try:
                return float(m.group(1).replace(",", "."))
            except ValueError:
                pass
    return None


def _extraer_caudal_ls(texto):
    m = re.search(r"(\d+(?:[\.,]\d+)?)\s*l\s*/\s*s\b", texto, re.I)
    if m:
        return float(m.group(1).replace(",", "."))
    m = re.search(r"(\d+(?:[\.,]\d+)?)\s*(?:l/min|lpm)\b", texto, re.I)
    if m:
        return float(m.group(1).replace(",", ".")) / 60.0
    m = re.search(r"(\d+(?:[\.,]\d+)?)\s*m[³3]\s*/\s*h\b", texto, re.I)
    if m:
        return float(m.group(1).replace(",", ".")) / 3.6
    return None


def _extraer_altura_mca(texto):
    patrones = [
        r"(\d+(?:[\.,]\d+)?)\s*m\.?c\.?a\.?\b",
        r"altura[^\d]{0,15}(\d+(?:[\.,]\d+)?)\s*m\b",
        r"hmax[^\d]{0,10}(\d+(?:[\.,]\d+)?)\s*m\b",
    ]
    for patron in patrones:
        m = re.search(patron, texto, re.I)
        if m:
            try:
                return float(m.group(1).replace(",", "."))
            except ValueError:
                pass
    return None


def es_resultado_irrelevante(resultado):
    texto = _texto_resultado(resultado)
    return any(p in texto for p in PALABRAS_DESCARTE)


def calcular_score(resultado, candidato):
    texto = _texto_resultado(resultado)
    if es_resultado_irrelevante(resultado):
        return 0.0

    score = 0.0
    if "bomba" in texto:
        score += 20
    if "centrif" in texto:
        score += 10

    hp_obj = float(candidato.get("hp_unitario", candidato.get("potencia_hp", 0)) or 0)
    hp_detect = _extraer_hp(texto)
    if hp_obj > 0 and hp_detect is not None:
        error = abs(hp_detect - hp_obj) / hp_obj
        if error <= 0.10:
            score += 35
        elif error <= 0.25:
            score += 20
        elif error <= 0.50:
            score += 8

    tipo = str(candidato.get("tipo", "")).lower().strip()
    if tipo and any(p in texto for p in tipo.split() if len(p) >= 4):
        score += 10

    voltaje = candidato.get("voltaje_v")
    if voltaje is not None:
        patron_v = rf"(?<!\d){int(float(voltaje))}\s*v\b"
        if re.search(patron_v, texto, re.I):
            score += 5

    try:
        if float(resultado.get("Precio_CLP", 0) or 0) > 0:
            score += 10
    except (TypeError, ValueError):
        pass

    # Puntos extra por especificaciones hidráulicas detectables.
    if _extraer_caudal_ls(texto) is not None:
        score += 5
    if _extraer_altura_mca(texto) is not None:
        score += 5
    return min(score, 100.0)


def actualizar_mercado_bombas(candidatos, caudal_requerido_ls, tdh_requerida_mca,
                               max_candidatos=6, vigencia_horas=24):
    resumen = []
    for candidato in list(candidatos)[: int(max_candidatos)]:
        id_bomba = candidato.get("id_bomba")
        if id_bomba is None:
            resumen.append({"modelo": candidato.get("modelo"), "estado": "Sin id_bomba", "nuevos": 0})
            continue
        if cotizacion_bomba_reciente(id_bomba, horas=vigencia_horas):
            resumen.append({"id_bomba": id_bomba, "modelo": candidato.get("modelo"),
                            "estado": f"SQL vigente (< {vigencia_horas} h)", "nuevos": 0})
            continue

        consulta = construir_consulta_bomba(candidato, caudal_requerido_ls, tdh_requerida_mca)
        resultados, errores = [], []
        res_tv, err_tv = buscar_precios_tavily(consulta, max_resultados=6)
        resultados.extend(res_tv)
        if err_tv:
            errores.append(f"Tavily: {err_tv}")
        if buscar_productos_ml is not None:
            res_ml, err_ml = buscar_productos_ml(consulta, limite=6)
            resultados.extend(res_ml)
            if err_ml:
                errores.append(f"Mercado Libre: {err_ml}")

        validos = []
        for r in resultados:
            try:
                precio = float(r.get("Precio_CLP", 0) or 0)
            except (TypeError, ValueError):
                continue
            if precio <= 0 or es_resultado_irrelevante(r):
                continue
            r["Precio_CLP"] = precio
            r["Score"] = calcular_score(r, candidato)
            if r["Score"] >= 40:  # SQL decide validez estricta >=60.
                validos.append(r)

        insertados = guardar_cotizaciones_bomba(
            id_bomba, consulta, validos, caudal_requerido_ls, tdh_requerida_mca
        )
        resumen.append({
            "id_bomba": id_bomba,
            "modelo": candidato.get("modelo"),
            "estado": "Actualizado" if insertados else "Sin coincidencias válidas",
            "nuevos": insertados,
            "errores": " | ".join(errores) if errores else "",
            "consulta": consulta,
        })
    return resumen


def obtener_precios_mercado(horas=168):
    """Estadística representativa por bomba; mediana es el precio principal."""
    df = cargar_cotizaciones_bombas(horas=horas, solo_validas=True)
    if df.empty:
        return df
    df["precio_clp"] = pd.to_numeric(df["precio_clp"], errors="coerce")
    df["fecha_consulta"] = pd.to_datetime(df["fecha_consulta"], errors="coerce")
    df = df.dropna(subset=["precio_clp", "fecha_consulta"])
    if df.empty:
        return df

    # Filtro IQR por bomba cuando hay suficiente muestra; reduce falsos positivos de precio.
    partes = []
    for _, g in df.groupby("id_bomba"):
        if len(g) >= 4:
            q1, q3 = g["precio_clp"].quantile([0.25, 0.75])
            iqr = q3 - q1
            if iqr > 0:
                g2 = g[(g["precio_clp"] >= q1 - 1.5 * iqr) & (g["precio_clp"] <= q3 + 1.5 * iqr)]
                if not g2.empty:
                    g = g2
        partes.append(g)
    df = pd.concat(partes, ignore_index=True) if partes else df

    resumen = (
        df.groupby("id_bomba")
        .agg(
            precio_mercado_clp=("precio_clp", "median"),
            precio_promedio_clp=("precio_clp", "mean"),
            precio_min_clp=("precio_clp", "min"),
            precio_max_clp=("precio_clp", "max"),
            desviacion_precio_clp=("precio_clp", "std"),
            n_cotizaciones=("precio_clp", "count"),
            ultima_actualizacion=("fecha_consulta", "max"),
        )
        .reset_index()
    )
    ahora = pd.Timestamp.now()
    resumen["antiguedad_horas"] = (ahora - resumen["ultima_actualizacion"]).dt.total_seconds() / 3600.0
    resumen["vigencia"] = resumen["antiguedad_horas"].apply(
        lambda h: "FRESCO" if h <= 24 else "RECIENTE" if h <= 168 else "ANTIGUO"
    )
    resumen["desviacion_precio_clp"] = resumen["desviacion_precio_clp"].fillna(0.0)
    return resumen


def analizar_historial_precios(df_historial: pd.DataFrame) -> pd.DataFrame:
    if df_historial is None or df_historial.empty:
        return pd.DataFrame()
    df = df_historial.copy()
    df["fecha_consulta"] = pd.to_datetime(df["fecha_consulta"], errors="coerce")
    df["precio_clp"] = pd.to_numeric(df["precio_clp"], errors="coerce")
    df = df.dropna(subset=["fecha_consulta", "precio_clp"])
    filas = []
    ahora = df["fecha_consulta"].max()
    for id_bomba, g in df.groupby("id_bomba"):
        g = g.sort_values("fecha_consulta")
        mediana = float(g["precio_clp"].median())
        def variacion(dias):
            corte = ahora - pd.Timedelta(days=dias)
            viejo = g[g["fecha_consulta"] <= corte]
            if viejo.empty:
                return None
            base = float(viejo.iloc[-1]["precio_clp"])
            actual = float(g.iloc[-1]["precio_clp"])
            return ((actual / base) - 1.0) * 100 if base else None
        filas.append({
            "id_bomba": id_bomba,
            "mediana_clp": mediana,
            "variacion_7d_pct": variacion(7),
            "variacion_30d_pct": variacion(30),
            "volatilidad_pct": float(g["precio_clp"].std(ddof=0) / mediana * 100) if mediana else None,
            "n_observaciones": len(g),
        })
    return pd.DataFrame(filas)


def buscar_candidatos_web(caudal_requerido_ls, tdh_requerida_mca, potencia_aprox_hp=None, max_resultados=8):
    """Segunda capa: busca bombas externas y las deja PENDIENTE_HITL/REVISAR."""
    hp = potencia_aprox_hp or (float(caudal_requerido_ls) * float(tdh_requerida_mca) / (75 * 0.70))
    consulta = (
        f"bomba centrifuga riego {hp:.1f} HP caudal {float(caudal_requerido_ls):.1f} L/s "
        f"altura {float(tdh_requerida_mca):.1f} mca Chile"
    )
    resultados, errores = [], []
    res_tv, err_tv = buscar_precios_tavily(consulta, max_resultados=max_resultados)
    resultados.extend(res_tv)
    if err_tv:
        errores.append(f"Tavily: {err_tv}")
    if buscar_productos_ml is not None:
        res_ml, err_ml = buscar_productos_ml(consulta, limite=max_resultados)
        resultados.extend(res_ml)
        if err_ml:
            errores.append(f"Mercado Libre: {err_ml}")

    guardados = []
    for r in resultados:
        if es_resultado_irrelevante(r):
            continue
        texto = _texto_resultado(r)
        hp_d = _extraer_hp(texto)
        q_d = _extraer_caudal_ls(texto)
        h_d = _extraer_altura_mca(texto)
        score = 20 if "bomba" in texto else 0
        if hp_d is not None:
            score += 30 if abs(hp_d - hp) / max(hp, 0.1) <= 0.25 else 10
        if q_d is not None:
            score += 20
        if h_d is not None:
            score += 20
        try:
            precio = float(r.get("Precio_CLP"))
            if precio > 0:
                score += 10
        except Exception:
            precio = None
        estado = "PENDIENTE_HITL" if score >= 60 else "REVISAR"
        datos = {
            "producto": r.get("Producto"), "marca": None, "modelo_detectado": r.get("Producto"),
            "potencia_detectada_hp": hp_d, "caudal_detectado_ls": q_d,
            "altura_detectada_mca": h_d, "precio_clp": precio,
            "fuente": r.get("Fuente"), "url": r.get("URL"), "score_coincidencia": score,
            "consulta_busqueda": consulta, "estado": estado,
        }
        try:
            datos["id_candidato"] = guardar_candidato_web(datos)
            guardados.append(datos)
        except Exception as e:
            errores.append(f"SQL candidato: {e}")
    return guardados, errores
