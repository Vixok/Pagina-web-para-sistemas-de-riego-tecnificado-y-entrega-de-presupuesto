"""Consulta productos de Mercado Libre Chile usando ML_ACCESS_TOKEN."""
import os
import requests
from dotenv import load_dotenv

load_dotenv()


def buscar_productos_ml(palabra_clave, token=None, limite=5):
    token = token or os.getenv("ML_ACCESS_TOKEN")
    if not token:
        return [], "No hay ML_ACCESS_TOKEN configurado en .env."

    url = "https://api.mercadolibre.com/sites/MLC/search"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"q": palabra_clave, "limit": limite}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
    except requests.RequestException as e:
        return [], f"No se pudo conectar a Mercado Libre: {e}"

    if response.status_code == 401:
        return [], (
            "El token de Mercado Libre expiró o es inválido. "
            "Renueva ML_ACCESS_TOKEN; Tavily seguirá funcionando como respaldo."
        )
    if response.status_code != 200:
        return [], f"Mercado Libre devolvió error {response.status_code}: {response.text[:200]}"

    productos = []
    for item in response.json().get("results", []):
        precio = item.get("price")
        if precio:
            productos.append({
                "Fuente": "Mercado Libre",
                "Producto": item.get("title") or "",
                "Precio_CLP": precio,
                "URL": item.get("permalink") or "",
                "Contenido": item.get("title") or "",
            })
    return productos, None
