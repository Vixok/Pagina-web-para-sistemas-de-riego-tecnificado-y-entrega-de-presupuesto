"""
Búsqueda web de referencias de precio con Tavily.
Se usa como fuente de mercado/segunda opinión: el precio se extrae del texto.
"""
import os
import re
from dotenv import load_dotenv

load_dotenv()

PATRON_PRECIO_CLP = re.compile(r"\$\s?([\d]{1,3}(?:[.,]\d{3})+)")


def extraer_precio_clp(texto):
    match = PATRON_PRECIO_CLP.search(texto or "")
    if not match:
        return None
    try:
        return int(match.group(1).replace(".", "").replace(",", ""))
    except ValueError:
        return None


def buscar_precios_tavily(producto, api_key=None, max_resultados=5):
    api_key = api_key or os.getenv("TAVILY_API_KEY")
    if not api_key:
        return [], "No hay TAVILY_API_KEY configurada en .env."

    try:
        from tavily import TavilyClient
    except ImportError:
        return [], "Falta instalar tavily-python: pip install tavily-python"

    try:
        cliente = TavilyClient(api_key=api_key)
        respuesta = cliente.search(
            query=f"{producto} comprar Chile precio CLP",
            search_depth="advanced",
            max_results=max_resultados,
            include_answer=True,
        )
    except Exception as e:
        return [], f"Error de conexión con Tavily: {e}"

    resultados = []
    for r in respuesta.get("results", []):
        contenido = r.get("content", "") or ""
        titulo = r.get("title", "") or ""
        precio = extraer_precio_clp(contenido)
        if precio is None:
            precio = extraer_precio_clp(titulo)
        if precio is not None:
            resultados.append({
                "Fuente": "Web (Tavily)",
                "Producto": titulo,
                "Precio_CLP": precio,
                "URL": r.get("url", ""),
                "Contenido": contenido,
            })

    return resultados, None
