# streamlit run app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import math
import json
import requests 
from pathlib import Path
from datetime import date
from shapely.geometry import Polygon
from database import (
    consulta_dataframe,
    cargar_curvas_bombas,
    cargar_historial_precios_bomba,
    crear_proyecto_sesion,
    guardar_proyecto_con_presupuesto,
    guardar_ejecucion_agente,
    crear_aprobacion_hitl,
    resolver_aprobacion_hitl,
    guardar_resumen_montecarlo,
    cargar_candidatos_web,
    resolver_candidato_web,
    promover_candidato_a_bomba,
    listar_proyectos_disenio,
    cargar_proyecto_disenio,
)

from mercado_equipos import (
    actualizar_mercado_bombas, obtener_precios_mercado, analizar_historial_precios,
    buscar_candidatos_web,
)
from optimizador_bombeo import (
    ParametrosOptimizacion, construir_curva_sistema, optimizar_estacion_bombeo,
    datos_grafico_operacion,
)
from agente_riego import (analizar_configuracion, evaluar_con_judge,)
from simulacion_montecarlo import ParametrosMonteCarlo, simular_costos
from estimacion_costos import estimar_costo_bomba_williams
from ubicacion_predio import (
    identificar_ubicacion_predio,
    normalizar_nombre_administrativo,
)
# LIBRERÍAS GIS
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw, Geocoder, Fullscreen

try:
    from proveedor_mercadolibre import buscar_productos_ml
except ImportError:
    buscar_productos_ml = None
try:
    from proveedor_tavily import buscar_precios_tavily
except ImportError:
    buscar_precios_tavily = None

# ==========================================
# BLOQUE 1: CONFIGURACIÓN GENERAL Y CSS
# ==========================================
st.set_page_config(page_title="Diseño de Riego Agrícola", page_icon="🌱", layout="wide")

PRIMARY = "#4CAF50"
PRIMARY_DARK = "#2e7d32"
ACCENT = "#29b6f6"
BG_CARD = "#161b22"
BG_CARD_BORDER = "#2a3441"
WARN = "#f0a020"
BAD = "#e5484d"
GOOD = "#3ecf8e"

st.markdown(
    f"""
    <style>
    /* 1. Ocultar el encabezado nativo de Streamlit */
    header[data-testid="stHeader"] {{
        display: none !important;
    }}
    
    .main {{
        overflow: visible !important;
    }}
    .main .block-container {{
        padding-top: 0.5rem !important;
        overflow: visible !important;
    }}

    /* 2. Fijar el título principal arriba del todo */
    div.element-container:has(.encabezado-fijo) {{
        position: sticky;
        top: 0;
        z-index: 99999;
        background-color: #0e1117;
        padding-top: 0.5rem;
        padding-bottom: 0rem;
    }}

    .encabezado-fijo {{
        background: #10151c;
        padding: 10px 14px;
        border-radius: 10px;
        border: 1px solid {BG_CARD_BORDER};
        border-bottom: 3px solid {PRIMARY};
        box-shadow: 0 4px 14px rgba(0,0,0,0.8);
    }}
    .encabezado-fijo h1 {{
        margin: 0; padding: 0; font-size: 1.3rem;
        background: linear-gradient(90deg, {PRIMARY} 0%, {ACCENT} 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
    }}
    .encabezado-fijo p {{ margin: 2px 0 0 0; color: #9aa7b5; font-size: 0.8rem; }}

    /* 3. Fijar las pestañas (Tabs) de manera independiente justo debajo del título */
    [data-testid="stTabs"] {{
        position: sticky !important;
        top: 4.8rem !important;
        z-index: 99998 !important;
        background-color: #0e1117 !important;
        padding-top: 6px;
        padding-bottom: 6px;
        margin-top: 4px;
    }}

    [data-testid="stTabs"] > div:first-child {{
        background-color: #0e1117 !important;
    }}

    /* --- ESTILOS DE TARJETAS Y COMPONENTES --- */
    .kpi-card {{
        background: {BG_CARD};
        border: 1px solid {BG_CARD_BORDER};
        border-radius: 14px;
        padding: 16px 18px;
        margin-bottom: 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.25);
        transition: transform 0.15s ease;
    }}
    .kpi-card:hover {{ transform: translateY(-2px); border-color: {PRIMARY}; }}
    .kpi-label {{
        color: #c7d0d9; font-size: 0.78rem; text-transform: uppercase;
        letter-spacing: .06em; font-weight: 600; margin-bottom: 6px;
    }}
    .kpi-value {{ font-size: 1.55rem; font-weight: 800; color: #eef2f6; line-height: 1.15; }}
    .kpi-sub {{ font-size: 0.8rem; color: #aeb9c5; margin-top: 4px; }}
    .kpi-good {{ border-left: 4px solid {GOOD}; }}
    .kpi-warn {{ border-left: 4px solid {WARN}; }}
    .kpi-bad {{ border-left: 4px solid {BAD}; }}
    .kpi-neutral {{ border-left: 4px solid {ACCENT}; }}

    .status-banner {{
        border-radius: 12px; padding: 14px 18px; font-weight: 600;
        display: flex; align-items: center; gap: 10px; margin: 10px 0 4px 0;
        border: 1px solid;
    }}
    .status-good {{ background: rgba(62,207,142,0.10); border-color: {GOOD}; color: {GOOD}; }}
    .status-warn {{ background: rgba(240,160,32,0.10); border-color: {WARN}; color: {WARN}; }}
    .status-bad  {{ background: rgba(229,72,77,0.10); border-color: {BAD}; color: {BAD}; }}

    .section-title {{
        font-size: 1.05rem; font-weight: 700; color: #eef2f6;
        border-bottom: 1px solid {BG_CARD_BORDER}; padding-bottom: 6px; margin: 6px 0 14px 0;
    }}

    [data-testid="stTabs"] [role="tablist"] {{ gap: 4px; }}
    [data-testid="stTabs"] [role="tab"] {{
        background-color: {BG_CARD}; border-radius: 10px 10px 0 0; padding: 8px 14px;
        border: 1px solid {BG_CARD_BORDER}; border-bottom: none;
        color: #c7d0d9 !important;
    }}
    [data-testid="stTabs"] [role="tab"][aria-selected="true"] {{
        background-color: {PRIMARY_DARK} !important;
        color: #ffffff !important;
    }}
    [data-testid="stTabs"] [role="tab"][aria-selected="true"] p {{
        color: #ffffff !important;
    }}

    .pump-card {{
        background: linear-gradient(135deg, rgba(76,175,80,0.10), rgba(41,182,246,0.06));
        border: 1px solid {PRIMARY}; border-radius: 16px; padding: 20px 22px; margin: 8px 0 16px 0;
    }}
    .pump-title {{ font-size: 1.15rem; font-weight: 800; color: #74d680; margin-bottom: 4px; }}
    .pump-detail {{ color: #c7d0d9; font-size: 0.92rem; line-height: 1.6; }}

    /* --- PRESUPUESTO PROFESIONAL --- */
    .budget-shell {{
        background: linear-gradient(180deg, rgba(22,27,34,.92), rgba(14,17,23,.92));
        border: 1px solid #2a3441;
        border-radius: 16px;
        padding: 16px 18px;
        margin: 8px 0 14px 0;
        box-shadow: 0 6px 18px rgba(0,0,0,.22);
    }}
    .budget-heading {{
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:12px;
        margin-bottom:12px;
    }}
    .budget-heading-title {{
        font-size:1.02rem;
        font-weight:800;
        color:#eef2f6;
    }}
    .budget-heading-sub {{
        color:#9aa7b5;
        font-size:.80rem;
        margin-top:2px;
    }}
    .budget-kpi {{
        min-height:118px;
        background:#161b22;
        border:1px solid #2a3441;
        border-top:3px solid var(--budget-accent, #29b6f6);
        border-radius:14px;
        padding:14px 14px 12px 14px;
        box-shadow:0 3px 10px rgba(0,0,0,.18);
    }}
    .budget-kpi.total {{
        background:linear-gradient(135deg, rgba(46,125,50,.34), rgba(22,27,34,.96));
        border-color:#3ecf8e;
    }}
    .budget-kpi-label {{
        color:#aeb9c5;
        font-size:.72rem;
        text-transform:uppercase;
        letter-spacing:.055em;
        font-weight:700;
        margin-bottom:8px;
    }}
    .budget-kpi-value {{
        color:#f3f6f9;
        font-size:1.30rem;
        font-weight:850;
        line-height:1.15;
    }}
    .budget-kpi-sub {{
        color:#8f9ba8;
        font-size:.74rem;
        margin-top:7px;
    }}
    .budget-badges {{
        display:flex;
        flex-wrap:wrap;
        gap:8px;
        justify-content:flex-end;
        margin:4px 0 10px 0;
    }}
    .budget-badge {{
        display:inline-block;
        padding:6px 10px;
        border:1px solid #2a3441;
        border-radius:999px;
        background:#111821;
        color:#cbd5df;
        font-size:.75rem;
        font-weight:650;
    }}
    .budget-badge.good {{
        border-color:#2e7d32;
        background:rgba(46,125,50,.14);
        color:#7ee787;
    }}
    .budget-badge.warn {{
        border-color:#8a5a0a;
        background:rgba(240,160,32,.10);
        color:#f0b24b;
    }}
    .agent-summary-card {{
        background:linear-gradient(135deg, rgba(46,125,50,.15), rgba(22,27,34,.96));
        border:1px solid #2e7d32;
        border-radius:14px;
        padding:14px 16px;
        min-height:150px;
    }}
    .agent-risk-card {{
        background:#161b22;
        border:1px solid #3a3030;
        border-radius:14px;
        padding:14px 16px;
        min-height:150px;
    }}
    .agent-title {{
        font-weight:800;
        color:#7ee787;
        margin-bottom:8px;
    }}
    .agent-risk-title {{
        font-weight:800;
        color:#f0b24b;
        margin-bottom:8px;
    }}
    .source-card {{
        background:#121820;
        border:1px solid #2a3441;
        border-radius:12px;
        padding:11px 12px;
        min-height:78px;
    }}
    .source-title {{
        color:#eef2f6;
        font-weight:750;
        font-size:.86rem;
    }}
    .source-sub {{
        color:#8f9ba8;
        font-size:.72rem;
        margin-top:4px;
    }}

    </style>
    """, unsafe_allow_html=True)

def kpi_card(label, value, sub="", tono="neutral"):
    st.markdown(f"""<div class="kpi-card kpi-{tono}"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div><div class="kpi-sub">{sub}</div></div>""", unsafe_allow_html=True)

def status_banner(texto, tono="good", icono="✅"):
    st.markdown(f"""<div class="status-banner status-{tono}">{icono} {texto}</div>""", unsafe_allow_html=True)

def section_title(texto):
    st.markdown(f"""<div class="section-title">{texto}</div>""", unsafe_allow_html=True)


PEDROLLO_EN733_URL = (
    "https://www.pedrollo.com/es/product/superficie/"
    "centrifugas-normalizadas/monobloque-normalizadas-en-733/f/"
)


def budget_kpi_card(label, value, sub="", accent="#29b6f6", total=False):
    clase_total = " total" if total else ""
    st.markdown(
        f"""
        <div class="budget-kpi{clase_total}" style="--budget-accent:{accent};">
            <div class="budget-kpi-label">{label}</div>
            <div class="budget-kpi-value">{value}</div>
            <div class="budget-kpi-sub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _lista_texto_segura(valor):
    """Normaliza observaciones del agente sin asumir un esquema rígido."""
    if valor is None:
        return []
    if isinstance(valor, str):
        texto = valor.strip()
        return [texto] if texto else []
    if isinstance(valor, dict):
        return [f"{k}: {v}" for k, v in valor.items()]
    if isinstance(valor, (list, tuple, set)):
        return [str(v).strip() for v in valor if str(v).strip()]
    return [str(valor)]


def _extraer_ajustes_presupuesto_agente(resultado):
    """
    Extrae únicamente ajustes presupuestarios permitidos.
    Nunca se aplican sin una acción HITL explícita.
    """
    if not isinstance(resultado, dict):
        return {}

    candidatos = resultado.get("ajustes_presupuesto")
    if not isinstance(candidatos, dict):
        candidatos = resultado.get("ajustes_recomendados")
    if not isinstance(candidatos, dict):
        return {}

    alias = {
        "pct_accesorios": "presupuesto_pct_accesorios",
        "porcentaje_accesorios": "presupuesto_pct_accesorios",
        "pct_obra_civil": "presupuesto_pct_obra_civil",
        "porcentaje_obra_civil": "presupuesto_pct_obra_civil",
        "pct_instalacion": "presupuesto_pct_instalacion",
        "porcentaje_instalacion": "presupuesto_pct_instalacion",
        "costo_filtro_clp": "costo_filtro_override",
        "costo_filtrado_clp": "costo_filtro_override",
    }

    ajustes = {}
    for clave, valor in candidatos.items():
        destino = alias.get(str(clave).strip().lower())
        if destino is None:
            continue
        try:
            numero = float(valor)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(numero):
            continue
        if destino.startswith("presupuesto_pct_"):
            if 0 <= numero <= 100:
                ajustes[destino] = numero
        elif numero >= 0:
            ajustes[destino] = numero
    return ajustes

PAT_TAB_LABELS = (
    "📍 1. Diseño del Terreno",
    "💧 2. Análisis Hidráulico",
    "⚙️ 3. Selección de Equipos",
    "💰 4. Presupuesto",
    "📊 5. Bases de Datos",
    "🎲 6. Monte Carlo",
)
PAT_TAB_NAMES = (
    "Diseño del Terreno",
    "Análisis Hidráulico",
    "Selección de Equipos",
    "Presupuesto",
    "Bases de Datos",
    "Monte Carlo",
)


def _seleccionar_pestana_pat(etiqueta):
    st.session_state["pat_tab_activa"] = etiqueta


def _mostrar_navegacion_pat(paso):
    anterior, indicador, siguiente = st.columns([1, 1, 2])
    with anterior:
        st.button(
            "← Anterior",
            key=f"pat_nav_anterior_{paso}",
            disabled=paso == 0,
            on_click=_seleccionar_pestana_pat,
            args=(PAT_TAB_LABELS[max(paso - 1, 0)],),
        )
    with indicador:
        st.caption(f"Paso {paso + 1} de {len(PAT_TAB_LABELS)}")
    with siguiente:
        destino = min(paso + 1, len(PAT_TAB_LABELS) - 1)
        st.button(
            f"Siguiente: {PAT_TAB_NAMES[destino]}",
            key=f"pat_nav_siguiente_{paso}",
            disabled=paso == len(PAT_TAB_LABELS) - 1,
            on_click=_seleccionar_pestana_pat,
            args=(PAT_TAB_LABELS[destino],),
            type="primary",
        )

# ==========================================
# FUNCIONES MATEMÁTICAS Y BASE DE DATOS
# ==========================================
@st.cache_data(ttl=300)
def cargar_bases_de_datos():
    """Carga los catálogos activos desde SQL Server y normaliza tipos numéricos."""

    tub = consulta_dataframe(
        """
        SELECT
            codigo_tubo,
            material,
            diametro_nominal_mm AS diametro_mm,
            diametro_interior_mm,
            coef_hazen,
            precio_metro_clp AS costo_metro_clp,
            presion_nominal,
            rugosidad_mm
        FROM Tuberias
        WHERE activo = 1
        """
    )

    acc = consulta_dataframe(
        """
        SELECT
            id_accesorio,
            nombre,
            tipo,
            relacion_longitud_equivalente_ld
        FROM Accesorios
        WHERE activo = 1
        """
    )

    bomb = consulta_dataframe(
        """
        SELECT
            id_bomba,
            codigo_bomba,
            modelo,
            tipo,
            caudal_max_lmin,
            altura_max_mca,
            potencia_hp,
            eficiencia_pct,
            voltaje_v,
            precio_ref_clp
        FROM Bombas
        WHERE activo = 1
        """
    )

    emi = consulta_dataframe(
        """
        SELECT
            codigo_emisor,
            nombre,
            tipo,
            caudal_lh,
            presion_operacion_mca,
            radio_cobertura_m,
            precio_clp
        FROM Emisores
        WHERE activo = 1
        """
    )

    mat = consulta_dataframe(
        """
        SELECT
            material,
            rugosidad_absoluta_mm,
            factor_c_min,
            factor_c_max
        FROM MaterialesTuberia
        WHERE activo = 1
        """
    )

    # SQL Server puede devolver DECIMAL como Decimal.
    # Los convertimos a tipos numéricos compatibles con NumPy/Pandas.
    columnas_tuberias = [
        "diametro_mm",
        "diametro_interior_mm",
        "coef_hazen",
        "costo_metro_clp",
        "rugosidad_mm",
    ]
    for col in columnas_tuberias:
        if col in tub.columns:
            tub[col] = pd.to_numeric(tub[col], errors="coerce")

    columnas_bombas = [
        "caudal_max_lmin",
        "altura_max_mca",
        "potencia_hp",
        "eficiencia_pct",
        "voltaje_v",
        "precio_ref_clp",
    ]
    for col in columnas_bombas:
        if col in bomb.columns:
            bomb[col] = pd.to_numeric(bomb[col], errors="coerce")

    columnas_emisores = [
        "caudal_lh",
        "presion_operacion_mca",
        "radio_cobertura_m",
        "precio_clp",
    ]
    for col in columnas_emisores:
        if col in emi.columns:
            emi[col] = pd.to_numeric(emi[col], errors="coerce")

    if "relacion_longitud_equivalente_ld" in acc.columns:
        acc["relacion_longitud_equivalente_ld"] = pd.to_numeric(
            acc["relacion_longitud_equivalente_ld"], errors="coerce"
        )

    for col in ["rugosidad_absoluta_mm", "factor_c_min", "factor_c_max"]:
        if col in mat.columns:
            mat[col] = pd.to_numeric(mat[col], errors="coerce")

    return tub, acc, bomb, emi, mat


def _normalizar(nombre):
    return str(nombre).strip().lower().replace(" ", "_").replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")

def mapear_columnas(df, alias_por_campo):
    cols_norm = {_normalizar(c): c for c in df.columns}
    resultado = {}
    for campo, alias in alias_por_campo.items():
        for a in alias:
            if a in cols_norm:
                resultado[campo] = cols_norm[a]
                break
    return resultado

@st.cache_data(ttl=86400)
def obtener_altitud_openmeteo(lat, lon):
    """
    Obtiene la elevación del terreno desde Open-Meteo Elevation API.
    Retorna la altitud en metros sobre el nivel del mar o None si falla.
    """
    try:
        url = "https://api.open-meteo.com/v1/elevation"
        parametros = {
            "latitude": lat,
            "longitude": lon,
        }
        respuesta = requests.get(url, params=parametros, timeout=10)
        respuesta.raise_for_status()

        data = respuesta.json()
        elevaciones = data.get("elevation", [])

        if elevaciones and elevaciones[0] is not None:
            return float(elevaciones[0])

    except Exception as e:
        print("Error obteniendo altitud Open-Meteo:", e)

    return None


@st.cache_data(ttl=3600)
def obtener_clima_satelital(lat, lon, temporada):
    """Obtiene promedios históricos desde Open-Meteo Archive API."""

    fechas = {
        "Verano (Máxima Demanda)": ("2023-01-01", "2023-01-31"),
        "Primavera": ("2023-10-01", "2023-10-31"),
        "Otoño": ("2023-04-01", "2023-04-30"),
        "Invierno": ("2023-07-01", "2023-07-31"),
    }
    start, end = fechas.get(
        temporada,
        ("2023-01-01", "2023-01-31"),
    )

    try:
        url = "https://archive-api.open-meteo.com/v1/archive"
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start,
            "end_date": end,
            "daily": (
                "temperature_2m_mean,"
                "et0_fao_evapotranspiration,"
                "wind_speed_10m_mean"
            ),
            "hourly": "relative_humidity_2m",
            "timezone": "auto",
        }

        res = requests.get(url, params=params, timeout=15)
        res.raise_for_status()
        data = res.json()

        temp_list = [
            t for t in data.get("daily", {}).get("temperature_2m_mean", [])
            if t is not None
        ]
        eto_list = [
            e for e in data.get("daily", {}).get("et0_fao_evapotranspiration", [])
            if e is not None
        ]
        viento_list = [
            v for v in data.get("daily", {}).get("wind_speed_10m_mean", [])
            if v is not None
        ]
        hr_list = [
            h for h in data.get("hourly", {}).get("relative_humidity_2m", [])
            if h is not None
        ]

        if not temp_list or not eto_list or not viento_list or not hr_list:
            return None, None, None, None

        temp = sum(temp_list) / len(temp_list)
        eto = sum(eto_list) / len(eto_list)
        hr = sum(hr_list) / len(hr_list)

        # Open-Meteo entrega el viento diario en km/h.
        viento_kmh = sum(viento_list) / len(viento_list)
        viento_ms = viento_kmh / 3.6

        return temp, hr, viento_ms, eto

    except Exception as e:
        print("Error API Open-Meteo:", e)

    return None, None, None, None


def calcular_eto_penman(t_celsius, altitud_m, rn_mj, u2_ms, hr_porcentaje):
    presion_mar = 101.3
    dif_presion = 0.01055
    pah = presion_mar - (dif_presion * altitud_m)
    lv = 2.501 - (2.361 * 10 ** -3) * t_celsius
    es = math.exp((16.78 * t_celsius - 116.9) / (t_celsius + 237.3))
    ea = es * (hr_porcentaje / 100)
    dpv = es - ea
    delta = (4098 * es) / ((t_celsius + 237.3) ** 2)
    gamma = (pah / lv) * 0.00163
    g = 0.1 * rn_mj
    num = 0.408 * delta * (rn_mj - g) + gamma * (900 / (t_celsius + 273)) * u2_ms * dpv
    den = delta + gamma * (1 + 0.34 * u2_ms)
    return num / den, dpv, es, ea


def calcular_demanda_agronomica(eto, kc, eficiencia, uniformidad):
    etc = eto * kc
    nt = etc / (eficiencia * uniformidad)
    return etc, nt

def evaluar_suelo(textura):
    tabla = {
        "Arcilloso": (4.0, "< 5 mm/hr", "Lenta", "Alta retención. Riesgo de escorrentía si caudal es alto."),
        "Franco-Arcilloso": (8.0, "5 - 10 mm/hr", "Mod. Lenta", "Buen equilibrio, precaución con riegos prolongados."),
        "Franco": (15.0, "10 - 20 mm/hr", "Media", "Suelo óptimo. Drenaje y retención equilibrados."),
        "Franco-Arenoso": (25.0, "20 - 30 mm/hr", "Mod. Rápida", "Drenaje rápido. Riegos más frecuentes."),
        "Arenoso": (35.0, "> 30 mm/hr", "Rápida", "Baja retención. Exige riegos cortos y muy frecuentes."),
    }
    return tabla.get(textura, (15.0, "10 - 20 mm/hr", "Media", "Valor estándar asumido."))

PARAMETROS_EMISOR_PRELIMINARES = {
    "Aspersión": {
        "radio_cobertura_m": 12.0,
        "caudal_lh": 1260.0,
        "presion_operacion_mca": 25.0,
        "factor_traslape": 1.414,
    },
    "Microaspersión": {
        "radio_cobertura_m": 12.0,
        "caudal_lh": 1260.0,
        "presion_operacion_mca": 25.0,
        "factor_traslape": 1.414,
    },
}


def cargar_catalogo_fichas_emisores(ruta=None):
    """Carga fichas con todos los campos y validación técnica explícita."""
    ruta = Path(ruta) if ruta else Path(__file__).with_name(
        "catalogo_fichas_emisores.csv"
    )
    columnas = {
        "codigo",
        "nombre",
        "tecnica",
        "caudal_lh",
        "presion_operacion_mca",
        "radio_cobertura_m",
        "fuente_ficha",
        "fecha_ficha",
        "validada",
    }
    tabla = pd.read_csv(ruta, dtype=str, keep_default_na=False)
    faltantes = columnas - set(tabla.columns)
    if faltantes:
        raise ValueError(
            "El catálogo de fichas de emisores no contiene las columnas "
            f"requeridas: {', '.join(sorted(faltantes))}."
        )

    fichas = []
    codigos_vistos = set()
    pendientes = 0
    for indice, fila in tabla.iterrows():
        estado_validacion = str(fila["validada"]).strip().lower()
        if estado_validacion not in {
            "", "0", "false", "no", "1", "true", "si", "sí", "verdadero"
        }:
            raise ValueError(
                f"El campo validada en la fila {indice + 2} debe ser 0 o 1."
            )
        validada = estado_validacion in {"1", "true", "si", "sí", "verdadero"}
        if not validada:
            pendientes += 1
            continue
        tecnica = str(fila["tecnica"]).strip()
        if tecnica not in PARAMETROS_EMISOR_PRELIMINARES:
            raise ValueError(
                f"La técnica de la ficha en la fila {indice + 2} no es válida."
            )
        try:
            datos = {
                "caudal_lh": float(fila["caudal_lh"]),
                "presion_operacion_mca": float(
                    fila["presion_operacion_mca"]
                ),
                "radio_cobertura_m": float(fila["radio_cobertura_m"]),
            }
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"La ficha marcada como validada en la fila {indice + 2} "
                "tiene datos numéricos incompletos."
            ) from exc
        if any(
            not math.isfinite(valor) or valor <= 0
            for valor in datos.values()
        ):
            raise ValueError(
                f"La ficha marcada como validada en la fila {indice + 2} "
                "requiere caudal, presión y radio positivos y finitos."
            )
        codigo = str(fila["codigo"]).strip()
        nombre = str(fila["nombre"]).strip()
        fuente = str(fila["fuente_ficha"]).strip()
        fecha_ficha = str(fila["fecha_ficha"]).strip()
        if not all((codigo, nombre, fuente, fecha_ficha)):
            raise ValueError(
                f"La ficha marcada como validada en la fila {indice + 2} "
                "requiere código, nombre, fuente y fecha."
            )
        if codigo in codigos_vistos:
            raise ValueError(
                f"El código de ficha {codigo} está duplicado en el catálogo."
            )
        codigos_vistos.add(codigo)
        try:
            date.fromisoformat(fecha_ficha)
        except ValueError as exc:
            raise ValueError(
                f"La fecha de ficha en la fila {indice + 2} debe tener "
                "formato AAAA-MM-DD."
            ) from exc
        fichas.append(
            {
                "codigo": codigo,
                "nombre": nombre,
                "tecnica": tecnica,
                **datos,
                "fuente_ficha": fuente,
                "fecha_ficha": fecha_ficha,
            }
        )
    return fichas, pendientes


def cargar_catalogo_precios_obra_civil(ruta=None, tabla=None):
    """Devuelve precios civiles solo cuando la fila está documentada y validada."""
    ruta = Path(ruta) if ruta else Path(__file__).with_name(
        "catalogo_precios_obra_civil.csv"
    )
    columnas = {
        "codigo",
        "partida",
        "unidad",
        "precio_unitario_clp",
        "fuente",
        "fecha",
        "condiciones",
        "alcance_mano_obra",
        "incluye_mano_obra",
        "validado",
    }
    if tabla is None:
        tabla = pd.read_csv(ruta, dtype=str, keep_default_na=False)
    else:
        tabla = tabla.fillna("").copy()
    faltantes = columnas - set(tabla.columns)
    if faltantes:
        raise ValueError(
            "El catálogo de obras civiles no contiene las columnas "
            f"requeridas: {', '.join(sorted(faltantes))}."
        )

    precios = []
    codigos_vistos = set()
    pendientes = 0
    for indice, fila in tabla.iterrows():
        estado_validacion = str(fila["validado"]).strip().lower()
        if estado_validacion not in {
            "", "0", "false", "no", "1", "true", "si", "sí", "verdadero"
        }:
            raise ValueError(
                f"El campo validado en la fila {indice + 2} debe ser 0 o 1."
            )
        validado = estado_validacion in {"1", "true", "si", "sí", "verdadero"}
        if not validado:
            pendientes += 1
            continue
        codigo = str(fila["codigo"]).strip()
        partida = str(fila["partida"]).strip()
        unidad = str(fila["unidad"]).strip()
        fuente = str(fila["fuente"]).strip()
        fecha = str(fila["fecha"]).strip()
        condiciones = str(fila["condiciones"]).strip()
        alcance_mano_obra = str(fila["alcance_mano_obra"]).strip()
        try:
            precio = float(fila["precio_unitario_clp"])
            date.fromisoformat(fecha)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"El precio marcado como validado en la fila {indice + 2} "
                "requiere un importe numérico y fecha AAAA-MM-DD."
            ) from exc
        if (
            not all(
                (
                    codigo,
                    partida,
                    unidad,
                    fuente,
                    fecha,
                    condiciones,
                    alcance_mano_obra,
                )
            )
            or not math.isfinite(precio)
            or precio <= 0
        ):
            raise ValueError(
                f"El precio marcado como validado en la fila {indice + 2} "
                "tiene datos faltantes o un importe no positivo."
            )
        if partida not in {
            "EXCAVACION",
            "RELLENO_COMPACTACION",
            "HORMIGON_ANCLAJES",
        }:
            raise ValueError(
                f"La partida de la fila {indice + 2} no está soportada."
            )
        if unidad != "m³":
            raise ValueError(
                f"La unidad de la fila {indice + 2} debe ser m³ para poder "
                "usarse en esta cubicación."
            )
        if codigo in codigos_vistos:
            raise ValueError(
                f"El código de precio {codigo} está duplicado en el catálogo."
            )
        codigos_vistos.add(codigo)
        incluye = str(fila["incluye_mano_obra"]).strip().lower()
        if incluye not in {"1", "0", "true", "false", "si", "sí", "no"}:
            raise ValueError(
                f"El alcance de mano de obra en la fila {indice + 2} "
                "debe indicar si incluye mano de obra."
            )
        precios.append(
            {
                "codigo": codigo,
                "partida": partida,
                "unidad": unidad,
                "precio_unitario_clp": precio,
                "fuente": fuente,
                "fecha": fecha,
                "condiciones": condiciones,
                "alcance_mano_obra": alcance_mano_obra,
                "incluye_mano_obra": incluye
                in {"1", "true", "si", "sí"},
            }
        )
    return precios, pendientes


def guardar_catalogo_precios_obra_civil(tabla, ruta=None):
    """Valida el catálogo completo antes de persistirlo en el archivo local."""
    ruta = Path(ruta) if ruta else Path(__file__).with_name(
        "catalogo_precios_obra_civil.csv"
    )
    tabla = tabla.fillna("").astype(str).copy()
    filas_vacias = tabla.apply(
        lambda columna: columna.str.strip().eq("")
    ).all(axis=1)
    tabla = tabla.loc[~filas_vacias]
    resultado = cargar_catalogo_precios_obra_civil(tabla=tabla)
    tabla.to_csv(ruta, index=False, encoding="utf-8")
    return resultado


def estimar_longitud_matriz_desde_perimetro(perimetro_m, divisor=2.5):
    """Aplica la aproximación geométrica existente, nunca un trazado real."""
    perimetro = _validar_valor_presupuesto("perímetro del terreno", perimetro_m)
    divisor = _validar_valor_presupuesto("divisor geométrico", divisor)
    if perimetro <= 0 or divisor <= 0:
        raise ValueError("El perímetro y el divisor deben ser mayores que cero.")
    return perimetro / divisor


def generar_red_aspertension(ancho, largo, radio, caudal_e, factor_traslape=1.414):
    try:
        valores = tuple(
            float(valor)
            for valor in (ancho, largo, radio, caudal_e, factor_traslape)
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Ancho, largo, radio, caudal y factor de traslape deben ser "
            "números positivos."
        ) from exc
    if any(not math.isfinite(valor) or valor <= 0 for valor in valores):
        raise ValueError(
            "Ancho, largo, radio, caudal y factor de traslape deben ser "
            "positivos y finitos."
        )
    ancho, largo, radio, caudal_e, factor_traslape = valores
    espaciamiento = radio * factor_traslape
    n_x = int(np.ceil(ancho / espaciamiento)) + 1
    n_y = int(np.ceil(largo / espaciamiento)) + 1
    total_emisores = n_x * n_y
    caudal_total = total_emisores * caudal_e
    return n_x, n_y, total_emisores, caudal_total, largo, ancho * n_y, largo + (ancho * n_y)

def generar_red_goteo(ancho, largo, dist_hileras, dist_goteros, caudal_g):
    n_hileras = int(np.ceil(largo / dist_hileras)) + 1
    goteros_por_hilera = int(np.ceil(ancho / dist_goteros)) + 1
    total_emisores = n_hileras * goteros_por_hilera
    caudal_total = (total_emisores * caudal_g) / 3600
    return goteros_por_hilera, n_hileras, total_emisores, caudal_total, largo, ancho * n_hileras, largo + (ancho * n_hileras)

def calcular_hazen_williams(longitud, caudal_ls, diametro_mm, coeficiente_c):
    if caudal_ls <= 0 or diametro_mm <= 0 or coeficiente_c <= 0 or longitud <= 0: return 0.0
    q, d = caudal_ls / 1000, diametro_mm / 1000
    return 10.67 * longitud * (q ** 1.852) / ((coeficiente_c ** 1.852) * (d ** 4.87))

def calcular_tdh_y_potencia(altura_estatica, perdida_tub, perdida_acc, presion_emisor, caudal_ls, eficiencia=0.70):
    tdh = altura_estatica + perdida_tub + perdida_acc + presion_emisor
    return tdh, (caudal_ls * tdh) / (75 * eficiencia)

def seleccionar_bomba_optima(
    caudal_requerido_ls,
    tdh_requerido_m,
    df_bomb,
    margen_seguridad=1.10,
    criterio="balanceado",
):
    """
    Preselecciona configuraciones de bombas usando los límites del catálogo.

    IMPORTANTE:
    - Este método usa Qmax y Hmax como filtro preliminar de catálogo.
    - No reemplaza una validación final con curva Q-H del fabricante.

    criterio:
      - "menor_costo": prioriza CAPEX.
      - "menor_numero": prioriza cantidad de equipos.
      - "balanceado": combina costo, número de equipos y sobredimensionamiento.
    """
    alias = {
        "id_bomba": ["id_bomba"],
        "modelo": ["modelo", "codigo_bomba", "model", "nombre", "equipo"],
        "tipo": ["tipo"],
        "voltaje_v": ["voltaje_v", "voltaje"],
        "caudal_max_lmin": ["caudal_max_lmin", "caudal_max", "caudal", "q_max"],
        "altura_max": ["altura_max_mca", "altura_max_m", "altura_max", "altura", "h_max", "tdh_max"],
        "potencia_hp": ["potencia_hp", "potencia", "hp"],
        "precio": [
            "precio_seleccion_clp",
            "precio_mercado_clp",
            "precio_ref_clp",
            "precio_clp",
            "precio",
            "costo",
            "valor",
        ],
        "precio_mercado_clp": ["precio_mercado_clp"],
        "precio_ref_clp": ["precio_ref_clp"],
        "n_cotizaciones": ["n_cotizaciones"],
        "ultima_actualizacion": ["ultima_actualizacion"],
    }
    cols = mapear_columnas(df_bomb, alias)
    requeridas = {"modelo", "caudal_max_lmin", "altura_max", "potencia_hp"}
    if not requeridas.issubset(cols.keys()):
        return None

    q_obj = float(caudal_requerido_ls) * float(margen_seguridad)
    h_obj = float(tdh_requerido_m) * float(margen_seguridad)
    candidatos = []

    for _, fila in df_bomb.iterrows():
        try:
            q_uni = float(fila[cols["caudal_max_lmin"]]) / 60.0
            h_uni = float(fila[cols["altura_max"]])
            hp_uni = float(fila[cols["potencia_hp"]])
        except (TypeError, ValueError, KeyError):
            continue

        if q_uni <= 0 or h_uni <= 0 or hp_uni <= 0:
            continue

        n_paralelo = max(1, math.ceil(q_obj / q_uni))
        n_serie = max(1, math.ceil(h_obj / h_uni))
        n_total = n_paralelo * n_serie

        precio_uni = None
        if "precio" in cols:
            valor_precio = fila[cols["precio"]]
            if pd.notna(valor_precio):
                try:
                    precio_uni = float(
                        str(valor_precio)
                        .replace("$", "")
                        .replace(".", "")
                        .replace(",", "")
                        .strip()
                    )
                except (TypeError, ValueError):
                    precio_uni = None

        costo_total = precio_uni * n_total if precio_uni is not None else None

        # Capacidad instalada aproximada con la configuración calculada.
        q_instalado = q_uni * n_paralelo
        h_instalada = h_uni * n_serie
        exceso_q = max(0.0, (q_instalado - q_obj) / q_obj) if q_obj > 0 else 0.0
        exceso_h = max(0.0, (h_instalada - h_obj) / h_obj) if h_obj > 0 else 0.0

        def valor_opcional(nombre, default=None):
            col = cols.get(nombre)
            if not col:
                return default
            valor = fila[col]
            return default if pd.isna(valor) else valor

        candidatos.append({
            "id_bomba": int(valor_opcional("id_bomba")) if valor_opcional("id_bomba") is not None else None,
            "modelo": str(fila[cols["modelo"]]),
            "tipo": str(valor_opcional("tipo", "Bomba")),
            "voltaje_v": float(valor_opcional("voltaje_v")) if valor_opcional("voltaje_v") is not None else None,
            "n_paralelo": n_paralelo,
            "n_serie": n_serie,
            "n_total": n_total,
            "hp_unitario": hp_uni,
            "hp_total": hp_uni * n_total,
            "caudal_unitario": q_uni,
            "altura_unitaria": h_uni,
            "caudal_instalado": q_instalado,
            "altura_instalada": h_instalada,
            "exceso_q_pct": exceso_q * 100.0,
            "exceso_h_pct": exceso_h * 100.0,
            "precio_unitario": precio_uni,
            "costo_total": costo_total,
            "precio_mercado_clp": float(valor_opcional("precio_mercado_clp")) if valor_opcional("precio_mercado_clp") is not None else None,
            "precio_ref_clp": float(valor_opcional("precio_ref_clp")) if valor_opcional("precio_ref_clp") is not None else None,
            "n_cotizaciones": int(valor_opcional("n_cotizaciones", 0) or 0),
            "ultima_actualizacion": valor_opcional("ultima_actualizacion"),
        })

    if not candidatos:
        return None

    costos_validos = [c["costo_total"] for c in candidatos if c["costo_total"] is not None and c["costo_total"] > 0]
    costo_min = min(costos_validos) if costos_validos else None
    costo_max = max(costos_validos) if costos_validos else None
    max_unidades = max(c["n_total"] for c in candidatos) or 1

    for c in candidatos:
        if costo_min is not None and costo_max is not None and c["costo_total"] is not None:
            rango = max(costo_max - costo_min, 1.0)
            costo_norm = (c["costo_total"] - costo_min) / rango
        else:
            costo_norm = 1.0
        unidades_norm = (c["n_total"] - 1) / max(max_unidades - 1, 1)
        sobre_norm = min((c["exceso_q_pct"] + c["exceso_h_pct"]) / 200.0, 1.0)
        # Balanceado: 55% CAPEX + 25% cantidad de equipos + 20% sobredimensionamiento.
        c["score_balanceado"] = (0.55 * costo_norm) + (0.25 * unidades_norm) + (0.20 * sobre_norm)

    if criterio == "menor_costo":
        candidatos.sort(key=lambda c: (c["costo_total"] if c["costo_total"] is not None else float("inf"), c["n_total"], c["hp_total"]))
    elif criterio == "menor_numero":
        candidatos.sort(key=lambda c: (c["n_total"], c["costo_total"] if c["costo_total"] is not None else float("inf"), c["hp_total"]))
    else:
        candidatos.sort(key=lambda c: (c["score_balanceado"], c["costo_total"] if c["costo_total"] is not None else float("inf")))

    mejor = dict(candidatos[0])
    if mejor["n_serie"] > 1 and mejor["n_paralelo"] > 1:
        mejor["config_texto"] = f"{mejor['n_paralelo']} ramas PARALELO × {mejor['n_serie']} bombas SERIE"
    elif mejor["n_serie"] > 1:
        mejor["config_texto"] = f"{mejor['n_serie']} bombas en SERIE"
    elif mejor["n_paralelo"] > 1:
        mejor["config_texto"] = f"{mejor['n_paralelo']} bombas en PARALELO"
    else:
        mejor["config_texto"] = "1 sola bomba es suficiente"

    mejor["candidatos_evaluados"] = candidatos
    return mejor

def obtener_costo_tuberia_por_diametro(df_tub, diametro_mm, costo_default=1500):
    alias = {"diametro": ["diametro_mm", "diametro"], "costo_metro": ["costo_metro_clp", "costo_metro", "precio_metro"]}
    cols = mapear_columnas(df_tub, alias)
    if "diametro" in cols and "costo_metro" in cols:
        df_tmp = df_tub.copy()
        df_tmp["_diff"] = (df_tmp[cols["diametro"]] - diametro_mm).abs()
        fila = df_tmp.sort_values("_diff").iloc[0]
        try: return float(fila[cols["costo_metro"]]), fila[cols["diametro"]]
        except: pass
    return costo_default, diametro_mm

def calcular_presupuesto(m_prin, m_lat, diametro_matriz, df_tub, total_emisores, tecnica_riego):
    costo_emi_default = 120 if tecnica_riego == "Goteo" else 800 if tecnica_riego == "Microaspersión" else 4500
    costo_tub_lateral_default = 150 if tecnica_riego == "Goteo" else 250 if tecnica_riego == "Microaspersión" else 900
    costo_m_matriz, _ = obtener_costo_tuberia_por_diametro(df_tub, diametro_matriz)
    p_matriz = m_prin * costo_m_matriz
    p_lateral = m_lat * costo_tub_lateral_default
    p_emi = total_emisores * costo_emi_default
    return p_matriz, p_lateral, p_emi, p_matriz + p_lateral + p_emi, costo_m_matriz

TABLA_FILTROS = [(60, 2, 180_000), (150, 3, 350_000), (280, 4, 650_000), (480, 6, 1_200_000), (700, 8, 1_900_000)]
def dimensionar_filtro(caudal_m3h):
    for limite_m3h, pulgadas, costo in TABLA_FILTROS:
        if caudal_m3h <= limite_m3h: return pulgadas, costo
    return TABLA_FILTROS[-1][1], TABLA_FILTROS[-1][2]

def _validar_valor_presupuesto(nombre, valor, obligatorio=True):
    if valor is None:
        if obligatorio:
            raise ValueError(f"Falta ingresar {nombre}.")
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{nombre} debe ser un número válido.") from exc
    if not math.isfinite(numero) or numero < 0:
        raise ValueError(f"{nombre} debe ser un número finito y no negativo.")
    return numero


def clasificar_longitudes_tuberia_obra_civil(
    longitud_matriz_m,
    longitud_laterales_m,
    clasificacion_matriz,
    clasificacion_laterales,
    longitud_matriz_enterrada_mixta=None,
    longitud_laterales_enterrada_mixta=None,
):
    """Calcula solo los metros enterrados confirmados por clasificación del usuario."""
    longitudes = {
        "Matriz": _validar_valor_presupuesto(
            "longitud de matriz",
            longitud_matriz_m,
        ),
        "Laterales": _validar_valor_presupuesto(
            "longitud de laterales",
            longitud_laterales_m,
        ),
    }
    clasificaciones = {
        "Matriz": clasificacion_matriz,
        "Laterales": clasificacion_laterales,
    }
    longitudes_mixtas = {
        "Matriz": longitud_matriz_enterrada_mixta,
        "Laterales": longitud_laterales_enterrada_mixta,
    }
    permitidas = {"Pendiente de validar", "Enterrado", "Superficial", "Mixto"}
    resultado = {}

    for nombre, longitud_total in longitudes.items():
        clasificacion = clasificaciones[nombre]
        if clasificacion not in permitidas:
            raise ValueError(f"Clasificación no válida para {nombre.lower()}.")

        if clasificacion == "Enterrado":
            enterrada = longitud_total
        elif clasificacion == "Superficial" or clasificacion == "Pendiente de validar":
            enterrada = 0.0
        else:
            enterrada = _validar_valor_presupuesto(
                f"longitud enterrada mixta de {nombre.lower()}",
                longitudes_mixtas[nombre],
            )
            if not 0 < enterrada < longitud_total:
                raise ValueError(
                    f"En tramo mixto, la longitud enterrada de {nombre.lower()} "
                    "debe ser mayor que cero y menor que la longitud total."
                )

        resultado[nombre.lower()] = {
            "longitud_total_m": longitud_total,
            "clasificacion": clasificacion,
            "longitud_enterrada_confirmada_m": enterrada,
            "longitud_superficial_confirmada_m": (
                longitud_total - enterrada
                if clasificacion in {"Enterrado", "Superficial", "Mixto"}
                else 0.0
            ),
            "longitud_pendiente_validacion_m": (
                longitud_total if clasificacion == "Pendiente de validar" else 0.0
            ),
        }

    total_enterrado = math.fsum(
        tramo["longitud_enterrada_confirmada_m"]
        for tramo in resultado.values()
    )
    total_superficial = math.fsum(
        tramo["longitud_superficial_confirmada_m"]
        for tramo in resultado.values()
    )
    total_pendiente = math.fsum(
        tramo["longitud_pendiente_validacion_m"]
        for tramo in resultado.values()
    )
    return {
        "tramos": resultado,
        "longitud_enterrada_confirmada_m": total_enterrado,
        "longitud_superficial_confirmada_m": total_superficial,
        "longitud_pendiente_validacion_m": total_pendiente,
        "longitud_total_red_m": math.fsum(longitudes.values()),
    }


def calcular_obra_civil_cantidades(
    longitud_zanja_m,
    ancho_zanja_m,
    profundidad_zanja_m,
    volumen_relleno_m3,
    precio_excavacion_clp_m3,
    fuente_excavacion,
    precio_relleno_clp_m3,
    fuente_relleno,
    volumen_hormigon_anclajes_m3,
    precio_hormigon_clp_m3,
    fuente_hormigon,
    fecha_precio_excavacion=None,
    fecha_precio_relleno=None,
    fecha_precio_hormigon=None,
    incluye_mano_obra_excavacion=False,
    incluye_mano_obra_relleno=False,
    incluye_mano_obra_hormigon=False,
    fuente_dimensiones_zanja=None,
    fuente_volumen_relleno=None,
    fuente_volumen_hormigon=None,
):
    longitud = _validar_valor_presupuesto("longitud de zanja", longitud_zanja_m)
    if longitud > 0:
        ancho = _validar_valor_presupuesto("ancho de zanja", ancho_zanja_m)
        profundidad = _validar_valor_presupuesto(
            "profundidad de zanja",
            profundidad_zanja_m,
        )
        if ancho <= 0 or profundidad <= 0:
            raise ValueError(
                "El ancho y la profundidad de la zanja deben ser mayores que cero."
            )
        if not str(fuente_dimensiones_zanja or "").strip():
            raise ValueError(
                "Indica la fuente técnica de las dimensiones de zanja."
            )
        volumen_excavacion = math.prod((longitud, ancho, profundidad))
    else:
        volumen_excavacion = 0.0

    volumenes = {
        "excavacion": volumen_excavacion,
        "relleno": _validar_valor_presupuesto("volumen de relleno", volumen_relleno_m3),
        "hormigon": _validar_valor_presupuesto(
            "volumen de hormigón de anclajes",
            volumen_hormigon_anclajes_m3,
        ),
    }
    if any(not math.isfinite(volumen) for volumen in volumenes.values()):
        raise ValueError("Los volúmenes calculados deben ser finitos.")
    if volumenes["relleno"] > volumenes["excavacion"]:
        raise ValueError(
            "El volumen de relleno y compactación no puede superar el volumen "
            "de excavación de la zanja. Revisa la cubicación y sus unidades."
        )
    if volumenes["relleno"] > 0 and not str(
        fuente_volumen_relleno or ""
    ).strip():
        raise ValueError(
            "Indica la fuente de cubicación del volumen de relleno."
        )
    if volumenes["hormigon"] > 0 and not str(
        fuente_volumen_hormigon or ""
    ).strip():
        raise ValueError(
            "Indica la fuente de cubicación del volumen de hormigón."
        )

    configuracion = (
        (
            "Excavación de zanjas",
            "excavacion",
            precio_excavacion_clp_m3,
            fuente_excavacion,
            fecha_precio_excavacion,
            incluye_mano_obra_excavacion,
        ),
        (
            "Relleno y compactación",
            "relleno",
            precio_relleno_clp_m3,
            fuente_relleno,
            fecha_precio_relleno,
            incluye_mano_obra_relleno,
        ),
        (
            "Hormigón para anclajes",
            "hormigon",
            precio_hormigon_clp_m3,
            fuente_hormigon,
            fecha_precio_hormigon,
            incluye_mano_obra_hormigon,
        ),
    )
    partidas = []
    for nombre, clave, precio_ingresado, fuente_ingresada, fecha_precio, incluye_mano_obra in configuracion:
        volumen = volumenes[clave]
        precio = _validar_valor_presupuesto(
            f"precio unitario de {nombre.lower()}",
            precio_ingresado,
            obligatorio=volumen > 0,
        )
        fuente = str(fuente_ingresada or "").strip()
        if precio is not None and precio > 0 and not fuente:
            raise ValueError(
                f"Indica la fuente verificable del precio unitario de {nombre.lower()}."
            )
        if volumen > 0 and (precio is None or precio <= 0):
            raise ValueError(
                f"El precio unitario de {nombre.lower()} debe ser mayor que cero."
            )
        subtotal = volumen * (precio or 0.0)
        if not math.isfinite(subtotal):
            raise ValueError(f"El subtotal de {nombre.lower()} no es finito.")
        partidas.append(
            {
                "Ítem": nombre,
                "Cantidad": volumen,
                "Unidad": "m³",
                "Precio unitario (CLP/m³)": precio,
                "Fuente": fuente or None,
                "Fecha del precio": fecha_precio,
                "Incluye mano de obra": bool(incluye_mano_obra),
                "Subtotal (CLP)": subtotal,
            }
        )

    return {
        "partidas": partidas,
        "total": math.fsum(partida["Subtotal (CLP)"] for partida in partidas),
        "volumen_excavacion_m3": volumenes["excavacion"],
        "fuente_dimensiones_zanja": (
            str(fuente_dimensiones_zanja).strip()
            if volumenes["excavacion"] > 0
            else None
        ),
        "fuente_volumen_relleno": (
            str(fuente_volumen_relleno).strip()
            if volumenes["relleno"] > 0
            else None
        ),
        "fuente_volumen_hormigon": (
            str(fuente_volumen_hormigon).strip()
            if volumenes["hormigon"] > 0
            else None
        ),
        "volumen_relleno_m3": volumenes["relleno"],
        "volumen_hormigon_anclajes_m3": volumenes["hormigon"],
    }


def calcular_presupuesto_detallado(
    p_matriz,
    p_lateral,
    p_emi,
    costo_bombas,
    caudal_total_ls,
    pct_accesorios,
    pct_obra_civil,
    pct_instalacion,
    costo_filtro_manual,
    incluir_iva,
    *,
    metodo_obra_civil="porcentaje",
    obra_civil_cantidades=None,
    longitud_matriz_m=None,
    longitud_laterales_m=None,
    cantidad_emisores=None,
    cantidad_bombas=None,
):
    p_matriz = _validar_valor_presupuesto("costo de tubería matriz", p_matriz)
    p_lateral = _validar_valor_presupuesto("costo de tubería lateral", p_lateral)
    p_emi = _validar_valor_presupuesto("costo de emisores", p_emi)
    costo_bombas = _validar_valor_presupuesto("costo de bombeo", costo_bombas)
    caudal_total_ls = _validar_valor_presupuesto("caudal total", caudal_total_ls)
    pct_accesorios = _validar_valor_presupuesto("porcentaje de accesorios", pct_accesorios)
    pct_obra_civil = _validar_valor_presupuesto("porcentaje referencial de obra civil", pct_obra_civil)
    pct_instalacion = _validar_valor_presupuesto("porcentaje de instalación", pct_instalacion)
    if any(porcentaje > 100 for porcentaje in (pct_accesorios, pct_obra_civil, pct_instalacion)):
        raise ValueError("Los porcentajes del presupuesto no pueden superar 100%.")
    if metodo_obra_civil not in {"porcentaje", "cantidades"}:
        raise ValueError("Método de obra civil no válido.")

    longitud_matriz_m = _validar_valor_presupuesto(
        "longitud de tubería matriz",
        longitud_matriz_m,
        obligatorio=False,
    )
    longitud_laterales_m = _validar_valor_presupuesto(
        "longitud de tubería lateral",
        longitud_laterales_m,
        obligatorio=False,
    )
    cantidad_emisores = _validar_valor_presupuesto(
        "cantidad de emisores",
        cantidad_emisores,
        obligatorio=False,
    )
    cantidad_bombas = _validar_valor_presupuesto(
        "cantidad de bombas",
        cantidad_bombas,
        obligatorio=False,
    )

    pulgadas_filtro, costo_filtro_sugerido = dimensionar_filtro(caudal_total_ls * 3.6)
    costo_filtro = (
        _validar_valor_presupuesto("costo de filtrado", costo_filtro_manual)
        if costo_filtro_manual is not None
        else float(costo_filtro_sugerido)
    )
    p_tuberias = p_matriz + p_lateral
    p_accesorios = p_tuberias * (pct_accesorios / 100.0)
    p_obra_civil_referencial = p_tuberias * (pct_obra_civil / 100.0)
    if metodo_obra_civil == "cantidades":
        if not isinstance(obra_civil_cantidades, dict):
            raise ValueError("Completa las cantidades y precios unitarios de obra civil.")
        partidas_cantidades = obra_civil_cantidades.get("partidas")
        p_obra_civil_cantidades = _validar_valor_presupuesto(
            "total de obra civil por cantidades",
            obra_civil_cantidades.get("total"),
        )
        if not isinstance(partidas_cantidades, list) or len(partidas_cantidades) != 3:
            raise ValueError("El desglose de obra civil por cantidades está incompleto.")
        suma_partidas = math.fsum(
            _validar_valor_presupuesto(
                "subtotal de una partida de obra civil",
                partida.get("Subtotal (CLP)"),
            )
            for partida in partidas_cantidades
        )
        if not math.isclose(suma_partidas, p_obra_civil_cantidades, rel_tol=1e-9):
            raise ValueError("El total de obra civil no coincide con la suma de sus partidas.")
        p_obra_civil = p_obra_civil_cantidades
    else:
        partidas_cantidades = (
            obra_civil_cantidades.get("partidas")
            if isinstance(obra_civil_cantidades, dict)
            else None
        )
        p_obra_civil_cantidades = (
            _validar_valor_presupuesto(
                "total de obra civil por cantidades",
                obra_civil_cantidades.get("total"),
            )
            if isinstance(obra_civil_cantidades, dict)
            else None
        )
        p_obra_civil = p_obra_civil_referencial

    subtotal_materiales = p_matriz + p_lateral + p_emi + costo_bombas + costo_filtro + p_accesorios + p_obra_civil
    if metodo_obra_civil == "cantidades":
        costo_civil_con_mano_obra = math.fsum(
            partida["Subtotal (CLP)"]
            for partida in partidas_cantidades
            if partida.get("Incluye mano de obra")
        )
        base_instalacion = subtotal_materiales - costo_civil_con_mano_obra
    else:
        base_instalacion = subtotal_materiales
    p_instalacion = base_instalacion * (pct_instalacion / 100.0)
    subtotal_con_instalacion = subtotal_materiales + p_instalacion
    iva = subtotal_con_instalacion * 0.19 if incluir_iva else 0.0
    total = subtotal_con_instalacion + iva

    def item_presupuesto(descripcion, subtotal, cantidad=None, unidad="global"):
        item = {
            "Ítem": descripcion,
            "Subtotal (CLP)": float(subtotal),
        }
        if cantidad is not None and float(cantidad) > 0:
            cantidad = float(cantidad)
            item["Cantidad"] = cantidad
            item["Unidad"] = unidad
            item["Precio unitario (CLP)"] = float(subtotal) / cantidad
        else:
            item["Cantidad"] = 1.0
            item["Unidad"] = "global"
            item["Precio unitario (CLP)"] = float(subtotal)
        return item

    items = [
        item_presupuesto(
            "Tubería matriz",
            p_matriz,
            longitud_matriz_m,
            "m",
        ),
        item_presupuesto(
            "Tubería lateral",
            p_lateral,
            longitud_laterales_m,
            "m",
        ),
        item_presupuesto(
            "Emisores",
            p_emi,
            cantidad_emisores,
            "unidad",
        ),
        item_presupuesto(
            f"Equipo de filtrado ({pulgadas_filtro}\")",
            costo_filtro,
        ),
        item_presupuesto(
            f"Válvulas/accesorios ({pct_accesorios:.0f}%)",
            p_accesorios,
        ),
    ]
    if metodo_obra_civil == "cantidades":
        items.extend(partidas_cantidades)
    else:
        items.append(
            {
                "Ítem": f"Obra civil/anclajes ({pct_obra_civil:.0f}%, referencial)",
                "Subtotal (CLP)": p_obra_civil,
            }
        )
    items.extend(
        [
            item_presupuesto(
                "Equipo de bombeo",
                costo_bombas,
                cantidad_bombas,
                "unidad",
            ),
            {
                "Ítem": "Subtotal materiales",
                "Subtotal (CLP)": subtotal_materiales,
            },
            item_presupuesto(
                (
                    f"Instalación ({pct_instalacion:.0f}% de base sin mano de obra civil incluida)"
                    if metodo_obra_civil == "cantidades"
                    else f"Instalación ({pct_instalacion:.0f}%)"
                ),
                p_instalacion,
            ),
        ]
    )
    if incluir_iva:
        items.append(
            item_presupuesto(
                "IVA (19%)",
                iva,
            )
        )
    items.append(
        {
            "Ítem": "TOTAL",
            "Subtotal (CLP)": total,
        }
    )
    
    return {
        "items": items,
        "subtotal_materiales": subtotal_materiales,
        "subtotal_con_instalacion": subtotal_con_instalacion,
        "total": total,
        "costo_filtro": costo_filtro,
        "p_accesorios": p_accesorios,
        "p_obra_civil": p_obra_civil,
        "p_obra_civil_referencial": p_obra_civil_referencial,
        "p_obra_civil_cantidades": p_obra_civil_cantidades,
        "partidas_obra_civil": partidas_cantidades or [],
        "metodo_obra_civil": metodo_obra_civil,
        "base_instalacion": base_instalacion,
        "p_instalacion": p_instalacion,
        "iva": iva
    }


_CLAVES_ESTADO_PROYECTO = {
    "cultivo",
    "temporada",
    "tipo_suelo",
    "modo_clima",
    "latitud",
    "longitud",
    "area_m2",
    "superficie_ha",
    "perimetro_m",
    "longitud_matriz_m",
    "presupuesto_detallado",
    "codigo_ficha_emisor",
    "comuna_predio",
    "comunas_predio",
    "region_predio",
    "regiones_predio",
    "pais_predio",
}
_PREFIJOS_ESTADO_PROYECTO = (
    "alt_",
    "alternativas_bombeo",
    "caudal_",
    "clasificacion_tramos",
    "coef_hazen",
    "componentes_presupuesto",
    "costo_bombas",
    "datos_agronomicos_",
    "diametro_matriz",
    "dist_",
    "eficiencia_bomba",
    "errores_web",
    "etc",
    "estimacion_williams",
    "ficha_emisor_",
    "firma_busqueda_externa",
    "fuente_altitud",
    "fuente_clima",
    "fuente_parametros_emisor",
    "fuente_precio_bomba",
    "hp_req",
    "horas_jornada",
    "hr_",
    "id_aprobacion_hitl",
    "id_ejecucion_agente",
    "id_proyecto_sql",
    "kc_",
    "lat_centro",
    "lat_auto",
    "lon_centro",
    "lon_auto",
    "m_",
    "metodo_longitudes_red",
    "modelo_bomba",
    "modo_clima_activo",
    "necesidad_total",
    "num_sectores",
    "parametros_emisor_",
    "perdida_",
    "plano_",
    "presion_",
    "presupuesto_",
    "presion_hidraulica_emisor_",
    "presion_operacion_emisor",
    "q_",
    "radio_emisor_",
    "resultado_mc",
    "respuesta_agente",
    "riego_",
    "seleccion_bomba",
    "temp_",
    "tdh",
    "tecnica_riego",
    "tiempo_riego",
    "tot_emi",
    "trazado_real_",
    "velocidad_infiltracion_",
    "viento_",
    "eto",
    "factor_traslape_",
    "candidatos_web",
    "altura_estatica",
)
_CLAVES_WIDGET_PROYECTO = {
    "cultivo_diseno",
    "temporada_diseno",
    "selector_modo_clima",
    "tipo_suelo_diseno",
    "tecnica_riego_seleccion",
    "diametro_matriz_input",
    "coef_hazen_input",
    "altura_estatica_input",
    "perdida_acc_input",
    "eficiencia_bomba_diseno_slider",
    "presupuesto_clasificacion_matriz",
    "presupuesto_clasificacion_laterales",
    "presupuesto_ancho_zanja_m",
    "presupuesto_profundidad_zanja_m",
    "presupuesto_volumen_relleno_m3",
    "presupuesto_volumen_hormigon_m3",
    "presupuesto_precio_excavacion",
    "presupuesto_precio_relleno",
    "presupuesto_precio_hormigon",
    "presupuesto_fecha_precio_excavacion",
    "presupuesto_fecha_precio_relleno",
    "presupuesto_fecha_precio_hormigon",
    "presupuesto_fuente_excavacion",
    "presupuesto_fuente_relleno",
    "presupuesto_fuente_hormigon",
    "presupuesto_excavacion_incluye_mano_obra",
    "presupuesto_relleno_incluye_mano_obra",
    "presupuesto_hormigon_incluye_mano_obra",
    "nombre_proyecto_guardar",
}


def _es_clave_estado_proyecto(clave):
    return (
        clave in _CLAVES_ESTADO_PROYECTO
        or clave in _CLAVES_WIDGET_PROYECTO
        or any(clave.startswith(prefijo) for prefijo in _PREFIJOS_ESTADO_PROYECTO)
    )


def _restaurar_datos_proyecto_en_sesion(datos, estado):
    """Valida un snapshot y sustituye solo el estado perteneciente al proyecto."""
    if not isinstance(datos, dict) or any(
        not isinstance(clave, str) for clave in datos
    ):
        raise ValueError("Los datos guardados del proyecto no son válidos.")
    try:
        json.dumps(datos, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Los datos guardados del proyecto contienen valores no válidos."
        ) from exc

    datos_preparados = {
        clave: valor
        for clave, valor in datos.items()
        if _es_clave_estado_proyecto(clave)
        and clave not in {"resultado_mc", "respuesta_agente"}
    }
    for clave in ("comuna_predio", "region_predio"):
        valor = datos_preparados.get(clave)
        if isinstance(valor, str):
            datos_preparados[clave] = normalizar_nombre_administrativo(valor)
    for clave in ("comunas_predio", "regiones_predio"):
        nombres = datos_preparados.get(clave)
        if isinstance(nombres, list):
            datos_preparados[clave] = [
                normalizar_nombre_administrativo(nombre)
                if isinstance(nombre, str)
                else nombre
                for nombre in nombres
            ]
    for clave in ("datos_agronomicos_listos", "riego_configurado"):
        if clave in datos_preparados and not isinstance(
            datos_preparados[clave], bool
        ):
            raise ValueError(f"El indicador guardado {clave} no es válido.")

    nuevo_estado = {
        clave: valor
        for clave, valor in estado.items()
        if not _es_clave_estado_proyecto(clave)
    }
    nuevo_estado.update(datos_preparados)
    nuevo_estado.setdefault("datos_agronomicos_listos", False)
    nuevo_estado.setdefault("riego_configurado", False)
    nuevo_estado.setdefault("necesidad_total", None)
    nuevo_estado.setdefault("etc", None)
    nuevo_estado.setdefault("eto_final", None)

    asignaciones = {
        "cultivo": (
            "cultivo_diseno",
            {"Avellano Europeo", "Manzano", "Vid Vinífera", "Nogal", "Otro"},
        ),
        "temporada": (
            "temporada_diseno",
            {
                "Verano (Máxima Demanda)",
                "Primavera",
                "Otoño",
                "Invierno",
            },
        ),
        "modo_clima": (
            "selector_modo_clima",
            {"📡 Automático - Open-Meteo"},
        ),
        "tipo_suelo": (
            "tipo_suelo_diseno",
            {
                "Arcilloso",
                "Franco-Arcilloso",
                "Franco",
                "Franco-Arenoso",
                "Arenoso",
            },
        ),
        "tecnica_riego": (
            "tecnica_riego_seleccion",
            {"Aspersión", "Microaspersión", "Goteo"},
        ),
        "diametro_matriz": ("diametro_matriz_input", None),
        "coef_hazen": ("coef_hazen_input", None),
        "altura_estatica": ("altura_estatica_input", None),
        "perdida_acc": ("perdida_acc_input", None),
    }
    advertencias = []
    for clave_datos, (clave_widget, opciones) in asignaciones.items():
        valor = datos_preparados.get(clave_datos)
        if valor is None:
            continue
        if opciones is None or valor in opciones:
            nuevo_estado[clave_widget] = valor
        else:
            advertencias.append(
                f"No se pudo restaurar {clave_datos}: valor no reconocido."
            )

    if "eficiencia_bomba_diseno" in datos_preparados:
        try:
            eficiencia = float(datos_preparados["eficiencia_bomba_diseno"])
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "La eficiencia de bomba guardada no es válida."
            ) from exc
        if not math.isfinite(eficiencia) or not 0.4 <= eficiencia <= 0.9:
            raise ValueError(
                "La eficiencia de bomba guardada debe estar entre 0,4 y 0,9."
            )
        nuevo_estado["eficiencia_bomba_diseno_slider"] = round(
            eficiencia * 100
        )

    tecnica = datos_preparados.get("tecnica_riego")
    if tecnica:
        clave_presion = (
            "presion_hidraulica_emisor_"
            + str(datos_preparados.get("codigo_ficha_emisor") or tecnica)
        )
        if "presion_emisor" in datos_preparados:
            try:
                presion_emisor = float(datos_preparados["presion_emisor"])
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "La presión del emisor guardada no es válida."
                ) from exc
            if not math.isfinite(presion_emisor) or presion_emisor < 0:
                raise ValueError(
                    "La presión del emisor guardada debe ser finita y no negativa."
                )
            nuevo_estado[clave_presion] = presion_emisor
        ficha = datos_preparados.get("ficha_emisor_seleccionada")
        clave_ficha = f"ficha_emisor_{tecnica}"
        if isinstance(ficha, dict) and ficha.get("codigo") and ficha.get("nombre"):
            nuevo_estado[clave_ficha] = f'{ficha["codigo"]} — {ficha["nombre"]}'
        elif tecnica in {"Aspersión", "Microaspersión"}:
            nuevo_estado[clave_ficha] = "Parámetros manuales/preliminares"

    clasificacion = datos_preparados.get("clasificacion_tramos_obra_civil")
    if clasificacion is None:
        clasificacion = {}
    if not isinstance(clasificacion, dict):
        raise ValueError("La clasificación de tramos guardada no es válida.")
    tramos = clasificacion.get("tramos", {})
    if not isinstance(tramos, dict):
        raise ValueError("Los tramos de obra civil guardados no son válidos.")
    for nombre, clave_widget in (
        ("matriz", "presupuesto_clasificacion_matriz"),
        ("laterales", "presupuesto_clasificacion_laterales"),
    ):
        tramo = tramos.get(nombre, {})
        if not isinstance(tramo, dict):
            raise ValueError(
                f"El tramo de {nombre} guardado no tiene un formato válido."
            )
        valor = tramo.get("clasificacion")
        if valor in {"Pendiente de validar", "Enterrado", "Superficial"}:
            nuevo_estado[clave_widget] = valor
        elif valor == "Mixto":
            advertencias.append(
                f"La clasificación mixta de {nombre} necesita confirmación."
            )

    if nuevo_estado.get("datos_agronomicos_listos") and not all(
        nuevo_estado.get(clave) is not None
        for clave in ("necesidad_total", "etc", "eto_final")
    ):
        nuevo_estado["datos_agronomicos_listos"] = False
        nuevo_estado["necesidad_total"] = None
        nuevo_estado["etc"] = None
        nuevo_estado["eto_final"] = None

    claves_hidraulicas_requeridas = (
        "q_tot",
        "m_prin",
        "m_lat",
        "tot_emi",
        "tecnica_riego",
        "caudal_sector",
        "tdh",
        "hp_req",
    )
    if not nuevo_estado.get("riego_configurado") or not all(
        nuevo_estado.get(clave) is not None
        for clave in claves_hidraulicas_requeridas
    ):
        nuevo_estado["riego_configurado"] = False
        for clave in (
            "q_tot",
            "caudal_sector",
            "tdh",
            "hp_req",
            "tiempo_riego",
            "num_sectores",
            "seleccion_bomba_v2",
            "alternativas_bombeo_v2",
            "costo_bombas",
        ):
            nuevo_estado.pop(clave, None)

    claves_presupuesto_requeridas = (
        "m_prin",
        "m_lat",
        "diametro_matriz",
        "tot_emi",
        "tecnica_riego",
    )
    if not all(
        nuevo_estado.get(clave) is not None
        for clave in claves_presupuesto_requeridas
    ):
        for clave in (
            "presupuesto_total",
            "presupuesto_obra_civil",
            "componentes_presupuesto",
            "presupuesto_detallado",
        ):
            nuevo_estado.pop(clave, None)

    if (
        datos_preparados.get("plano_area_real_m2")
        and not datos_preparados.get("plano_coordenadas_gps")
    ):
        advertencias.append(
            "Este proyecto no guardaba el polígono del terreno; se recuperaron "
            "sus medidas, pero el mapa debe delimitarse de nuevo."
        )

    estado.clear()
    estado.update(nuevo_estado)
    return advertencias


def _cargar_proyecto_guardado_callback():
    estado = st.session_state
    estado.pop("proyecto_carga_error", None)
    estado.pop("proyecto_carga_exito", None)
    try:
        proyecto = cargar_proyecto_disenio(
            estado["proyecto_guardado_seleccionado"]
        )
        advertencias = _restaurar_datos_proyecto_en_sesion(
            proyecto["datos"],
            estado,
        )
        estado["id_proyecto_sql"] = proyecto["id_proyecto"]
        estado["nombre_proyecto_guardar"] = proyecto["nombre"]
        estado["proyecto_carga_exito"] = (
            proyecto["nombre"],
            advertencias,
        )
    except Exception as error:
        estado["proyecto_carga_error"] = str(error)


# ==========================================
# BLOQUE PRINCIPAL: INTERFAZ GRÁFICA
# ==========================================
def main():
    st.markdown(
        """<div class="encabezado-fijo">
            <h1>🌱 Herramienta Avanzada de Diseño Hidráulico</h1>
            <p>Plataforma paramétrica para diseño agronómico, hidráulico y evaluación de proyectos de riego</p>
        </div>""",
        unsafe_allow_html=True,
    )

    try:
        df_tub, df_acc, df_bomb, df_emi, df_mat = cargar_bases_de_datos()
    except Exception as e:
        st.error(f"❌ Error al cargar bases de datos: {e}")
        return

    # ========================================================
    # ESTADO PERSISTENTE DEL PROYECTO
    # ========================================================
    valores_iniciales = {
        "necesidad_total": None,
        "etc": None,
        "eto_final": None,
        "datos_agronomicos_listos": False,
        "riego_configurado": False,
    }
    for clave, valor in valores_iniciales.items():
        if clave not in st.session_state:
            st.session_state[clave] = valor

    (tab_diseno, tab_hidraulica, tab_equipos, tab_presupuesto, tab_datos,
     tab_montecarlo) = st.tabs(
        PAT_TAB_LABELS,
        key="pat_tab_activa",
        on_change="rerun",
    )

    # ========================================================
    # PESTAÑA 1: DISEÑO DEL TERRENO
    # ========================================================
    with tab_diseno:
        st.write(
            "Complete las etapas secuenciales para parametrizar su proyecto agrícola."
        )

        # ----------------------------------------------------
        # PASO 1: MAPA Y GEOLOCALIZACIÓN
        # ----------------------------------------------------
        with st.expander(
            "📍 Paso 1: Delimitación Geográfica del Predio (Buscador GPS)",
            expanded=True,
        ):
            st.info(
                "Utiliza la lupa 🔍 en el mapa para buscar tu comuna o dirección "
                "(ej. 'San Clemente, Maule'). Luego, dibuja el polígono de tu predio ⬟."
            )

            # ============================================================
            # DATOS GUARDADOS DEL MAPA
            # ============================================================

            lat_centro_guardado = st.session_state.get("lat_centro")
            lon_centro_guardado = st.session_state.get("lon_centro")

            coordenadas_guardadas = st.session_state.get(
                "plano_coordenadas_gps"
            )

            # Centro inicial
            if (
                lat_centro_guardado is not None
                and lon_centro_guardado is not None
            ):
                centro_mapa = [
                    float(lat_centro_guardado),
                    float(lon_centro_guardado),
                ]
            else:
                # Talca por defecto
                centro_mapa = [-35.4264, -71.6554]


            # ============================================================
            # CREACIÓN DEL MAPA
            # ============================================================

            mapa = folium.Map(
                location=centro_mapa,
                zoom_start=12,
                tiles=None,
                control_scale=True,
                prefer_canvas=True,
            )


            # ============================================================
            # CAPA SATELITAL
            # ============================================================

            folium.TileLayer(
                tiles=(
                    "https://services.arcgisonline.com/"
                    "ArcGIS/rest/services/World_Imagery/"
                    "MapServer/tile/{z}/{y}/{x}"
                ),
                attr="Esri World Imagery",
                name="🛰️ Satélite",
                overlay=False,
                control=True,
                show=True,
            ).add_to(mapa)

            # ============================================================
            # LÍMITES Y LUGARES ESRI
            # ============================================================

            folium.TileLayer(
                tiles=(
                    "https://services.arcgisonline.com/"
                    "ArcGIS/rest/services/Reference/"
                    "World_Boundaries_and_Places/"
                    "MapServer/tile/{z}/{y}/{x}"
                ),
                attr="Esri",
                name="📍 Ciudades y límites",
                overlay=True,
                control=True,
                show=True,
            ).add_to(mapa)


            # ============================================================
            # MAPA VIAL
            # ============================================================

            folium.TileLayer(
                tiles="OpenStreetMap",
                name="🛣️ Mapa vial",
                overlay=False,
                control=True,
                show=False,
            ).add_to(mapa)


            # ============================================================
            # MAPA CLARO
            # ============================================================

            folium.TileLayer(
                tiles="CartoDB positron",
                name="📋 Mapa claro",
                overlay=False,
                control=True,
                show=False,
            ).add_to(mapa)


            # ============================================================
            # POLÍGONO GUARDADO
            # ============================================================

            if coordenadas_guardadas:

                geojson_predio = {
                    "type": "Feature",
                    "properties": {
                        "nombre": "Predio seleccionado",
                        "origen": "Proyecto PAT",
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            coordenadas_guardadas
                        ],
                    },
                }

                folium.GeoJson(
                    geojson_predio,
                    name="🌱 Predio seleccionado",
                    style_function=lambda feature: {
                        "color": "#00BFFF",
                        "weight": 4,
                        "fillColor": "#00BFFF",
                        "fillOpacity": 0.18,
                    },
                    tooltip="Predio seleccionado",
                ).add_to(mapa)


                # ========================================================
                # ZOOM AUTOMÁTICO AL PREDIO
                # IMPORTANTE:
                # tus coordenadas están como [LONGITUD, LATITUD]
                # Folium usa [LATITUD, LONGITUD]
                # ========================================================

                latitudes = [
                    float(punto[1])
                    for punto in coordenadas_guardadas
                ]

                longitudes = [
                    float(punto[0])
                    for punto in coordenadas_guardadas
                ]

                bounds_predio = [
                    [
                        min(latitudes),
                        min(longitudes),
                    ],
                    [
                        max(latitudes),
                        max(longitudes),
                    ],
                ]

                mapa.fit_bounds(
                    bounds_predio,
                    padding=(40, 40),
                    max_zoom=17,
                )


                # ========================================================
                # MARCADOR EN EL CENTRO DEL PREDIO
                # ========================================================

                lat_centro_visual = sum(latitudes) / len(latitudes)
                lon_centro_visual = sum(longitudes) / len(longitudes)

                folium.Marker(
                    location=[
                        lat_centro_visual,
                        lon_centro_visual,
                    ],
                    tooltip="Centro del predio",
                    popup=(
                        f"<b>Centro del predio</b><br>"
                        f"Lat: {lat_centro_visual:.6f}<br>"
                        f"Lon: {lon_centro_visual:.6f}"
                    ),
                    icon=folium.Icon(
                        color="green",
                        icon="info-sign",
                    ),
                ).add_to(mapa)


            # ============================================================
            # BUSCADOR GPS
            # ============================================================

            Geocoder(
                collapsed=False,
                position="topright",
                add_marker=True,
                zoom=16,
                placeholder="Buscar comuna, camino o dirección...",
            ).add_to(mapa)


            # ============================================================
            # HERRAMIENTA DE DIBUJO
            # ============================================================

            draw = Draw(
                export=True,
                position="topleft",
                draw_options={
                    "polyline": False,
                    "rectangle": False,
                    "circle": False,
                    "circlemarker": False,
                    "marker": False,
                    "polygon": {
                        "allowIntersection": False,
                        "showArea": True,
                        "shapeOptions": {
                            "color": "#00BFFF",
                            "weight": 4,
                            "fillOpacity": 0.20,
                        },
                    },
                },
                edit_options={
                    "edit": True,
                    "remove": True,
                },
            )

            draw.add_to(mapa)


            # ============================================================
            # PANTALLA COMPLETA
            # ============================================================

            Fullscreen(
                position="topleft",
                title="Pantalla completa",
                title_cancel="Salir de pantalla completa",
                force_separate_button=True,
            ).add_to(mapa)


            # ============================================================
            # CONTROL DE CAPAS
            # ============================================================

            folium.LayerControl(
                position="bottomright",
                collapsed=True,
            ).add_to(mapa)


            # ============================================================
            # MOSTRAR MAPA
            # ============================================================

            mapa_output = st_folium(
                mapa,
                width=None,
                height=560,
                key="mapa_diseno_predio",
            )


            # ============================================================
            # PROCESAR / PERSISTIR POLÍGONO DEL PREDIO
            # ============================================================
            dibujos = mapa_output.get("all_drawings") or []

            if dibujos:
                geometria = dibujos[-1].get("geometry", {})
                coordenadas_gps = geometria.get("coordinates", [[]])[0]

                if len(coordenadas_gps) >= 4:
                    poly_shapely = Polygon(coordenadas_gps)

                    from pyproj import Geod

                    geod = Geod(ellps="WGS84")
                    area_m2, perimetro_m = geod.geometry_area_perimeter(
                        poly_shapely
                    )

                    area_real_m2 = abs(float(area_m2))
                    perimetro_m = abs(float(perimetro_m))
                    superficie_ha = area_real_m2 / 10000.0

                    # Shapely recibe el polígono como [longitud, latitud].
                    lat_centro = float(poly_shapely.centroid.y)
                    lon_centro = float(poly_shapely.centroid.x)

                    coordenadas_anteriores = st.session_state.get(
                        "plano_coordenadas_gps"
                    )
                    poligono_cambio = coordenadas_anteriores != coordenadas_gps

                    # IMPORTANTE: guardar todo antes de cualquier rerun.
                    st.session_state.update(
                        {
                            "lat_centro": lat_centro,
                            "lon_centro": lon_centro,
                            "plano_coordenadas_gps": coordenadas_gps,
                            "plano_area_real_m2": area_real_m2,
                            "plano_superficie_ha": superficie_ha,
                            "plano_perimetro_m": perimetro_m,
                            "plano_largo_matriz_m": (
                                estimar_longitud_matriz_desde_perimetro(
                                    perimetro_m
                                )
                            ),
                            "metodo_longitudes_red": (
                                "estimacion_geometrica_cuadrado_equivalente"
                            ),
                            "trazado_real_disponible": False,
                            "predio_delimitado": True,
                        }
                    )

                    # Altitud del centroide.
                    altitud_predio = obtener_altitud_openmeteo(
                        lat_centro,
                        lon_centro,
                    )

                    if altitud_predio is not None:
                        st.session_state["alt_def"] = float(altitud_predio)
                        st.session_state["fuente_altitud"] = (
                            "Open-Meteo Elevation / Copernicus DEM GLO-90"
                        )
                    else:
                        st.session_state["alt_def"] = None
                        st.session_state["fuente_altitud"] = "No disponible"

                    # Si cambia el predio, invalidar resultados derivados.
                    if poligono_cambio:
                        st.session_state["datos_agronomicos_listos"] = False
                        st.session_state["riego_configurado"] = False

                        for clave in (
                            "necesidad_total",
                            "etc",
                            "eto_final",
                            "q_tot",
                            "caudal_sector",
                            "tdh",
                            "hp_req",
                            "seleccion_bomba_v2",
                            "alternativas_bombeo_v2",
                            "presupuesto_total",
                        ):
                            st.session_state.pop(clave, None)

                        # Reconstruye el mapa ya con el polígono persistido.
                        st.rerun()

                    st.success("✅ Terreno capturado satelitalmente.")

                    c_gps1, c_gps2, c_gps3, c_gps4 = st.columns(4)

                    with c_gps1:
                        kpi_card(
                            "Área Real",
                            f"{superficie_ha:.2f} ha",
                            tono="good",
                        )

                    with c_gps2:
                        kpi_card(
                            "Perímetro",
                            f"{perimetro_m:.0f} m",
                        )

                    with c_gps3:
                        kpi_card(
                            "Lat/Lon",
                            f"{lat_centro:.4f}, {lon_centro:.4f}",
                        )

                    with c_gps4:
                        if altitud_predio is not None:
                            kpi_card(
                                "Altitud",
                                f"{altitud_predio:.0f} m s.n.m.",
                                sub="Open-Meteo Elevation",
                                tono="good",
                            )
                        else:
                            kpi_card(
                                "Altitud",
                                "No disponible",
                                tono="warn",
                            )

                else:
                    st.warning(
                        "⚠️ El polígono debe contener al menos tres vértices válidos."
                    )

            else:
                # Después de st.rerun(), streamlit-folium puede no devolver
                # all_drawings. Recuperamos entonces el predio persistido.
                area_recuperada = st.session_state.get("plano_area_real_m2")
                coordenadas_recuperadas = st.session_state.get(
                    "plano_coordenadas_gps"
                )

                if area_recuperada and coordenadas_recuperadas:
                    st.session_state["predio_delimitado"] = True

                    st.success(
                        "✅ Predio delimitado y recuperado correctamente."
                    )

                    k_area, k_perimetro, k_centro, k_altitud = st.columns(4)

                    with k_area:
                        kpi_card(
                            "Área guardada",
                            f"{float(area_recuperada) / 10000:.2f} ha",
                            tono="good",
                        )

                    with k_perimetro:
                        kpi_card(
                            "Perímetro guardado",
                            f"{float(st.session_state.get('plano_perimetro_m', 0.0)):.0f} m",
                        )

                    with k_centro:
                        if (
                            lat_centro_guardado is not None
                            and lon_centro_guardado is not None
                        ):
                            kpi_card(
                                "Centro del predio",
                                f"{float(lat_centro_guardado):.4f}, "
                                f"{float(lon_centro_guardado):.4f}",
                            )
                        else:
                            kpi_card(
                                "Centro del predio",
                                "No disponible",
                                tono="warn",
                            )

                    with k_altitud:
                        altitud_guardada = st.session_state.get("alt_def")
                        if altitud_guardada is not None:
                            kpi_card(
                                "Altitud",
                                f"{float(altitud_guardada):.0f} m s.n.m.",
                                sub=st.session_state.get(
                                    "fuente_altitud",
                                    "Open-Meteo Elevation",
                                ),
                                tono="good",
                            )
                        else:
                            kpi_card(
                                "Altitud",
                                "No disponible",
                                tono="warn",
                            )

                    st.caption(
                        "El mapa se centra automáticamente sobre el predio "
                        "guardado. Puedes editar o eliminar el polígono para "
                        "actualizar el diseño."
                    )
                else:
                    st.session_state["predio_delimitado"] = False
                    st.caption(
                        "Dibuja un polígono sobre el mapa para calcular área, "
                        "perímetro, centroide y altitud."
                    )

            coordenadas_predio = st.session_state.get("plano_coordenadas_gps")
            ubicacion_predio = None
            error_ubicacion = None
            if coordenadas_predio:
                try:
                    coordenadas_cache = tuple(
                        (float(longitud), float(latitud))
                        for longitud, latitud in coordenadas_predio
                    )
                    ubicacion_predio = identificar_ubicacion_predio(
                        coordenadas_cache
                    )
                except (
                    requests.RequestException,
                    ValueError,
                    KeyError,
                    TypeError,
                ) as error:
                    error_ubicacion = error

                st.session_state["comuna_predio"] = (
                    None if ubicacion_predio is None else ubicacion_predio["comuna"]
                )
                st.session_state["comunas_predio"] = (
                    [] if ubicacion_predio is None else ubicacion_predio["comunas"]
                )
                st.session_state["region_predio"] = (
                    None if ubicacion_predio is None else ubicacion_predio["region"]
                )
                st.session_state["regiones_predio"] = (
                    [] if ubicacion_predio is None else ubicacion_predio["regiones"]
                )
                st.session_state["pais_predio"] = (
                    None if ubicacion_predio is None else ubicacion_predio["pais"]
                )

            with st.container(border=True):
                st.markdown("**Ubicación del predio**")
                if not coordenadas_predio:
                    st.caption(
                        "Delimita el terreno para identificar comuna y región."
                    )
                elif ubicacion_predio is None:
                    st.info("Ubicación no disponible.")
                    if error_ubicacion is not None:
                        st.caption(
                            "No fue posible consultar los límites administrativos. "
                            "El diseño y sus cálculos continúan disponibles."
                        )
                else:
                    comuna_visible = (
                        ubicacion_predio["comuna"]
                        or "Varias: " + ", ".join(ubicacion_predio["comunas"])
                    )
                    region_visible = (
                        ubicacion_predio["region"]
                        or (
                            ", ".join(ubicacion_predio["regiones"])
                            if ubicacion_predio["regiones"]
                            else "No disponible"
                        )
                    )
                    st.markdown(f"**Comuna:** {comuna_visible}")
                    st.markdown(f"**Región:** {region_visible}")
                    st.markdown(f"**País:** {ubicacion_predio['pais']}")
                    if len(ubicacion_predio["comunas"]) > 1:
                        st.warning(
                            "El predio intersecta más de una comuna; no se "
                            "asigna una comuna única."
                        )
                    if len(ubicacion_predio["regiones"]) > 1:
                        st.warning(
                            "El predio intersecta más de una región."
                        )
                st.caption(
                    "Límites administrativos: [geoBoundaries]"
                    "(https://www.geoboundaries.org/), "
                    "comunas y regiones de Chile (BCN/OCHA ROLAC, CC BY 3.0 IGO)."
                )

        # ----------------------------------------------------
        # PASO 2: PARÁMETROS AGRONÓMICOS Y CLIMÁTICOS
        # ----------------------------------------------------
        with st.expander(
            "☁️ Paso 2: Parámetros Agronómicos y Climáticos",
            expanded=False,
        ):
            c_cult, c_temp = st.columns(2)

            with c_cult:
                cultivo = st.selectbox(
                    "Especie agrícola a evaluar",
                    [
                        "Avellano Europeo",
                        "Manzano",
                        "Vid Vinífera",
                        "Nogal",
                        "Otro",
                    ],
                    key="cultivo_diseno",
                )

            with c_temp:
                temporada = st.selectbox(
                    "Temporada de Diseño",
                    [
                        "Verano (Máxima Demanda)",
                        "Primavera",
                        "Otoño",
                        "Invierno",
                    ],
                    key="temporada_diseno",
                )

            kc_referencia = {
                "Avellano Europeo": 0.95,
                "Manzano": 1.05,
                "Vid Vinífera": 0.80,
                "Nogal": 1.10,
                "Otro": 1.00,
            }

            st.markdown("#### Fuente de información climática")

            modo_clima = "📡 Automático - Open-Meteo"

            # Si el usuario cambia de modo, invalidamos el cálculo anterior.
            if st.session_state.get("modo_clima_activo") != modo_clima:
                st.session_state["modo_clima_activo"] = modo_clima
                st.session_state["datos_agronomicos_listos"] = False
                st.session_state["necesidad_total"] = None
                st.session_state["etc"] = None
                st.session_state["eto_final"] = None
                st.session_state["riego_configurado"] = False

            # =================================================
            # MODO AUTOMÁTICO
            # =================================================
            if modo_clima == "📡 Automático - Open-Meteo":
                st.info(
                    "Los parámetros climáticos se obtendrán automáticamente "
                    "usando las coordenadas del predio."
                )

                if (
                    "lat_centro" not in st.session_state
                    or "lon_centro" not in st.session_state
                ):
                    st.warning(
                        "⚠️ Primero debes delimitar el predio en el Paso 1."
                    )
                    st.session_state["datos_agronomicos_listos"] = False
                    st.session_state["necesidad_total"] = None

                else:
                    lat = float(st.session_state["lat_centro"])
                    lon = float(st.session_state["lon_centro"])

                    if st.button(
                        "📡 Extraer Promedios Satelitales",
                        type="primary",
                    ):
                        with st.spinner(
                            f"Consultando datos climáticos de {temporada}..."
                        ):
                            t, h, v, eto = obtener_clima_satelital(
                                lat,
                                lon,
                                temporada,
                            )
                            alt = obtener_altitud_openmeteo(
                                lat,
                                lon,
                            )

                        if all(
                            valor is not None
                            for valor in [t, h, v, eto, alt]
                        ):
                            st.session_state["temp_auto"] = float(t)
                            st.session_state["hr_auto"] = float(h)
                            st.session_state["viento_auto"] = float(v)
                            st.session_state["eto_auto"] = float(eto)
                            st.session_state["alt_auto"] = float(alt)

                            st.session_state["temporada_auto"] = temporada
                            st.session_state["lat_auto"] = lat
                            st.session_state["lon_auto"] = lon

                            # Mantiene sincronizada la altitud visible del predio.
                            st.session_state["alt_def"] = float(alt)

                            st.success(
                                "✅ Datos climáticos y altitud obtenidos correctamente."
                            )
                        else:
                            st.error(
                                "❌ No fue posible obtener todos los datos desde Open-Meteo. "
                                "Revisa la conexión y vuelve a intentarlo."
                            )

                    datos_auto_validos = (
                        "eto_auto" in st.session_state
                        and st.session_state.get("temporada_auto") == temporada
                        and abs(
                            float(st.session_state.get("lat_auto", 999.0)) - lat
                        ) < 1e-8
                        and abs(
                            float(st.session_state.get("lon_auto", 999.0)) - lon
                        ) < 1e-8
                    )

                    if datos_auto_validos:
                        temp = float(st.session_state["temp_auto"])
                        hr = float(st.session_state["hr_auto"])
                        viento = float(st.session_state["viento_auto"])
                        eto_final = float(st.session_state["eto_auto"])
                        alt = float(st.session_state["alt_auto"])
                        kc = float(kc_referencia[cultivo])

                        etc, necesidad_total = calcular_demanda_agronomica(
                            eto_final,
                            kc,
                            0.90,
                            0.90,
                        )

                        st.session_state["eto_final"] = eto_final
                        st.session_state["etc"] = etc
                        st.session_state["necesidad_total"] = necesidad_total
                        st.session_state["datos_agronomicos_listos"] = True
                        st.session_state["fuente_clima"] = "Open-Meteo"

                        st.markdown("#### 📡 Datos obtenidos automáticamente")

                        a1, a2, a3, a4 = st.columns(4)

                        with a1:
                            kpi_card(
                                "Temperatura",
                                f"{temp:.2f} °C",
                            )
                        with a2:
                            kpi_card(
                                "Humedad Relativa",
                                f"{hr:.1f} %",
                            )
                        with a3:
                            kpi_card(
                                "Viento",
                                f"{viento:.2f} m/s",
                            )
                        with a4:
                            kpi_card(
                                "Altitud",
                                f"{alt:.0f} m s.n.m.",
                                sub="Open-Meteo Elevation",
                                tono="good",
                            )

                        b1, b2, b3, b4 = st.columns(4)

                        with b1:
                            kpi_card(
                                "ETo",
                                f"{eto_final:.2f} mm/día",
                            )
                        with b2:
                            kpi_card(
                                "Kc",
                                f"{kc:.2f}",
                                sub=cultivo,
                            )
                        with b3:
                            kpi_card(
                                "ETc",
                                f"{etc:.2f} mm/día",
                            )
                        with b4:
                            kpi_card(
                                "Necesidad Total (NT)",
                                f"{necesidad_total:.2f} mm/día",
                                tono="good",
                            )
                    else:
                        st.session_state["datos_agronomicos_listos"] = False
                        st.session_state["necesidad_total"] = None
                        st.caption(
                            "Presiona «Extraer Promedios Satelitales» para obtener "
                            "los parámetros correspondientes al predio y temporada actual."
                        )

        # ----------------------------------------------------
        # PASO 3: SUELO
        # ----------------------------------------------------
        with st.expander(
            "🟤 Paso 3: Textura del Suelo",
            expanded=False,
        ):
            tipo_suelo = st.selectbox(
                "Textura Predominante",
                [
                    "Arcilloso",
                    "Franco-Arcilloso",
                    "Franco",
                    "Franco-Arenoso",
                    "Arenoso",
                ],
                index=2,
                key="tipo_suelo_diseno",
            )

            v_inf_num, v_inf_rango, clasificacion, descripcion = evaluar_suelo(
                tipo_suelo
            )

            col_s1, col_s2 = st.columns([1, 2])

            with col_s1:
                kpi_card(
                    "Vel. Infiltración",
                    v_inf_rango,
                    sub=clasificacion,
                )

            with col_s2:
                st.info(f"**Recomendación:** {descripcion}")

        # ----------------------------------------------------
        # PASO 4: OPERACIÓN Y EMISORES
        # ----------------------------------------------------
        with st.expander(
            "⚙️ Paso 4: Configuración de Riego y Geometría",
            expanded=False,
        ):
            area_real = float(
                st.session_state.get(
                    "plano_area_real_m2",
                    0.0,
                ) or 0.0
            )

            coordenadas_predio_paso4 = st.session_state.get(
                "plano_coordenadas_gps"
            )

            predio_delimitado = bool(
                coordenadas_predio_paso4
                and area_real > 0
            )

            st.session_state["predio_delimitado"] = predio_delimitado

            necesidad_total = st.session_state.get(
                "necesidad_total"
            )

            if not predio_delimitado:
                st.warning(
                    "⚠️ Delimita y confirma tu predio en el Paso 1 antes "
                    "de dimensionar la red."
                )
                st.session_state["riego_configurado"] = False

            elif (
                not st.session_state.get(
                    "datos_agronomicos_listos",
                    False,
                )
                or necesidad_total is None
            ):
                st.warning(
                    "⚠️ Completa el Paso 2 para calcular la Necesidad Total de Riego (NT)."
                )
                st.session_state["riego_configurado"] = False

            else:
                st.success(
                    f"✅ Calculando red hidráulica en base a "
                    f"{area_real / 10000:.2f} hectáreas digitalizadas."
                )

                # Aproximación geométrica equivalente cuadrada.
                ancho_terreno = math.sqrt(area_real)
                largo_terreno = math.sqrt(area_real)

                tecnica_riego = st.selectbox(
                    "Técnica a implementar",
                    [
                        "Aspersión",
                        "Microaspersión",
                        "Goteo",
                    ],
                    index=2,
                    key="tecnica_riego_seleccion",
                )

                if tecnica_riego in [
                    "Aspersión",
                    "Microaspersión",
                ]:
                    try:
                        fichas_emisores, fichas_pendientes = (
                            cargar_catalogo_fichas_emisores()
                        )
                    except (OSError, ValueError) as exc:
                        st.error(f"No se pudo cargar el catálogo de fichas: {exc}")
                        fichas_emisores, fichas_pendientes = [], 0

                    fichas_tecnica = [
                        ficha
                        for ficha in fichas_emisores
                        if ficha["tecnica"] == tecnica_riego
                    ]
                    opciones_ficha = {
                        f'{ficha["codigo"]} — {ficha["nombre"]}': ficha
                        for ficha in fichas_tecnica
                    }
                    etiqueta_manual = "Parámetros manuales/preliminares"
                    seleccion_ficha = st.selectbox(
                        "Emisor con ficha técnica",
                        [etiqueta_manual, *opciones_ficha],
                        index=1 if opciones_ficha else 0,
                        key=f"ficha_emisor_{tecnica_riego}",
                        help=(
                            "Solo se ofrecen como verificados los registros "
                            "completos marcados como validados en el catálogo local."
                        ),
                    )
                    ficha_emisor = opciones_ficha.get(seleccion_ficha)
                    parametros_preliminares = (
                        PARAMETROS_EMISOR_PRELIMINARES[tecnica_riego]
                    )

                    if ficha_emisor:
                        radio_emisor = ficha_emisor["radio_cobertura_m"]
                        caudal_emisor_lh = ficha_emisor["caudal_lh"]
                        presion_emisor_mca = ficha_emisor[
                            "presion_operacion_mca"
                        ]
                        st.info(
                            f"Ficha {ficha_emisor['codigo']}: "
                            f"{caudal_emisor_lh:.2f} L/h, "
                            f"{presion_emisor_mca:.2f} m.c.a., "
                            f"radio {radio_emisor:.2f} m. Fuente: "
                            f"{ficha_emisor['fuente_ficha']} "
                            f"({ficha_emisor['fecha_ficha']})."
                        )
                    else:
                        st.warning(
                            "No hay una ficha técnica local seleccionada. "
                            "Los valores heredados son solo referencias "
                            "preliminares y no están validados para el emisor."
                        )
                        c_p1, c_p2, c_p3 = st.columns(3)
                        with c_p1:
                            radio_emisor = st.number_input(
                                "Radio de cobertura (m)",
                                min_value=0.1,
                                value=parametros_preliminares[
                                    "radio_cobertura_m"
                                ],
                                step=0.5,
                                key=f"radio_emisor_{tecnica_riego}",
                            )
                        with c_p2:
                            caudal_emisor_lh = st.number_input(
                                "Caudal del emisor (L/h)",
                                min_value=0.1,
                                value=parametros_preliminares["caudal_lh"],
                                step=10.0,
                                key=f"caudal_emisor_lh_{tecnica_riego}",
                            )
                        with c_p3:
                            presion_emisor_mca = st.number_input(
                                "Presión de operación (m.c.a.)",
                                min_value=0.1,
                                value=parametros_preliminares[
                                    "presion_operacion_mca"
                                ],
                                step=0.5,
                                key=f"presion_emisor_{tecnica_riego}",
                            )
                    st.caption(
                        f"Fichas locales pendientes de validación: "
                        f"{fichas_pendientes}. El dato de presión se transferirá "
                        "al cálculo hidráulico."
                    )

                    factor_traslape = st.number_input(
                        "Factor de separación geométrica (sin validar)",
                        min_value=0.01,
                        value=parametros_preliminares["factor_traslape"],
                        step=0.01,
                        format="%.3f",
                        key=f"factor_traslape_{tecnica_riego}",
                    )
                    caudal_emisor = caudal_emisor_lh / 3600.0

                    (
                        nx,
                        ny,
                        tot_emi,
                        q_tot,
                        m_prin,
                        m_lat,
                        m_tot,
                    ) = generar_red_aspertension(
                        ancho_terreno,
                        largo_terreno,
                        radio_emisor,
                        caudal_emisor,
                        factor_traslape,
                    )

                    pp_horaria = (
                        (q_tot * 3600.0) / area_real
                        if area_real > 0
                        else 0.0
                    )
                    st.session_state.update(
                        {
                            "ficha_emisor_seleccionada": ficha_emisor,
                            "codigo_ficha_emisor": (
                                ficha_emisor["codigo"] if ficha_emisor else None
                            ),
                            "parametros_emisor_verificados": bool(ficha_emisor),
                            "presion_operacion_emisor_mca": float(
                                presion_emisor_mca
                            ),
                            "fuente_parametros_emisor": (
                                ficha_emisor["fuente_ficha"]
                                if ficha_emisor
                                else "Parámetros heredados/manuales sin ficha verificada"
                            ),
                        }
                    )

                else:
                    st.session_state.update(
                        {
                            "ficha_emisor_seleccionada": None,
                            "codigo_ficha_emisor": None,
                            "parametros_emisor_verificados": False,
                            "fuente_parametros_emisor": None,
                        }
                    )
                    c_p1, c_p2, c_p3 = st.columns(3)

                    with c_p1:
                        dist_hileras = st.number_input(
                            "Dist. hileras (m)",
                            min_value=0.1,
                            value=2.0,
                            step=0.1,
                            key="dist_hileras_riego",
                        )

                    with c_p2:
                        dist_goteros = st.number_input(
                            "Dist. goteros (m)",
                            min_value=0.1,
                            value=0.5,
                            step=0.1,
                            key="dist_goteros_riego",
                        )

                    with c_p3:
                        caudal_emisor = st.number_input(
                            "Caudal gotero (L/h)",
                            min_value=0.1,
                            value=2.0,
                            step=0.1,
                            key="caudal_gotero_riego",
                        )

                    (
                        nx,
                        ny,
                        tot_emi,
                        q_tot,
                        m_prin,
                        m_lat,
                        m_tot,
                    ) = generar_red_goteo(
                        ancho_terreno,
                        largo_terreno,
                        dist_hileras,
                        dist_goteros,
                        caudal_emisor,
                    )

                    pp_horaria = (
                        caudal_emisor
                        / (dist_hileras * dist_goteros)
                        if dist_hileras > 0 and dist_goteros > 0
                        else 0.0
                    )

                # La tubería matriz se aproxima con la estimación derivada
                # del perímetro geodésico calculado en el Paso 1.
                m_prin = float(
                    st.session_state.get(
                        "plano_largo_matriz_m",
                        m_prin,
                    )
                )
                m_tot = math.fsum((m_prin, m_lat))

                if pp_horaria > 0:
                    tiempo_riego = float(necesidad_total) / pp_horaria
                else:
                    tiempo_riego = 0.0

                c_op1, c_op2, c_op3, c_op4 = st.columns(4)

                with c_op1:
                    kpi_card(
                        "Necesidad Total (NT)",
                        f"{float(necesidad_total):.2f} mm/día",
                    )

                with c_op2:
                    kpi_card(
                        "Precipitación (Pp)",
                        f"{pp_horaria:.2f} mm/h",
                    )

                with c_op3:
                    kpi_card(
                        "Tiempo de Riego (TR)",
                        f"{tiempo_riego:.2f} h/turno",
                        sub="TR = NT / Pp",
                        tono="good",
                    )

                with c_op4:
                    horas_jornada = st.number_input(
                        "Horas operativas caseta",
                        min_value=1,
                        max_value=24,
                        value=18,
                        key="horas_jornada_riego",
                    )

                # Mantiene la lógica solicitada para dimensionar sectores.
                num_sectores = (
                    max(
                        1,
                        math.ceil(
                            horas_jornada / tiempo_riego
                        ),
                    )
                    if tiempo_riego > 0
                    else 1
                )

                if pp_horaria > v_inf_num:
                    st.warning(
                        f"⚠️ La intensidad de aplicación ({pp_horaria:.2f} mm/h) "
                        f"supera la velocidad de infiltración de referencia "
                        f"({v_inf_num:.2f} mm/h) para suelo {tipo_suelo}."
                    )

                st.session_state.update(
                    {
                        "num_sectores": num_sectores,
                        "q_tot": float(q_tot),
                        "m_prin": float(m_prin),
                        "m_lat": float(m_lat),
                        "m_tot": float(m_tot),
                        "tot_emi": int(tot_emi),
                        "tecnica_riego": tecnica_riego,
                        "metodo_longitudes_red": (
                            "estimacion_geometrica_cuadrado_equivalente"
                        ),
                        "trazado_real_disponible": False,
                        "pp_horaria": float(pp_horaria),
                        "tiempo_riego": float(tiempo_riego),
                        "riego_configurado": True,
                    }
                )

                st.caption(
                    f"Configuración: {int(tot_emi):,} emisores · "
                    f"{float(m_prin):,.1f} m de matriz · "
                    f"{float(m_lat):,.1f} m de laterales · "
                    f"{float(m_tot):,.1f} m total estimado."
                )
                st.warning(
                    "Estas longitudes son estimaciones geométricas: el terreno "
                    "se aproxima por un cuadrado equivalente, los laterales se "
                    "calculan por separación y la matriz como perímetro/2,5. "
                    "La aplicación no genera un trazado real de tuberías; "
                    "estos resultados son preliminares, no un diseño definitivo."
                )
                if tecnica_riego in {"Aspersión", "Microaspersión"} and not st.session_state.get(
                    "parametros_emisor_verificados",
                    False,
                ):
                    st.warning(
                        "Caudal, presión, alcance y separación del emisor no "
                        "están respaldados por una ficha técnica verificada."
                    )

        _mostrar_navegacion_pat(0)

    # ========================================================
    # PESTAÑA 2: ANÁLISIS HIDRÁULICO
    # ========================================================
    with tab_hidraulica:
        section_title("💧 Cálculos Hidráulicos Sectorizados")

        if not st.session_state.get(
            "riego_configurado",
            False,
        ):
            st.warning(
                "⚠️ Completa primero los pasos 1, 2 y 4 en "
                "«Diseño del Terreno» para habilitar el análisis hidráulico."
            )

        else:
            q_tot = float(st.session_state["q_tot"])
            m_prin = float(st.session_state["m_prin"])
            m_lat = float(st.session_state["m_lat"])
            tot_emi = int(st.session_state["tot_emi"])
            tecnica_riego = st.session_state["tecnica_riego"]

            num_sectores = int(
                st.session_state.get(
                    "num_sectores",
                    1,
                )
            )

            caudal_sector = (
                q_tot / num_sectores
                if num_sectores > 0
                else q_tot
            )

            c_sec1, c_sec2, c_sec3 = st.columns(3)

            with c_sec1:
                kpi_card(
                    "N° de Sectores",
                    f"{num_sectores}",
                )

            with c_sec2:
                kpi_card(
                    "Caudal por Sector",
                    f"{caudal_sector:.2f} L/s",
                )

            with c_sec3:
                kpi_card(
                    "Tiempo de Riego",
                    f"{st.session_state.get('tiempo_riego', 0.0):.2f} h",
                    sub="por turno",
                )

            st.markdown("---")

            col_h1, col_h2 = st.columns(2)

            with col_h1:
                diametro_matriz = st.number_input(
                    "Diámetro Matriz (mm)",
                    min_value=1.0,
                    value=160.0,
                    step=10.0,
                    key="diametro_matriz_input",
                )

                coef_hazen = st.number_input(
                    "Coef. Hazen-Williams",
                    min_value=1,
                    value=150,
                    key="coef_hazen_input",
                )

                altura_estatica = st.number_input(
                    "Altura estática (m)",
                    value=5.0,
                    step=0.5,
                    key="altura_estatica_input",
                )

                perdida_acc = st.number_input(
                    "Pérdidas accesorios (m.c.a.)",
                    min_value=0.0,
                    value=1.5,
                    step=0.1,
                    key="perdida_acc_input",
                )

                presion_emisor = st.number_input(
                    "Presión emisor (m.c.a.)",
                    min_value=0.0,
                    value=float(
                        st.session_state.get(
                            "presion_operacion_emisor_mca",
                            10.0 if tecnica_riego == "Goteo" else 25.0,
                        )
                    ),
                    step=0.5,
                    key=(
                        "presion_hidraulica_emisor_"
                        + str(
                            st.session_state.get("codigo_ficha_emisor")
                            or tecnica_riego
                        )
                    ),
                )
                if (
                    tecnica_riego in {"Aspersión", "Microaspersión"}
                    and not st.session_state.get(
                        "parametros_emisor_verificados",
                        False,
                    )
                ):
                    st.warning(
                        "La presión de operación usada no está validada con "
                        "una ficha del emisor seleccionado."
                    )

                eficiencia_bomba = (
                    st.slider(
                        "Eficiencia bomba (%)",
                        40,
                        90,
                        70,
                        key="eficiencia_bomba_diseno_slider",
                    )
                    / 100.0
                )

            with col_h2:
                perdida_matriz = calcular_hazen_williams(
                    m_prin,
                    caudal_sector,
                    diametro_matriz,
                    coef_hazen,
                )

                tdh, hp_req = calcular_tdh_y_potencia(
                    altura_estatica,
                    perdida_matriz,
                    perdida_acc,
                    presion_emisor,
                    caudal_sector,
                    eficiencia_bomba,
                )

                kpi_card(
                    "Pérdida por Fricción",
                    f"{perdida_matriz:.2f} m.c.a.",
                )

                kpi_card(
                    "Altura Dinámica Total (TDH)",
                    f"{tdh:.2f} m.c.a.",
                    tono="good",
                )

                kpi_card(
                    "Potencia Requerida",
                    f"{hp_req:.2f} HP",
                )

            st.session_state.update(
                {
                    "caudal_sector": caudal_sector,
                    "tdh": tdh,
                    "hp_req": hp_req,
                    "m_prin": m_prin,
                    "m_lat": m_lat,
                    "tot_emi": tot_emi,
                    "diametro_matriz": diametro_matriz,
                    "tecnica_riego": tecnica_riego,
                    # Parámetros necesarios para reconstruir la curva del sistema.
                    "coef_hazen": coef_hazen,
                    "altura_estatica": altura_estatica,
                    "perdida_matriz_ref": perdida_matriz,
                    "perdida_acc_ref": perdida_acc,
                    "presion_emisor": presion_emisor,
                    "eficiencia_bomba_diseno": eficiencia_bomba,
                }
            )

        _mostrar_navegacion_pat(1)

    # ========================================================
    # PESTAÑA 3: SELECCIÓN DE EQUIPOS
    # ========================================================
    with tab_equipos:
        section_title("⚙️ Optimizador Serie/Paralelo + Curvas Q-H + Mercado")

        if "tdh" not in st.session_state:
            st.warning("⚠️ Complete el Análisis Hidráulico primero.")
        else:
            caudal_sector = float(st.session_state["caudal_sector"])
            tdh = float(st.session_state["tdh"])
            hp_req = float(st.session_state["hp_req"])

            st.caption(
                "Flujo V2: cálculo determinista → optimización serie/paralelo → curvas Q-H "
                "→ Tavily/Mercado Libre → SQL histórico → selección técnico-económica."
            )

            ccrit, cp, cs, ct = st.columns(4)
            with ccrit:
                criterio_ui = st.selectbox(
                    "Criterio de optimización",
                    ["Balance técnico-económico", "Menor inversión inicial", "Menor número de bombas"],
                    index=0,
                )
            with cp:
                max_paralelo = st.number_input("Máx. paralelo", 1, 20, 10)
            with cs:
                max_serie = st.number_input("Máx. serie", 1, 10, 5)
            with ct:
                max_total = st.number_input("Máx. bombas", 1, 50, 20)

            mapa_criterio = {
                "Balance técnico-económico": "balanceado",
                "Menor inversión inicial": "menor_costo",
                "Menor número de bombas": "menor_numero",
            }
            criterio = mapa_criterio[criterio_ui]
            parametros_opt = ParametrosOptimizacion(
                max_paralelo=int(max_paralelo), max_serie=int(max_serie),
                max_total_bombas=int(max_total), margen_caudal=1.10, margen_altura=1.00,
            )

            # Curva del sistema reconstruida a partir del cálculo hidráulico ya realizado.
            h_sistema = construir_curva_sistema(
                q_ref_ls=caudal_sector,
                altura_estatica_m=float(st.session_state.get("altura_estatica", 0.0)),
                presion_emisor_mca=float(st.session_state.get("presion_emisor", 0.0)),
                perdida_friccion_ref_mca=float(st.session_state.get("perdida_matriz_ref", 0.0)),
                perdida_accesorios_ref_mca=float(st.session_state.get("perdida_acc_ref", 0.0)),
            )
            curvas = cargar_curvas_bombas()

            # 1) Preselección técnica (sin forzar precios web aún).
            pre = optimizar_estacion_bombeo(
                caudal_sector, tdh, df_bomb, curvas=curvas, h_sistema=h_sistema,
                criterio="menor_numero", parametros=parametros_opt,
            )

            st.session_state["estimacion_williams_bomba"] = None
            st.session_state["fuente_precio_bomba"] = None
            if pre["mejor"] is None:
                st.error("No existe una configuración factible dentro de los límites definidos del catálogo maestro.")
                firma = f"{caudal_sector:.3f}-{tdh:.3f}-{hp_req:.3f}"
                if st.session_state.get("firma_busqueda_externa") != firma:
                    with st.spinner("Buscando candidatos externos que requerirán validación HITL..."):
                        candidatos_web, errores_web = buscar_candidatos_web(caudal_sector, tdh, hp_req)
                    st.session_state["firma_busqueda_externa"] = firma
                    st.session_state["candidatos_web"] = candidatos_web
                    st.session_state["errores_web"] = errores_web

                for err in st.session_state.get("errores_web", []):
                    st.warning(err)
                candidatos_web = st.session_state.get("candidatos_web", [])
                if candidatos_web:
                    st.warning("Se encontraron equipos externos. NO se incorporan a Bombas hasta validación humana.")
                    st.dataframe(pd.DataFrame(candidatos_web), width="stretch", hide_index=True)
                    st.info(
                        "Hay candidatos web pendientes de validación humana. "
                        "No se calcula Williams hasta confirmar que no existe "
                        "un producto apto."
                    )
                    st.session_state["costo_bombas"] = 0.0
                elif st.session_state.get("errores_web"):
                    st.warning(
                        "La búsqueda externa no pudo completarse. No se estima "
                        "un precio por Williams porque no se confirmó la ausencia "
                        "de equipos aptos."
                    )
                    st.session_state["costo_bombas"] = 0.0
                else:
                    precios_referencia = obtener_precios_mercado(horas=168)
                    bombas_referencia = df_bomb.copy()
                    if not precios_referencia.empty:
                        bombas_referencia = bombas_referencia.merge(
                            precios_referencia[["id_bomba", "precio_mercado_clp"]],
                            on="id_bomba",
                            how="left",
                        )
                    estimacion = estimar_costo_bomba_williams(
                        caudal_sector, bombas_referencia
                    )
                    if estimacion is None:
                        st.warning(
                            "La búsqueda externa finalizó sin encontrar una bomba "
                            "apta, pero no hay una bomba de referencia con precio "
                            "y caudal conocidos. No es posible calcular Williams."
                        )
                        st.session_state["costo_bombas"] = 0.0
                    else:
                        st.session_state["estimacion_williams_bomba"] = estimacion
                        st.session_state["costo_bombas"] = float(
                            estimacion["costo_estimado_clp"]
                        )
                        st.session_state["fuente_precio_bomba"] = (
                            "Estimación referencial por método de Williams"
                        )
                        st.warning(
                            "No se encontró una bomba disponible que cumpla las "
                            "especificaciones hidráulicas requeridas. El siguiente "
                            "monto es una **estimación referencial por el método de "
                            "Williams**, no un precio real, cotización ni confirmación "
                            "de disponibilidad."
                        )
                        st.metric(
                            "Costo referencial estimado por Williams",
                            f"${estimacion['costo_estimado_clp']:,.0f} CLP",
                            help="Estimación basada en caudal; no valida altura dinámica total.",
                        )
                        st.caption(
                            f"Rango indicativo por exponente (0,52–0,76): "
                            f"${estimacion['rango_min_clp']:,.0f}–"
                            f"${estimacion['rango_max_clp']:,.0f} CLP. "
                            f"Referencia: {estimacion['modelo_referencia']} "
                            f"({estimacion['caudal_referencia_ls']:.2f} L/s, "
                            f"${estimacion['precio_referencia_clp']:,.0f} CLP; "
                            f"{estimacion['fuente_precio_referencia']}). "
                            f"Caudal objetivo: {estimacion['caudal_objetivo_ls']:.2f} "
                            f"L/s; n={estimacion['exponente_williams']:.1f}. "
                            "El método solo escala por caudal y no comprueba que una "
                            "bomba real satisfaga la TDH del proyecto."
                        )
                st.session_state["seleccion_bomba_v2"] = None
            else:
                candidatos_tecnicos = pre["candidatos"]

                # 2) Mercado automático. Las API solo se consultan si SQL no posee precio fresco <24h.
                with st.spinner("🔎 Verificando mercado y persistiendo referencias en SQL..."):
                    resumen_busqueda = actualizar_mercado_bombas(
                        candidatos_tecnicos, caudal_sector, tdh,
                        max_candidatos=6, vigencia_horas=24,
                    )

                # 3) Leer SIEMPRE el precio nuevamente desde SQL.
                precios_mercado = obtener_precios_mercado(horas=168)
                df_bomb_mercado = df_bomb.copy()
                if not precios_mercado.empty:
                    df_bomb_mercado = df_bomb_mercado.merge(precios_mercado, on="id_bomba", how="left")
                    df_bomb_mercado["precio_seleccion_clp"] = pd.to_numeric(
                        df_bomb_mercado["precio_mercado_clp"], errors="coerce"
                    ).fillna(pd.to_numeric(df_bomb_mercado["precio_ref_clp"], errors="coerce"))
                else:
                    df_bomb_mercado["precio_seleccion_clp"] = pd.to_numeric(
                        df_bomb_mercado["precio_ref_clp"], errors="coerce"
                    )

                # 4) Optimización final con precio representativo SQL.
                opt = optimizar_estacion_bombeo(
                    caudal_sector, tdh, df_bomb_mercado, curvas=curvas, h_sistema=h_sistema,
                    criterio=criterio, parametros=parametros_opt,
                )
                resultado_bomba = opt["mejor"]

                if resultado_bomba is None:
                    st.error("La actualización de mercado no dejó una alternativa seleccionable.")
                    st.session_state["costo_bombas"] = 0.0
                else:
                    validacion = resultado_bomba["estado_validacion"]
                    if resultado_bomba["curva_validada"]:
                        status_banner(
                            f"Configuración hidráulicamente validada con curva Q-H: {resultado_bomba['config_texto']}",
                            tono="good", icono="✅",
                        )
                    else:
                        status_banner(
                            f"Estimación preliminar: {resultado_bomba['config_texto']}. Falta curva Q-H validada del fabricante.",
                            tono="warn", icono="⚠️",
                        )

                    st.markdown(
                        f"""
                        <div class="pump-card">
                          <div class="pump-title">🏆 {resultado_bomba['modelo']} — {resultado_bomba['config_texto']}</div>
                          <div class="pump-detail">
                            <b>Estado:</b> {validacion}<br>
                            <b>Total unidades:</b> {resultado_bomba['n_total']} —
                            {resultado_bomba['n_paralelo']} paralelo × {resultado_bomba['n_serie']} serie<br>
                            <b>Potencia instalada:</b> {resultado_bomba['hp_total']:.1f} HP<br>
                            <b>Score técnico-económico:</b> {resultado_bomba['score_balanceado']:.4f}
                          </div>
                        </div>
                        """, unsafe_allow_html=True,
                    )

                    a, b, c, d = st.columns(4)
                    with a:
                        kpi_card("N° total bombas", str(resultado_bomba["n_total"]), tono="good")
                    with b:
                        kpi_card("Caudal requerido", f"{caudal_sector:.2f} L/s")
                    with c:
                        kpi_card("TDH requerida", f"{tdh:.2f} m.c.a.")
                    with d:
                        if resultado_bomba["q_operacion_ls"] is not None:
                            kpi_card("Punto operación", f"{resultado_bomba['q_operacion_ls']:.2f} L/s",
                                     sub=f"{resultado_bomba['h_operacion_mca']:.2f} m.c.a.", tono="good")
                        else:
                            kpi_card("Curva Q-H", "Pendiente", sub="No extrapolada", tono="warn")

                    if resultado_bomba.get("costo_total") is not None:
                        costo_bombas = float(resultado_bomba["costo_total"])
                        st.session_state["costo_bombas"] = costo_bombas
                        fuente_precio = "Mercado reciente (mediana SQL)" if resultado_bomba.get("precio_mercado_clp") is not None else "Catálogo maestro SQL"
                        st.session_state["fuente_precio_bomba"] = fuente_precio
                        status_banner(f"Costo de bombeo: ${costo_bombas:,.0f} CLP — {fuente_precio}", icono="💰")
                    else:
                        st.session_state["costo_bombas"] = 0.0

                    st.session_state["modelo_bomba_seleccionado"] = resultado_bomba["modelo"]
                    st.session_state["seleccion_bomba_v2"] = resultado_bomba
                    st.session_state["alternativas_bombeo_v2"] = opt["candidatos"]

                    # Curvas y punto de operación, solo con datos validados.
                    if resultado_bomba["curva_validada"]:
                        curva_b = curvas[curvas["id_bomba"].astype(str) == str(resultado_bomba["id_bomba"])].copy()
                        datos_fig = datos_grafico_operacion(
                            curva_b, resultado_bomba["n_paralelo"], resultado_bomba["n_serie"], h_sistema
                        )
                        if not datos_fig.empty:
                            fig_qh = go.Figure()
                            fig_qh.add_trace(go.Scatter(x=datos_fig["caudal_ls"], y=datos_fig["bomba_mca"], name="Curva bomba/configuración"))
                            fig_qh.add_trace(go.Scatter(x=datos_fig["caudal_ls"], y=datos_fig["sistema_mca"], name="Curva del sistema"))
                            fig_qh.add_trace(go.Scatter(
                                x=[resultado_bomba["q_operacion_ls"]], y=[resultado_bomba["h_operacion_mca"]],
                                mode="markers", marker={"size": 12}, name="Punto de operación"
                            ))
                            fig_qh.update_layout(
                                title="Curva Q-H y punto real de operación", xaxis_title="Caudal (L/s)",
                                yaxis_title="Altura (m.c.a.)", template="plotly_dark", height=430,
                                paper_bgcolor="rgba(0,0,0,0)",
                            )
                            st.plotly_chart(fig_qh, width="stretch")

                    with st.expander("📊 Ver todas las configuraciones evaluadas", expanded=False):
                        df_comp = pd.DataFrame(opt["candidatos"])
                        cols = [c for c in [
                            "modelo", "n_paralelo", "n_serie", "n_total", "curva_validada",
                            "estado_validacion", "q_operacion_ls", "h_operacion_mca",
                            "q_capacidad_preliminar_ls", "h_capacidad_preliminar_mca",
                            "hp_total", "precio_unitario", "costo_total", "n_cotizaciones",
                            "exceso_q_pct", "exceso_h_pct", "eficiencia_operacion_pct", "score_balanceado"
                        ] if c in df_comp.columns]
                        st.dataframe(df_comp[cols], width="stretch", hide_index=True)

                        st.markdown("##### Estado de actualización de mercado")
                        st.dataframe(pd.DataFrame(resumen_busqueda), width="stretch", hide_index=True)

            st.markdown("---")
            section_title("📏 Resumen de Materiales")
            c_m1, c_m2, c_m3 = st.columns(3)
            with c_m1:
                kpi_card("Metros Matriz", f"{st.session_state.get('m_prin', 0):.1f} m")
            with c_m2:
                kpi_card("Metros Lateral", f"{st.session_state.get('m_lat', 0):.1f} m")
            with c_m3:
                kpi_card("N° Emisores", f"{st.session_state.get('tot_emi', 0)}")

        _mostrar_navegacion_pat(2)

    # ========================================================
    # PESTAÑA 4: PRESUPUESTO + AGENTE OPENAI + HITL
    # ========================================================
    with tab_presupuesto:
        st.markdown("## 💰 4. Presupuesto")
        st.caption(
            "Estimación de costos del sistema de riego basada en resultados hidráulicos, "
            "precios de mercado, catálogos SQL y supuestos paramétricos."
        )

        claves_presupuesto = [
            "m_prin",
            "m_lat",
            "diametro_matriz",
            "tot_emi",
            "tecnica_riego",
        ]

        if not all(
            clave in st.session_state
            for clave in claves_presupuesto
        ):
            st.warning(
                "⚠️ Complete el diseño del terreno y el análisis hidráulico antes "
                "de construir el presupuesto."
            )

        else:
            # ============================================================
            # 0. ESTADO Y CÁLCULO BASE
            # ============================================================
            defaults_presupuesto = {
                "presupuesto_pct_accesorios": 15.0,
                "presupuesto_pct_obra_civil": 20.0,
                "presupuesto_pct_instalacion": 40.0,
                "presupuesto_incluir_iva": True,
                "presupuesto_clasificacion_matriz": "Pendiente de validar",
                "presupuesto_clasificacion_laterales": "Pendiente de validar",
                "presupuesto_usuario_hitl": "Usuario PAT",
                "presupuesto_accion_agente": "Analizar configuración",
            }
            for clave, valor in defaults_presupuesto.items():
                st.session_state.setdefault(clave, valor)

            (
                p_matriz,
                p_lateral,
                p_emi,
                p_mat,
                costo_m_usado,
            ) = calcular_presupuesto(
                st.session_state["m_prin"],
                st.session_state["m_lat"],
                st.session_state["diametro_matriz"],
                df_tub,
                st.session_state["tot_emi"],
                st.session_state["tecnica_riego"],
            )

            costo_bombas = float(
                st.session_state.get("costo_bombas", 0.0) or 0.0
            )
            estimacion_williams = st.session_state.get(
                "estimacion_williams_bomba"
            )
            caudal_total_ls = float(
                st.session_state.get("caudal_sector", 0.0) or 0.0
            )

            pct_accesorios = float(
                st.session_state["presupuesto_pct_accesorios"]
            )
            pct_obra_civil = float(
                st.session_state["presupuesto_pct_obra_civil"]
            )
            pct_instalacion = float(
                st.session_state["presupuesto_pct_instalacion"]
            )
            incluir_iva = bool(
                st.session_state["presupuesto_incluir_iva"]
            )

            pulgadas_sugeridas, costo_sugerido = dimensionar_filtro(
                caudal_total_ls * 3.6
            )
            st.session_state.setdefault(
                "costo_filtro_override",
                float(costo_sugerido),
            )
            costo_filtro_manual = float(
                st.session_state.get(
                    "costo_filtro_override",
                    costo_sugerido,
                )
            )

            # En esta versión el cálculo base de obra civil sigue siendo
            # referencial por porcentaje. La clasificación de tramos queda
            # registrada para trazabilidad y futuras cubicaciones.
            obra_civil_cantidades = None
            metodo_obra_civil = "porcentaje"

            detalle = calcular_presupuesto_detallado(
                p_matriz,
                p_lateral,
                p_emi,
                costo_bombas,
                caudal_total_ls,
                pct_accesorios,
                pct_obra_civil,
                pct_instalacion,
                costo_filtro_manual,
                incluir_iva,
                metodo_obra_civil=metodo_obra_civil,
                obra_civil_cantidades=obra_civil_cantidades,
                longitud_matriz_m=st.session_state.get("m_prin"),
                longitud_laterales_m=st.session_state.get("m_lat"),
                cantidad_emisores=st.session_state.get("tot_emi"),
                cantidad_bombas=(
                    (st.session_state.get("seleccion_bomba_v2") or {}).get(
                        "n_total"
                    )
                    or 1
                ),
            )

            st.session_state["presupuesto_total"] = float(detalle["total"])
            st.session_state["presupuesto_obra_civil"] = {
                "metodo_seleccionado": detalle["metodo_obra_civil"],
                "costo_referencial_clp": float(
                    detalle["p_obra_civil_referencial"]
                ),
                "costo_por_cantidades_clp": (
                    None
                    if detalle["p_obra_civil_cantidades"] is None
                    else float(detalle["p_obra_civil_cantidades"])
                ),
                "partidas": detalle["partidas_obra_civil"],
                "fuente_dimensiones_zanja": None,
                "fuente_volumen_relleno": None,
                "fuente_volumen_hormigon": None,
                "origen_longitudes_red": st.session_state.get(
                    "metodo_longitudes_red"
                ),
            }
            st.session_state["componentes_presupuesto"] = {
                "matriz": float(p_matriz),
                "laterales": float(p_lateral),
                "emisores": float(p_emi),
                "bombeo": float(costo_bombas),
                "filtracion": float(detalle["costo_filtro"]),
                "accesorios": float(detalle["p_accesorios"]),
                "obra_civil": float(detalle["p_obra_civil"]),
                "instalacion": float(detalle["p_instalacion"]),
                "iva": float(detalle["iva"]),
            }

            total_presupuesto = float(detalle["total"])
            costo_materiales = (
                float(p_matriz)
                + float(p_lateral)
                + float(p_emi)
                + float(detalle["costo_filtro"])
                + float(detalle["p_accesorios"])
            )
            costo_obra = float(detalle["p_obra_civil"])
            costo_instalacion = float(detalle["p_instalacion"])
            costo_iva = float(detalle["iva"])

            def porcentaje_presupuesto(valor):
                if total_presupuesto <= 0:
                    return 0.0
                return (float(valor) / total_presupuesto) * 100.0

            # ============================================================
            # 1. RESUMEN EJECUTIVO
            # ============================================================
            st.markdown(
                """
                <div class="budget-shell">
                    <div class="budget-heading">
                        <div>
                            <div class="budget-heading-title">💼 1. Resumen ejecutivo del presupuesto</div>
                            <div class="budget-heading-sub">Costos consolidados por componente del proyecto.</div>
                        </div>
                        <div class="budget-badges">
                            <span class="budget-badge good">⚙️ Basado en resultados hidráulicos</span>
                            <span class="budget-badge good">📈 Precios de mercado / SQL</span>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            resumen_cols = st.columns([1, 1, 1, 1, 1, 1.15], gap="small")
            with resumen_cols[0]:
                budget_kpi_card(
                    "Costo equipos",
                    f"${costo_bombas:,.0f}",
                    f"{porcentaje_presupuesto(costo_bombas):.1f}% del total",
                    accent="#29b6f6",
                )
            with resumen_cols[1]:
                budget_kpi_card(
                    "Tuberías y materiales",
                    f"${costo_materiales:,.0f}",
                    f"{porcentaje_presupuesto(costo_materiales):.1f}% del total",
                    accent="#8b5cf6",
                )
            with resumen_cols[2]:
                budget_kpi_card(
                    "Obra civil",
                    f"${costo_obra:,.0f}",
                    f"{porcentaje_presupuesto(costo_obra):.1f}% del total",
                    accent="#f0a020",
                )
            with resumen_cols[3]:
                budget_kpi_card(
                    "Instalación / mano de obra",
                    f"${costo_instalacion:,.0f}",
                    f"{porcentaje_presupuesto(costo_instalacion):.1f}% del total",
                    accent="#3ecf8e",
                )
            with resumen_cols[4]:
                budget_kpi_card(
                    "IVA (19%)" if incluir_iva else "IVA",
                    f"${costo_iva:,.0f}",
                    f"{porcentaje_presupuesto(costo_iva):.1f}% del total",
                    accent="#94a3b8",
                )
            with resumen_cols[5]:
                budget_kpi_card(
                    "Total estimado",
                    f"${total_presupuesto:,.0f}",
                    "100% del presupuesto",
                    accent="#3ecf8e",
                    total=True,
                )

            if estimacion_williams:
                st.warning(
                    "⚠️ El costo de bombeo incorporado al presupuesto proviene de "
                    "una estimación referencial por Williams. No corresponde a una "
                    "cotización ni confirma disponibilidad del equipo."
                )

            # ============================================================
            # 2 + 3. DESGLOSE Y SUPUESTOS
            # ============================================================
            col_desglose, col_ajustes = st.columns([1.75, 1], gap="large")

            with col_desglose:
                section_title("📊 2. Desglose de costos")
                componentes_grafico = {
                    "Tuberías y materiales": costo_materiales,
                    "Equipos / bombeo": costo_bombas,
                    "Obra civil": costo_obra,
                    "Instalación / mano de obra": costo_instalacion,
                    "IVA": costo_iva,
                }
                componentes_grafico = {
                    nombre: valor
                    for nombre, valor in componentes_grafico.items()
                    if valor > 0
                }

                if componentes_grafico:
                    labels_costos = list(componentes_grafico.keys())
                    valores_costos = list(componentes_grafico.values())
                    textos_costos = [
                        f"${valor:,.0f} ({porcentaje_presupuesto(valor):.1f}%)"
                        for valor in valores_costos
                    ]
                    fig_costos = go.Figure(
                        go.Bar(
                            x=valores_costos,
                            y=labels_costos,
                            orientation="h",
                            text=textos_costos,
                            textposition="auto",
                            hovertemplate="%{y}<br>$%{x:,.0f} CLP<extra></extra>",
                        )
                    )
                    fig_costos.update_layout(
                        template="plotly_dark",
                        height=330,
                        margin=dict(l=10, r=20, t=10, b=40),
                        xaxis_title="Costo (CLP)",
                        yaxis_title="",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        showlegend=False,
                    )
                    fig_costos.update_yaxes(autorange="reversed")
                    st.plotly_chart(fig_costos, width="stretch")

                df_detalle = pd.DataFrame(detalle["items"])
                if estimacion_williams and not df_detalle.empty:
                    df_detalle.loc[
                        df_detalle["Ítem"] == "Equipo de bombeo",
                        "Ítem",
                    ] = "Equipo de bombeo (estimación referencial Williams)"

                with st.expander("📋 Ver tabla detallada", expanded=False):
                    df_detalle_vista = df_detalle.copy()
                    if "Subtotal (CLP)" in df_detalle_vista.columns:
                        df_detalle_vista["Subtotal (CLP)"] = (
                            df_detalle_vista["Subtotal (CLP)"]
                            .map(lambda v: f"${float(v):,.0f}")
                        )
                    st.dataframe(
                        df_detalle_vista,
                        width="stretch",
                        hide_index=True,
                    )

            with col_ajustes:
                section_title("⚙️ 3. Supuestos y ajustes")
                st.caption(
                    "Los cambios se recalculan automáticamente en cada ejecución."
                )

                st.number_input(
                    "Válvulas y accesorios (% de tuberías)",
                    min_value=0.0,
                    max_value=100.0,
                    step=1.0,
                    key="presupuesto_pct_accesorios",
                )
                st.number_input(
                    "Obra civil referencial (% de tuberías)",
                    min_value=0.0,
                    max_value=100.0,
                    step=1.0,
                    key="presupuesto_pct_obra_civil",
                )
                st.number_input(
                    "Instalación / mano de obra (%)",
                    min_value=0.0,
                    max_value=100.0,
                    step=1.0,
                    key="presupuesto_pct_instalacion",
                    help=(
                        "Porcentaje aplicado sobre la base calculada por PAT. "
                        "Debe sustituirse por cubicación real cuando exista ingeniería de detalle."
                    ),
                )
                st.checkbox(
                    "Incluir IVA (19%)",
                    key="presupuesto_incluir_iva",
                )
                st.info(
                    "Los porcentajes son supuestos referenciales. El agente puede "
                    "recomendar ajustes, pero solo se aplican después de aprobación humana."
                )

            # ============================================================
            # 4. ASISTENTE TÉCNICO + HITL INTEGRADO
            # ============================================================
            st.markdown("---")
            section_title("🤖 4. Asistente técnico + Human-in-the-Loop")

            st.markdown(
                """
                <div class="budget-badges">
                    <span class="budget-badge good">✅ Basado en resultados hidráulicos</span>
                    <span class="budget-badge warn">⚠️ Revisión humana requerida</span>
                    <span class="budget-badge">🔒 El agente no modifica parámetros automáticamente</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if st.session_state.get("seleccion_bomba_v2") is None:
                st.warning(
                    "Primero completa la selección de equipos en la pestaña 3. "
                    "El agente necesita una alternativa hidráulica para revisar el presupuesto."
                )
            else:
                with st.expander("⚙️ Configuración del análisis", expanded=False):
                    cfg_ag1, cfg_ag2 = st.columns([1, 1.5])
                    with cfg_ag1:
                        usuario_hitl = st.text_input(
                            "Responsable de revisión",
                            key="presupuesto_usuario_hitl",
                        )
                    with cfg_ag2:
                        accion_agente = st.selectbox(
                            "Acción del agente",
                            [
                                "Analizar configuración",
                                "Comparar alternativas",
                                "Explicar recomendación",
                                "Revisar riesgo",
                                "Preparar decisión",
                            ],
                            key="presupuesto_accion_agente",
                        )

                col_ejecutar, col_estado = st.columns([1, 3])
                with col_ejecutar:
                    ejecutar_agente = st.button(
                        "▶️ Ejecutar análisis",
                        type="primary",
                        key="presupuesto_ejecutar_agente",
                        width="stretch",
                    )
                with col_estado:
                    st.caption(
                        "GPT-4o-mini realiza el análisis operativo; el Judge valida "
                        "la recomendación antes de la decisión HITL."
                    )

                if ejecutar_agente:
                    id_proyecto_sql = st.session_state.get("id_proyecto_sql")

                    # La falta de persistencia SQL no debe impedir el análisis del agente.
                    if id_proyecto_sql is None:
                        try:
                            datos_proyecto_agente = {
                                "tecnica_riego": st.session_state.get("tecnica_riego"),
                                "latitud": st.session_state.get("lat_centro"),
                                "longitud": st.session_state.get("lon_centro"),
                                "area_m2": st.session_state.get("plano_area_real_m2"),
                                "longitud_matriz_m": st.session_state.get("m_prin"),
                            }
                            id_proyecto_sql = crear_proyecto_sesion(
                                nombre="Proyecto PAT - sesión Streamlit",
                                datos=datos_proyecto_agente,
                            )
                            st.session_state["id_proyecto_sql"] = id_proyecto_sql
                        except Exception as error_sql:
                            id_proyecto_sql = None
                            st.warning(
                                "El análisis continuará sin persistencia HITL en SQL: "
                                f"{error_sql}"
                            )

                    payload = {
                        "accion_solicitada": accion_agente,
                        "requerimiento": {
                            "caudal_sector_ls": st.session_state.get("caudal_sector"),
                            "tdh_mca": st.session_state.get("tdh"),
                            "potencia_requerida_hp": st.session_state.get("hp_req"),
                        },
                        "seleccion": st.session_state.get("seleccion_bomba_v2"),
                        "alternativas": st.session_state.get(
                            "alternativas_bombeo_v2",
                            [],
                        )[:10],
                        "presupuesto": {
                            "total_clp": total_presupuesto,
                            "componentes": st.session_state.get(
                                "componentes_presupuesto",
                                {},
                            ),
                            "pct_accesorios": pct_accesorios,
                            "pct_obra_civil": pct_obra_civil,
                            "pct_instalacion": pct_instalacion,
                            "incluye_iva": incluir_iva,
                        },
                        "fuentes_disponibles": {
                            "sql_historico": True,
                            "mercado_libre": buscar_productos_ml is not None,
                            "tavily": buscar_precios_tavily is not None,
                            "pedrollo_en733": PEDROLLO_EN733_URL,
                        },
                    }

                    resp = None
                    judge = None
                    try:
                        with st.spinner(
                            "Analizando configuración y presupuesto sin alterar "
                            "el motor determinista..."
                        ):
                            resp = analizar_configuracion(payload)

                        if not isinstance(resp, dict):
                            resp = {
                                "ok": False,
                                "error": (
                                    "El agente no devolvió una respuesta estructurada. "
                                    "Revisa agente_riego.py y la conexión con OpenAI."
                                ),
                            }

                        if resp.get("ok"):
                            resultado_agente = resp.get("resultado")
                            if not isinstance(resultado_agente, dict):
                                resultado_agente = {
                                    "recomendacion": str(
                                        resultado_agente
                                        or "Análisis completado sin detalle estructurado."
                                    )
                                }
                                resp["resultado"] = resultado_agente

                            with st.spinner(
                                "Validando recomendación con LLM as a Judge..."
                            ):
                                judge = evaluar_con_judge(
                                    payload,
                                    resultado_agente,
                                )
                            if judge is not None and not isinstance(judge, dict):
                                judge = {
                                    "ok": False,
                                    "error": "El Judge devolvió un formato no reconocido.",
                                }

                    except Exception as error_agente:
                        resp = {
                            "ok": False,
                            "error": str(error_agente),
                        }
                        judge = None

                    st.session_state["respuesta_agente"] = resp
                    st.session_state["respuesta_judge"] = judge

                    # Persistencia de la ejecución solo si SQL está disponible.
                    if resp.get("ok") and id_proyecto_sql is not None:
                        resultado_agente = resp.get("resultado") or {}
                        try:
                            id_ejec = guardar_ejecucion_agente(
                                id_proyecto_sql,
                                "Asistente Técnico de Riego",
                                resp.get("modelo", "desconocido"),
                                "COMPLETADA",
                                payload,
                                resultado_agente,
                                requiere_hitl=bool(
                                    resultado_agente.get(
                                        "requiere_hitl",
                                        True,
                                    )
                                ),
                            )
                            st.session_state[
                                "id_ejecucion_agente"
                            ] = id_ejec

                            st.session_state[
                                "id_aprobacion_hitl"
                            ] = crear_aprobacion_hitl(
                                id_proyecto_sql,
                                id_ejec,
                                accion_agente,
                                accion_solicitada=accion_agente,
                                resultado_previo=resultado_agente,
                            )
                        except Exception as error_persistencia:
                            st.warning(
                                "El análisis se completó, pero no se pudo registrar "
                                f"la ejecución HITL en SQL: {error_persistencia}"
                            )

                    if (
                        resp.get("ok")
                        and judge
                        and judge.get("ok")
                        and id_proyecto_sql is not None
                    ):
                        try:
                            id_ejec_judge = guardar_ejecucion_agente(
                                id_proyecto_sql,
                                "LLM as a Judge",
                                judge.get("modelo", "desconocido"),
                                "COMPLETADA",
                                {
                                    "datos_deterministas": payload,
                                    "respuesta_evaluada": resp.get("resultado") or {},
                                },
                                judge.get("resultado") or {},
                                requiere_hitl=bool(
                                    (judge.get("resultado") or {}).get(
                                        "requiere_revision",
                                        True,
                                    )
                                ),
                            )
                            st.session_state[
                                "id_ejecucion_judge"
                            ] = id_ejec_judge
                        except Exception as error_judge_sql:
                            st.warning(
                                "La validación Judge fue obtenida, pero no pudo "
                                f"persistirse en SQL: {error_judge_sql}"
                            )

                resp = st.session_state.get("respuesta_agente")
                judge = st.session_state.get("respuesta_judge")

                if resp:
                    if not isinstance(resp, dict) or not resp.get("ok"):
                        error_agente = (
                            resp.get("error")
                            if isinstance(resp, dict)
                            else "Respuesta no válida del agente."
                        )
                        st.error(f"Agente no disponible: {error_agente}")
                    else:
                        resultado = resp.get("resultado") or {}
                        if not isinstance(resultado, dict):
                            resultado = {
                                "recomendacion": str(resultado)
                            }

                        recomendacion = (
                            resultado.get("recomendacion")
                            or resultado.get("resumen")
                            or "Análisis completado."
                        )

                        observaciones = []
                        for clave_obs in (
                            "riesgos",
                            "observaciones",
                            "advertencias",
                            "problemas_detectados",
                        ):
                            observaciones.extend(
                                _lista_texto_segura(
                                    resultado.get(clave_obs)
                                )
                            )

                        if judge and isinstance(judge, dict) and judge.get("ok"):
                            evaluacion_judge = judge.get("resultado") or {}
                            observaciones.extend(
                                _lista_texto_segura(
                                    evaluacion_judge.get(
                                        "problemas_detectados"
                                    )
                                )
                            )

                        col_rec, col_riesgos = st.columns([1.45, 1], gap="large")
                        with col_rec:
                            st.success(f"💡 {recomendacion}")
                        with col_riesgos:
                            if observaciones:
                                st.warning(
                                    "⚠️ Observaciones y riesgos\n\n"
                                    + "\n".join(
                                        f"- {item}"
                                        for item in observaciones[:8]
                                    )
                                )
                            else:
                                st.info(
                                    "No se reportaron observaciones adicionales "
                                    "en la respuesta estructurada."
                                )

                        if judge and isinstance(judge, dict):
                            if judge.get("ok"):
                                evaluacion = judge.get("resultado") or {}
                                score = float(
                                    evaluacion.get("score", 0) or 0
                                )
                                j1, j2, j3, j4 = st.columns(4)
                                j1.metric("Judge", f"{score:.0f}/100")
                                j2.metric(
                                    "Consistencia",
                                    f"{float(evaluacion.get('consistencia_datos', 0) or 0):.0f}/100",
                                )
                                j3.metric(
                                    "Seguridad técnica",
                                    f"{float(evaluacion.get('seguridad_tecnica', 0) or 0):.0f}/100",
                                )
                                j4.metric(
                                    "Trazabilidad",
                                    f"{float(evaluacion.get('trazabilidad', 0) or 0):.0f}/100",
                                )
                            else:
                                st.warning(
                                    "El Judge no pudo ejecutarse: "
                                    + str(judge.get("error"))
                                )

                        ajustes_agente = _extraer_ajustes_presupuesto_agente(
                            resultado
                        )
                        if ajustes_agente:
                            etiquetas_ajustes = {
                                "presupuesto_pct_accesorios": "Accesorios (%)",
                                "presupuesto_pct_obra_civil": "Obra civil (%)",
                                "presupuesto_pct_instalacion": "Instalación (%)",
                                "costo_filtro_override": "Costo filtrado (CLP)",
                            }
                            tabla_ajustes = []
                            for clave_ajuste, nuevo_valor in ajustes_agente.items():
                                tabla_ajustes.append(
                                    {
                                        "Parámetro": etiquetas_ajustes[
                                            clave_ajuste
                                        ],
                                        "Actual": st.session_state.get(
                                            clave_ajuste
                                        ),
                                        "Propuesto": nuevo_valor,
                                    }
                                )
                            st.markdown("##### Ajustes propuestos por el agente")
                            st.dataframe(
                                pd.DataFrame(tabla_ajustes),
                                width="stretch",
                                hide_index=True,
                            )
                            st.caption(
                                "Estos valores no se aplican automáticamente. "
                                "Solo se incorporan al presupuesto al aceptar la sugerencia."
                            )

                        comentario_hitl = st.text_area(
                            "Comentario de revisión humana",
                            key="presupuesto_comentario_hitl",
                            placeholder=(
                                "Justificación técnica de la aprobación, rechazo "
                                "o solicitud de revisión."
                            ),
                        )
                        btn_aprobar, btn_rechazar, btn_revision = st.columns(3)
                        id_ap = st.session_state.get("id_aprobacion_hitl")
                        usuario_hitl = st.session_state.get(
                            "presupuesto_usuario_hitl",
                            "Usuario PAT",
                        )

                        with btn_aprobar:
                            if st.button(
                                "✅ Aceptar sugerencia",
                                key="presupuesto_hitl_aprobar",
                                width="stretch",
                            ):
                                if id_ap:
                                    try:
                                        resolver_aprobacion_hitl(
                                            id_ap,
                                            "APROBADO",
                                            usuario_hitl,
                                            comentario_hitl,
                                            resultado,
                                        )
                                    except Exception as error_hitl:
                                        st.warning(
                                            "No se pudo registrar la aprobación en SQL: "
                                            f"{error_hitl}"
                                        )

                                for clave_ajuste, valor_ajuste in ajustes_agente.items():
                                    st.session_state[clave_ajuste] = valor_ajuste

                                if ajustes_agente:
                                    st.success(
                                        "Recomendación aprobada y ajustes "
                                        "presupuestarios aplicados."
                                    )
                                    st.rerun()
                                else:
                                    st.success(
                                        "Recomendación aprobada. No había ajustes "
                                        "numéricos estructurados que aplicar."
                                    )

                        with btn_rechazar:
                            if st.button(
                                "❌ Rechazar",
                                key="presupuesto_hitl_rechazar",
                                width="stretch",
                            ):
                                if id_ap:
                                    try:
                                        resolver_aprobacion_hitl(
                                            id_ap,
                                            "RECHAZADO",
                                            usuario_hitl,
                                            comentario_hitl,
                                            resultado,
                                        )
                                    except Exception as error_hitl:
                                        st.warning(
                                            "No se pudo registrar el rechazo en SQL: "
                                            f"{error_hitl}"
                                        )
                                st.warning(
                                    "Recomendación rechazada. El presupuesto no fue modificado."
                                )

                        with btn_revision:
                            if st.button(
                                "🧑‍🔧 Enviar a revisión",
                                key="presupuesto_hitl_revision",
                                width="stretch",
                            ):
                                if id_ap:
                                    try:
                                        resolver_aprobacion_hitl(
                                            id_ap,
                                            "REVISION",
                                            usuario_hitl,
                                            comentario_hitl,
                                            resultado,
                                        )
                                    except Exception as error_hitl:
                                        st.warning(
                                            "No se pudo registrar la revisión en SQL: "
                                            f"{error_hitl}"
                                        )
                                st.info(
                                    "La recomendación quedó marcada para revisión humana."
                                )

                        with st.expander(
                            "🔍 Ver respuesta técnica completa",
                            expanded=False,
                        ):
                            st.json(resultado)
                            if judge and isinstance(judge, dict):
                                st.markdown("##### Resultado del Judge")
                                st.json(judge)

            # ============================================================
            # FUENTES DE INFORMACIÓN
            # ============================================================
            st.markdown("##### 🗂️ Fuentes de información de precios y fichas técnicas")
            fuente_cols = st.columns(4)
            with fuente_cols[0]:
                st.markdown(
                    """
                    <div class="source-card">
                        <div class="source-title">🗄️ SQL histórico</div>
                        <div class="source-sub">Catálogo maestro, precios y cotizaciones persistidas.</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with fuente_cols[1]:
                st.markdown(
                    """
                    <div class="source-card">
                        <div class="source-title">🛒 Mercado Libre</div>
                        <div class="source-sub">Referencias comerciales vigentes cuando el token está disponible.</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with fuente_cols[2]:
                st.markdown(
                    """
                    <div class="source-card">
                        <div class="source-title">🌐 Tavily</div>
                        <div class="source-sub">Búsqueda web para candidatos, precios y fuentes públicas.</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with fuente_cols[3]:
                st.markdown(
                    """
                    <div class="source-card">
                        <div class="source-title">📘 Fichas técnicas Q-H</div>
                        <div class="source-sub">Fuente fabricante para validar curvas y punto de operación.</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.link_button(
                    "Abrir Pedrollo EN 733 ↗",
                    PEDROLLO_EN733_URL,
                    width="stretch",
                )

            # ============================================================
            # COTIZACIÓN EN VIVO — AVANZADA / COLAPSADA
            # ============================================================
            with st.expander(
                "🔎 Cotización en vivo y actualización de filtrado",
                expanded=False,
            ):
                st.caption(
                    "Herramienta auxiliar para sustituir precios genéricos por "
                    "referencias actuales. No altera el catálogo maestro de bombas."
                )

                if (
                    buscar_productos_ml is None
                    and buscar_precios_tavily is None
                ):
                    st.info(
                        "No se encontraron los módulos de Mercado Libre/Tavily."
                    )
                else:
                    termino_busqueda = st.text_input(
                        "Buscar insumo",
                        value="filtro malla riego",
                        key="presupuesto_buscar_insumo",
                    )

                    if st.button(
                        "🔍 Buscar precios",
                        key="presupuesto_buscar_precios_vivo",
                    ):
                        resultados_totales = []
                        errores = []

                        with st.spinner(
                            "Consultando Mercado Libre y Tavily..."
                        ):
                            if buscar_productos_ml is not None:
                                try:
                                    res_ml, err_ml = buscar_productos_ml(
                                        termino_busqueda
                                    )
                                    resultados_totales.extend(
                                        res_ml or []
                                    )
                                    if err_ml:
                                        errores.append(
                                            f"Mercado Libre: {err_ml}"
                                        )
                                except Exception as error_ml:
                                    errores.append(
                                        f"Mercado Libre: {error_ml}"
                                    )

                            if buscar_precios_tavily is not None:
                                try:
                                    res_tv, err_tv = buscar_precios_tavily(
                                        termino_busqueda
                                    )
                                    resultados_totales.extend(
                                        res_tv or []
                                    )
                                    if err_tv:
                                        errores.append(
                                            f"Tavily: {err_tv}"
                                        )
                                except Exception as error_tv:
                                    errores.append(
                                        f"Tavily: {error_tv}"
                                    )

                        st.session_state[
                            "busqueda_viva_resultados"
                        ] = resultados_totales
                        st.session_state[
                            "busqueda_viva_errores"
                        ] = errores

                    for error_web in st.session_state.get(
                        "busqueda_viva_errores",
                        [],
                    ):
                        st.warning(error_web)

                    resultados_vivos = st.session_state.get(
                        "busqueda_viva_resultados"
                    )
                    if resultados_vivos:
                        df_vivo = pd.DataFrame(resultados_vivos)

                        if "Precio_CLP" in df_vivo.columns:
                            df_vivo["Precio_CLP"] = pd.to_numeric(
                                df_vivo["Precio_CLP"],
                                errors="coerce",
                            )
                            df_vivo = df_vivo.sort_values(
                                "Precio_CLP",
                                na_position="last",
                            ).reset_index(drop=True)

                        config_columnas = {}
                        if "URL" in df_vivo.columns:
                            config_columnas["URL"] = (
                                st.column_config.LinkColumn(
                                    "Fuente",
                                    display_text="Abrir ↗",
                                )
                            )

                        st.dataframe(
                            df_vivo,
                            width="stretch",
                            hide_index=True,
                            column_config=config_columnas,
                        )

                        if (
                            "Precio_CLP" in df_vivo.columns
                            and df_vivo["Precio_CLP"].notna().any()
                        ):
                            mas_barato = df_vivo.dropna(
                                subset=["Precio_CLP"]
                            ).iloc[0]
                            fuente_barata = mas_barato.get(
                                "Fuente",
                                "web",
                            )
                            if st.button(
                                (
                                    "✅ Usar menor precio detectado "
                                    f"(${mas_barato['Precio_CLP']:,.0f}, "
                                    f"{fuente_barata}) como costo de filtrado"
                                ),
                                key="presupuesto_usar_precio_filtrado",
                            ):
                                st.session_state[
                                    "costo_filtro_override"
                                ] = float(
                                    mas_barato["Precio_CLP"]
                                )
                                st.rerun()

                st.number_input(
                    (
                        f"Costo de filtrado ({pulgadas_sugeridas}\" sugerido "
                        "por caudal)"
                    ),
                    min_value=0.0,
                    step=50000.0,
                    key="costo_filtro_override",
                    help=(
                        "Editable. El valor seleccionado pasa al presupuesto "
                        "en el siguiente rerun."
                    ),
                )

            # ============================================================
            # OBRA CIVIL — TRAZABILIDAD SIN SOBRECARGAR LA VISTA
            # ============================================================
            with st.expander(
                "🚧 Obra civil y clasificación de tuberías",
                expanded=False,
            ):
                st.caption(
                    "Clasifica los tramos para documentar qué parte de la red "
                    "podría requerir excavación. El costo base continúa siendo "
                    "referencial hasta contar con cubicaciones verificadas."
                )
                longitudes_pat = {
                    "Matriz": float(st.session_state["m_prin"]),
                    "Laterales": float(st.session_state["m_lat"]),
                }
                modos_tramo = [
                    "Pendiente de validar",
                    "Enterrado",
                    "Superficial",
                ]
                c_clasif_matriz, c_clasif_laterales = st.columns(2)
                with c_clasif_matriz:
                    st.metric(
                        "Longitud matriz",
                        f"{longitudes_pat['Matriz']:.2f} m",
                    )
                    clasificacion_matriz = st.selectbox(
                        "Condición matriz",
                        modos_tramo,
                        key="presupuesto_clasificacion_matriz",
                    )
                with c_clasif_laterales:
                    st.metric(
                        "Longitud laterales",
                        f"{longitudes_pat['Laterales']:.2f} m",
                    )
                    clasificacion_laterales = st.selectbox(
                        "Condición laterales",
                        modos_tramo,
                        key="presupuesto_clasificacion_laterales",
                    )

                try:
                    clasificacion_tramos = (
                        clasificar_longitudes_tuberia_obra_civil(
                            longitudes_pat["Matriz"],
                            longitudes_pat["Laterales"],
                            clasificacion_matriz,
                            clasificacion_laterales,
                        )
                    )
                    st.session_state[
                        "clasificacion_tramos_obra_civil"
                    ] = clasificacion_tramos

                    oc1, oc2, oc3 = st.columns(3)
                    oc1.metric(
                        "Longitud enterrada",
                        (
                            f"{clasificacion_tramos['longitud_enterrada_confirmada_m']:.2f} m"
                        ),
                    )
                    oc2.metric(
                        "Longitud superficial",
                        (
                            f"{clasificacion_tramos['longitud_superficial_confirmada_m']:.2f} m"
                        ),
                    )
                    oc3.metric(
                        "Pendiente validar",
                        (
                            f"{clasificacion_tramos['longitud_pendiente_validacion_m']:.2f} m"
                        ),
                    )
                except ValueError as error_obra:
                    st.error(str(error_obra))

                st.metric(
                    f"Costo referencial de obra civil ({pct_obra_civil:.0f}%)",
                    f"${costo_obra:,.0f} CLP",
                )

            # ============================================================
            # EXPORTACIÓN
            # ============================================================
            st.markdown("---")
            exportar_col, nota_col = st.columns([1, 3])
            with exportar_col:
                csv_presupuesto = pd.DataFrame(
                    detalle["items"]
                ).to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    "📥 Exportar presupuesto CSV",
                    data=csv_presupuesto,
                    file_name="presupuesto_riego_PAT.csv",
                    mime="text/csv",
                    width="stretch",
                )
            with nota_col:
                st.caption(
                    "La exportación contiene el detalle numérico vigente. "
                    "Los resultados del agente y la decisión HITL se mantienen "
                    "trazables en la sesión/SQL cuando la persistencia está disponible."
                )

            # ============================================================
            # GESTIÓN DE PROYECTO — COLAPSADA
            # ============================================================
            with st.expander(
                "💾 Gestión del proyecto: cargar / guardar",
                expanded=False,
            ):
                st.markdown("---")
                section_title("📂 Cargar proyecto guardado")
                st.caption(
                    "Selecciona un proyecto de dbo.Proyectos para continuar desde "
                    "sus datos y cálculos guardados."
                )
                try:
                    proyectos_guardados = listar_proyectos_disenio()
                except Exception as error:
                    proyectos_guardados = pd.DataFrame()
                    st.error(f"No se pudieron consultar los proyectos guardados: {error}")
                else:
                    if proyectos_guardados.empty:
                        st.info("No hay proyectos guardados disponibles.")
                    else:
                        filas_proyectos = proyectos_guardados.to_dict(
                            orient="records"
                        )
                        opciones_proyecto = {
                            int(fila["id_proyecto"]): fila
                            for fila in filas_proyectos
                        }

                        def etiqueta_proyecto(id_proyecto):
                            fila = opciones_proyecto[id_proyecto]
                            area = fila.get("superficie_ha")
                            detalle_area = (
                                f" · {float(area):.2f} ha"
                                if pd.notna(area)
                                else ""
                            )
                            return (
                                f'{id_proyecto} — {fila["nombre"]}'
                                f'{detalle_area} · {fila.get("estado") or "sin estado"}'
                            )

                        st.selectbox(
                            "Proyecto",
                            options=list(opciones_proyecto),
                            format_func=etiqueta_proyecto,
                            key="proyecto_guardado_seleccionado",
                        )
                        st.button(
                            "Cargar proyecto guardado",
                            key="cargar_proyecto_guardado",
                            on_click=_cargar_proyecto_guardado_callback,
                        )

                if st.session_state.get("proyecto_carga_error"):
                    st.error(
                        "No se pudo cargar el proyecto: "
                        f"{st.session_state['proyecto_carga_error']}"
                    )
                carga_exitosa = st.session_state.get("proyecto_carga_exito")
                if carga_exitosa:
                    nombre_cargado, advertencias_carga = carga_exitosa
                    st.success(
                        f"Proyecto «{nombre_cargado}» cargado. "
                        "Los cambios posteriores se guardarán en ese mismo registro."
                    )
                    for advertencia in advertencias_carga:
                        st.warning(advertencia)

                st.markdown("---")
                section_title("💾 Guardar proyecto")
                st.caption(
                    "Guarda en SQL Server el diseño, los cálculos y el presupuesto "
                    "disponibles en esta sesión. Si cargaste un proyecto, este botón "
                    "actualiza ese registro."
                )
                st.text_input(
                    "Nombre del proyecto",
                    key="nombre_proyecto_guardar",
                    max_chars=150,
                    placeholder="Ej. Riego parcela norte",
                )

                if st.button(
                    "💾 Guardar proyecto",
                    type="primary",
                    key="guardar_proyecto_presupuesto",
                ):
                    nombre_proyecto = st.session_state[
                        "nombre_proyecto_guardar"
                    ].strip()

                    if not nombre_proyecto:
                        st.warning("Escribe un nombre antes de guardar.")
                    else:
                        claves_snapshot = (
                            "lat_centro",
                            "lon_centro",
                            "plano_coordenadas_gps",
                            "plano_area_real_m2",
                            "comuna_predio",
                            "comunas_predio",
                            "region_predio",
                            "regiones_predio",
                            "pais_predio",
                            "plano_superficie_ha",
                            "plano_perimetro_m",
                            "plano_largo_matriz_m",
                            "metodo_longitudes_red",
                            "trazado_real_disponible",
                            "parametros_emisor_verificados",
                            "codigo_ficha_emisor",
                            "ficha_emisor_seleccionada",
                            "presion_operacion_emisor_mca",
                            "fuente_parametros_emisor",
                            "alt_def",
                            "fuente_altitud",
                            "temp_auto",
                            "hr_auto",
                            "viento_auto",
                            "eto_auto",
                            "alt_auto",
                            "temp_manual",
                            "alt_manual",
                            "hr_manual",
                            "rn_manual",
                            "viento_manual",
                            "kc_manual",
                            "eto_final",
                            "etc",
                            "necesidad_total",
                            "fuente_clima",
                            "datos_agronomicos_listos",
                            "velocidad_infiltracion_mm_h",
                            "num_sectores",
                            "q_tot",
                            "m_prin",
                            "m_lat",
                            "m_tot",
                            "tot_emi",
                            "pp_horaria",
                            "tiempo_riego",
                            "riego_configurado",
                            "caudal_sector",
                            "tdh",
                            "hp_req",
                            "diametro_matriz",
                            "coef_hazen",
                            "altura_estatica",
                            "perdida_acc",
                            "perdida_matriz_ref",
                            "perdida_acc_ref",
                            "presion_emisor",
                            "eficiencia_bomba_diseno",
                            "dist_hileras_riego",
                            "dist_goteros_riego",
                            "caudal_gotero_riego",
                            "horas_jornada_riego",
                            "presupuesto_pct_accesorios",
                            "presupuesto_pct_obra_civil",
                            "presupuesto_pct_instalacion",
                            "presupuesto_incluir_iva",
                            "presupuesto_clasificacion_matriz",
                            "presupuesto_clasificacion_laterales",
                            "seleccion_bomba_v2",
                            "costo_bombas",
                            "fuente_precio_bomba",
                            "estimacion_williams_bomba",
                            "componentes_presupuesto",
                            "presupuesto_obra_civil",
                            "clasificacion_tramos_obra_civil",
                            "presupuesto_total",
                        )
                        datos_proyecto = {
                            clave: st.session_state[clave]
                            for clave in claves_snapshot
                            if clave in st.session_state
                            and st.session_state[clave] is not None
                        }
                        tecnica_snapshot = st.session_state.get("tecnica_riego")
                        if tecnica_snapshot:
                            for prefijo in (
                                "radio_emisor",
                                "caudal_emisor_lh",
                                "presion_emisor",
                                "factor_traslape",
                            ):
                                clave_emisor = f"{prefijo}_{tecnica_snapshot}"
                                if clave_emisor in st.session_state:
                                    datos_proyecto[clave_emisor] = (
                                        st.session_state[clave_emisor]
                                    )
                        datos_proyecto.update(
                            {
                                "cultivo": cultivo,
                                "temporada": temporada,
                                "tipo_suelo": tipo_suelo,
                                "modo_clima": modo_clima,
                                "latitud": st.session_state.get("lat_centro"),
                                "longitud": st.session_state.get("lon_centro"),
                                "area_m2": st.session_state.get(
                                    "plano_area_real_m2"
                                ),
                                "superficie_ha": st.session_state.get(
                                    "plano_superficie_ha"
                                ),
                                "perimetro_m": st.session_state.get(
                                    "plano_perimetro_m"
                                ),
                                "longitud_matriz_m": st.session_state.get(
                                    "plano_largo_matriz_m",
                                    st.session_state.get("m_prin"),
                                ),
                                "tecnica_riego": st.session_state.get(
                                    "tecnica_riego"
                                ),
                                "presupuesto_detallado": {
                                    "items": detalle["items"],
                                    "metodo_obra_civil": detalle[
                                        "metodo_obra_civil"
                                    ],
                                    "comparacion_obra_civil": {
                                        "referencial_5pct_clp": float(
                                            detalle["p_obra_civil_referencial"]
                                        ),
                                        "cantidades_clp": (
                                            None
                                            if detalle["p_obra_civil_cantidades"]
                                            is None
                                            else float(
                                                detalle[
                                                    "p_obra_civil_cantidades"
                                                ]
                                            )
                                        ),
                                    },
                                    "partidas_obra_civil": detalle[
                                        "partidas_obra_civil"
                                    ],
                                    "clasificacion_tramos_tuberia": (
                                        st.session_state.get(
                                            "clasificacion_tramos_obra_civil"
                                        )
                                    ),
                                    "origen_longitudes_red": st.session_state.get(
                                        "metodo_longitudes_red"
                                    ),
                                    "trazado_real_disponible": bool(
                                        st.session_state.get(
                                            "trazado_real_disponible",
                                            False,
                                        )
                                    ),
                                    "fuente_dimensiones_zanja": (
                                        None
                                        if obra_civil_cantidades is None
                                        else obra_civil_cantidades[
                                            "fuente_dimensiones_zanja"
                                        ]
                                    ),
                                    "fuente_volumen_relleno": (
                                        None
                                        if obra_civil_cantidades is None
                                        else obra_civil_cantidades[
                                            "fuente_volumen_relleno"
                                        ]
                                    ),
                                    "fuente_volumen_hormigon": (
                                        None
                                        if obra_civil_cantidades is None
                                        else obra_civil_cantidades[
                                            "fuente_volumen_hormigon"
                                        ]
                                    ),
                                    "incluye_iva": bool(incluir_iva),
                                    "costo_filtrado_clp": float(
                                        detalle["costo_filtro"]
                                    ),
                                    "costo_accesorios_clp": float(
                                        detalle["p_accesorios"]
                                    ),
                                    "costo_obra_civil_clp": float(
                                        detalle["p_obra_civil"]
                                    ),
                                    "base_instalacion_clp": float(
                                        detalle["base_instalacion"]
                                    ),
                                    "costo_instalacion_clp": float(
                                        detalle["p_instalacion"]
                                    ),
                                    "iva_clp": float(detalle["iva"]),
                                    "total_clp": float(detalle["total"]),
                                },
                            }
                        )
                        if not datos_proyecto.get("plano_area_real_m2") and not datos_proyecto.get("riego_configurado"):
                            st.warning(
                                "Completa el diseño del terreno y la configuración de riego "
                                "antes de guardar."
                            )
                        else:
                            try:
                                # Proyecto + presupuesto + partidas:
                                # una sola transacción SQL.
                                (
                                    id_proyecto,
                                    id_presupuesto,
                                ) = guardar_proyecto_con_presupuesto(
                                    nombre=nombre_proyecto,
                                    datos=datos_proyecto,
                                    detalle=detalle,
                                    id_proyecto=st.session_state.get(
                                        "id_proyecto_sql"
                                    ),
                                    incluir_iva=bool(incluir_iva),
                                    fuente_precio_bomba=st.session_state.get(
                                        "fuente_precio_bomba"
                                    ),
                                )

                            except Exception as error:
                                st.error(
                                    "No se pudo guardar el proyecto y su presupuesto: "
                                    f"{error}"
                                )

                            else:
                                st.session_state[
                                    "id_proyecto_sql"
                                ] = id_proyecto
                                st.session_state[
                                    "id_presupuesto_sql"
                                ] = id_presupuesto

                                st.success(
                                    f"✅ Proyecto guardado en SQL Server. "
                                    f"Proyecto ID: {id_proyecto} · "
                                    f"Presupuesto ID: {id_presupuesto}"
                                )
                                


        _mostrar_navegacion_pat(3)

    # ========================================================
    # PESTAÑA 5: BASES DE DATOS
    # ========================================================
    with tab_datos:
        section_title("📊 SQL Server — catálogos, curvas e históricos")

        db_tabs = st.tabs([
            "Tuberías", "Bombas", "Emisores", "Accesorios", "Materiales",
            "Mercado bombas", "Curvas Q-H", "Candidatos web",
            "Precios de obras civiles",
        ])
        with db_tabs[0]: st.dataframe(df_tub, width="stretch")
        with db_tabs[1]: st.dataframe(df_bomb, width="stretch")
        with db_tabs[2]: st.dataframe(df_emi, width="stretch")
        with db_tabs[3]: st.dataframe(df_acc, width="stretch")
        with db_tabs[4]: st.dataframe(df_mat, width="stretch")
        with db_tabs[5]:
            df_mercado_db = obtener_precios_mercado(horas=720)
            if df_mercado_db.empty:
                st.info("No hay cotizaciones de mercado almacenadas todavía.")
            else:
                st.dataframe(df_mercado_db, width="stretch", hide_index=True)
                hist = cargar_historial_precios_bomba(dias=365)
                analisis_hist = analizar_historial_precios(hist)
                if not analisis_hist.empty:
                    st.markdown("##### Variación y volatilidad")
                    st.dataframe(analisis_hist, width="stretch", hide_index=True)
                if not hist.empty:
                    hist_plot = hist.copy()
                    hist_plot["fecha_consulta"] = pd.to_datetime(hist_plot["fecha_consulta"], errors="coerce")
                    hist_plot["precio_clp"] = pd.to_numeric(hist_plot["precio_clp"], errors="coerce")
                    hist_plot = hist_plot.dropna(subset=["fecha_consulta", "precio_clp"])
                    if not hist_plot.empty:
                        fig_hist_p = go.Figure()
                        for modelo_hist, g in hist_plot.groupby("modelo"):
                            fig_hist_p.add_trace(go.Scatter(
                                x=g["fecha_consulta"], y=g["precio_clp"], mode="markers+lines",
                                name=str(modelo_hist)
                            ))
                        fig_hist_p.update_layout(
                            title="Historial de precios por modelo", xaxis_title="Fecha",
                            yaxis_title="Precio CLP", template="plotly_dark", height=420
                        )
                        st.plotly_chart(fig_hist_p, width="stretch")
        with db_tabs[6]:
            curvas_db = cargar_curvas_bombas(solo_activas=False)
            if curvas_db.empty:
                st.warning("No hay curvas Q-H cargadas. La selección se mantendrá como estimación preliminar.")
            else:
                st.dataframe(curvas_db, width="stretch", hide_index=True)
        with db_tabs[7]:
            try:
                cand_db = cargar_candidatos_web()
            except Exception as e:
                cand_db = pd.DataFrame()
                st.warning(f"Tabla de candidatos no disponible: {e}")
            if cand_db.empty:
                st.info("No hay candidatos externos registrados.")
            else:
                st.dataframe(cand_db, width="stretch", hide_index=True)
                st.markdown("##### Validación HITL de candidato web")
                opciones = {
                    f"#{int(r.id_candidato)} | {str(r.modelo_detectado or r.producto)[:80]} | {r.estado}": int(r.id_candidato)
                    for r in cand_db.itertuples()
                }
                etiqueta = st.selectbox("Candidato", list(opciones.keys()))
                id_cand = opciones[etiqueta]
                usuario_candidato = st.text_input("Validador técnico", value="Usuario PAT", key="validador_candidato")
                ca, cr, cp = st.columns(3)
                with ca:
                    if st.button("✅ Aprobar candidato"):
                        resolver_candidato_web(id_cand, "APROBADO")
                        st.success("Candidato aprobado. Aún no se incorpora al catálogo hasta usar 'Incorporar'.")
                with cr:
                    if st.button("❌ Rechazar candidato"):
                        resolver_candidato_web(id_cand, "RECHAZADO")
                        st.warning("Candidato rechazado.")
                with cp:
                    if st.button("📥 Incorporar aprobado a Bombas"):
                        try:
                            nuevo_id = promover_candidato_a_bomba(id_cand, usuario_candidato)
                            st.success(f"Candidato incorporado al catálogo maestro con id_bomba={nuevo_id}.")
                            cargar_bases_de_datos.clear()
                        except Exception as e:
                            st.error(f"No se pudo incorporar: {e}")
        with db_tabs[8]:
            st.markdown("### Catálogo local de precios de obras civiles")
            st.caption(
                "Administra aquí partidas, unidades, precios, fuente, fecha, "
                "condiciones y alcance de mano de obra. Solo se aceptan como "
                "validados los registros completos y consistentes."
            )
            ruta_catalogo_civil = Path(__file__).with_name(
                "catalogo_precios_obra_civil.csv"
            )
            try:
                catalogo_civil_df = pd.read_csv(
                    ruta_catalogo_civil,
                    dtype=str,
                    keep_default_na=False,
                )
            except (OSError, pd.errors.ParserError) as exc:
                st.error(f"No se pudo abrir el catálogo local: {exc}")
            else:
                with st.form("form_catalogo_precios_obra_civil"):
                    catalogo_civil_editado = st.data_editor(
                        catalogo_civil_df,
                        num_rows="dynamic",
                        width="stretch",
                        key="editor_catalogo_precios_obra_civil",
                    )
                    guardar_catalogo_civil = st.form_submit_button(
                        "Guardar catálogo"
                    )
                if guardar_catalogo_civil:
                    try:
                        guardar_catalogo_precios_obra_civil(
                            catalogo_civil_editado,
                            ruta_catalogo_civil,
                        )
                    except (OSError, ValueError) as exc:
                        st.error(f"No se guardó el catálogo: {exc}")
                    else:
                        st.success("Catálogo de obras civiles guardado.")
                        st.rerun()

        _mostrar_navegacion_pat(4)

    # ========================================================
    # PESTAÑA 6: MONTE CARLO
    # ========================================================
    with tab_montecarlo:
        section_title("🎲 Simulación Monte Carlo — Riesgo de costo")
        if st.session_state.get("estimacion_williams_bomba"):
            st.warning(
                "Esta simulación incluye como costo base una estimación "
                "referencial de bombeo por Williams; sus resultados no representan "
                "una cotización ni el precio confirmado de una bomba disponible."
            )
        st.caption(
            "Las distribuciones se muestran explícitamente. El precio de bomba usa bootstrap del histórico SQL "
            "cuando existen al menos 3 observaciones válidas."
        )
        componentes = st.session_state.get("componentes_presupuesto")
        if not componentes:
            st.warning("Primero genera el presupuesto completo en la pestaña 4.")
        else:
            c1, c2, c3 = st.columns(3)
            with c1:
                n_mc = st.selectbox("Iteraciones", [1000, 5000, 10000], index=1)
            with c2:
                seed_mc = st.number_input("Seed", min_value=0, value=42, step=1)
            with c3:
                objetivo_mc = st.number_input(
                    "Presupuesto objetivo (CLP)", min_value=0.0,
                    value=float(st.session_state.get("presupuesto_total", 0.0)) * 1.10,
                    step=100000.0,
                )

            with st.expander("Configurar incertidumbre", expanded=False):
                u1, u2, u3, u4, u5 = st.columns(5)
                with u1: vt = st.number_input("Tuberías ±%", 0.0, 100.0, 10.0)
                with u2: ve = st.number_input("Emisores ±%", 0.0, 100.0, 10.0)
                with u3: vi = st.number_input("Instalación ±%", 0.0, 100.0, 15.0)
                with u4: vo = st.number_input("Obra civil ±%", 0.0, 100.0, 20.0)
                with u5: vx = st.number_input("Otros ±%", 0.0, 100.0, 10.0)

            if st.button("🎲 Ejecutar Monte Carlo", type="primary"):
                historial_bomba = None
                sel = st.session_state.get("seleccion_bomba_v2") or {}
                if sel.get("id_bomba") is not None:
                    hist = cargar_historial_precios_bomba(sel["id_bomba"], dias=365)
                    if not hist.empty:
                        historial_bomba = hist["precio_clp"]

                p_mc = ParametrosMonteCarlo(
                    n_iteraciones=int(n_mc), seed=int(seed_mc), variacion_tuberias_pct=vt,
                    variacion_emisores_pct=ve, variacion_instalacion_pct=vi,
                    variacion_obra_civil_pct=vo, variacion_otros_pct=vx,
                )
                sim = simular_costos(componentes, p_mc, historial_bomba, objetivo_mc)
                st.session_state["resultado_mc"] = sim

            sim = st.session_state.get("resultado_mc")
            if sim:
                r = sim["resumen"]
                k1, k2, k3, k4 = st.columns(4)
                with k1: kpi_card("P50", f"${r['p50']:,.0f}")
                with k2: kpi_card("P80", f"${r['p80']:,.0f}")
                with k3: kpi_card("P90", f"${r['p90']:,.0f}")
                with k4: kpi_card("Prob. excedencia", f"{r['prob_excedencia_pct']:.1f}%", tono="warn")

                muestras = np.asarray(sim["muestras"], dtype=float)
                fig_hist = go.Figure(go.Histogram(x=muestras, nbinsx=50))
                fig_hist.update_layout(title="Distribución del costo total", xaxis_title="CLP", yaxis_title="Frecuencia", template="plotly_dark")
                st.plotly_chart(fig_hist, width="stretch")

                orden = np.sort(muestras)
                cdf = np.arange(1, len(orden) + 1) / len(orden)
                fig_cdf = go.Figure(go.Scatter(x=orden, y=cdf, mode="lines"))
                fig_cdf.update_layout(title="CDF del costo total", xaxis_title="CLP", yaxis_title="Probabilidad acumulada", template="plotly_dark")
                st.plotly_chart(fig_cdf, width="stretch")
                st.json(sim["supuestos"])

                if st.button("💾 Guardar resumen Monte Carlo en SQL"):
                    if "id_proyecto_sql" not in st.session_state:
                        st.session_state["id_proyecto_sql"] = crear_proyecto_sesion(
                            nombre="Proyecto PAT - sesión Streamlit",
                            datos={"tecnica_riego": st.session_state.get("tecnica_riego")},
                        )
                    id_sim = guardar_resumen_montecarlo(
                        st.session_state["id_proyecto_sql"], n_mc, seed_mc,
                        sim["parametros"], r,
                    )
                    st.success(f"Simulación guardada con ID {id_sim}.")

        _mostrar_navegacion_pat(5)

    # ========================================================
    # RESUMEN LATERAL
    # ========================================================
    with st.sidebar:
        st.markdown("### 📋 Resumen del Proyecto")

        if st.session_state.get("necesidad_total") is not None:
            st.metric(
                "Necesidad total",
                f"{st.session_state['necesidad_total']:.2f} mm/día",
            )

        if "tiempo_riego" in st.session_state:
            st.metric(
                "Tiempo de riego",
                f"{st.session_state['tiempo_riego']:.2f} h",
            )

        if "tdh" in st.session_state:
            st.metric(
                "Caudal sector",
                f"{st.session_state['caudal_sector']:.2f} L/s",
            )

            st.metric(
                "TDH",
                f"{st.session_state['tdh']:.2f} m.c.a.",
            )

            st.metric(
                "Sectores",
                st.session_state.get(
                    "num_sectores",
                    1,
                ),
            )

            if "costo_bombas" in st.session_state:
                st.metric(
                    "Costo bomba (Williams)" if st.session_state.get("estimacion_williams_bomba") else "Costo bombas",
                    f"${st.session_state['costo_bombas']:,.0f}",
                )
                if st.session_state.get("estimacion_williams_bomba"):
                    st.caption("Estimación referencial, no precio real.")

if __name__ == "__main__":
    main()
