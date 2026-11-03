import math

import requests
import streamlit as st
from shapely.errors import ShapelyError
from shapely.geometry import Polygon, shape


URL_COMUNAS = (
    "https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/"
    "9469f09592ced973a3448cf66b6100b741b64c0d/releaseData/gbOpen/CHL/ADM3/"
    "geoBoundaries-CHL-ADM3_simplified.geojson"
)
URL_REGIONES = (
    "https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/"
    "9469f09592ced973a3448cf66b6100b741b64c0d/releaseData/gbOpen/CHL/ADM1/"
    "geoBoundaries-CHL-ADM1_simplified.geojson"
)


def normalizar_nombre_administrativo(nombre: str) -> str:
    """Recupera nombres UTF-8 que llegaron decodificados previamente como Latin-1."""
    if not any(marcador in nombre for marcador in ("\u00c3", "\u00c2")):
        return nombre
    try:
        recuperado = nombre.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return nombre
    if recuperado == nombre or any(
        marcador in recuperado for marcador in ("\u00c3", "\u00c2")
    ):
        return nombre
    return recuperado


def _descargar_geojson(url):
    respuesta = requests.get(
        url,
        headers={"User-Agent": "PAT-Riego/1.0 (administrative boundaries)"},
        timeout=(5, 20),
    )
    respuesta.raise_for_status()
    datos = respuesta.json()
    if not isinstance(datos, dict) or not isinstance(datos.get("features"), list):
        raise ValueError("El proveedor devolvió límites administrativos inválidos.")
    return datos


@st.cache_data(ttl=30 * 24 * 60 * 60, max_entries=1, show_spinner=False)
def cargar_limites_administrativos():
    return {
        "comunas": _descargar_geojson(URL_COMUNAS),
        "regiones": _descargar_geojson(URL_REGIONES),
    }


def _nombres_intersectados(poligono, geojson):
    nombres = set()
    umbral_area = max(poligono.area * 1e-8, 1e-12)
    for feature in geojson["features"]:
        propiedades = feature.get("properties") or {}
        nombre = propiedades.get("shapeName") or propiedades.get("name")
        geometria_geojson = feature.get("geometry")
        if not nombre or not geometria_geojson:
            continue
        geometria = shape(geometria_geojson)
        if poligono.intersects(geometria):
            if poligono.intersection(geometria).area > umbral_area:
                nombres.add(normalizar_nombre_administrativo(str(nombre).strip()))
    return sorted(nombres)


def resolver_ubicacion_poligono(coordenadas, geojson_comunas, geojson_regiones):
    try:
        puntos = [
            (float(coordenada[0]), float(coordenada[1]))
            for coordenada in coordenadas
        ]
    except (TypeError, ValueError, IndexError):
        return None

    if len(puntos) < 4 or any(
        not math.isfinite(valor) for punto in puntos for valor in punto
    ):
        return None

    try:
        poligono = Polygon(puntos)
        if poligono.is_empty or not poligono.is_valid or poligono.area == 0:
            return None

        comunas = _nombres_intersectados(poligono, geojson_comunas)
        if not comunas:
            return None

        regiones = _nombres_intersectados(poligono, geojson_regiones)
    except ShapelyError as exc:
        raise ValueError("Los límites administrativos no son válidos.") from exc

    return {
        "comuna": comunas[0] if len(comunas) == 1 else None,
        "comunas": comunas,
        "region": regiones[0] if len(regiones) == 1 else None,
        "regiones": regiones,
        "pais": "Chile",
    }


@st.cache_data(ttl=7 * 24 * 60 * 60, max_entries=512, show_spinner=False)
def identificar_ubicacion_predio(coordenadas):
    limites = cargar_limites_administrativos()
    ubicacion = resolver_ubicacion_poligono(
        coordenadas,
        limites["comunas"],
        limites["regiones"],
    )
    if ubicacion is None:
        return None
    for clave in ("comuna", "region"):
        nombre = ubicacion[clave]
        if nombre is not None:
            ubicacion[clave] = normalizar_nombre_administrativo(nombre)
    for clave in ("comunas", "regiones"):
        ubicacion[clave] = [
            normalizar_nombre_administrativo(nombre)
            for nombre in ubicacion[clave]
        ]
    return ubicacion
