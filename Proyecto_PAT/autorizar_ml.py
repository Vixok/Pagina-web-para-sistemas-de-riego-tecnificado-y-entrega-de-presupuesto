import os
import secrets
import requests
import webbrowser
from urllib.parse import urlencode, urlparse, parse_qs
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("ML_CLIENT_ID")
CLIENT_SECRET = os.getenv("ML_CLIENT_SECRET")
REDIRECT_URI = os.getenv("ML_REDIRECT_URI")

if not CLIENT_ID:
    raise ValueError("Falta ML_CLIENT_ID en .env")

if not CLIENT_SECRET:
    raise ValueError("Falta ML_CLIENT_SECRET en .env")

if not REDIRECT_URI:
    raise ValueError("Falta ML_REDIRECT_URI en .env")

state = secrets.token_urlsafe(24)

params = {
    "response_type": "code",
    "client_id": CLIENT_ID,
    "redirect_uri": REDIRECT_URI,
    "state": state,
}

url_autorizacion = (
    "https://auth.mercadolibre.cl/authorization?"
    + urlencode(params)
)

print("\n1. Abriendo autorización de Mercado Libre...\n")
print(url_autorizacion)

webbrowser.open(url_autorizacion)

print(
    "\n2. Autoriza la aplicación.\n"
    "3. Cuando Mercado Libre te redirija, copia la URL COMPLETA "
    "de la barra del navegador."
)

url_final = input("\nPega aquí la URL completa: ").strip()

query = parse_qs(urlparse(url_final).query)

codigo = query.get("code", [None])[0]
state_recibido = query.get("state", [None])[0]

if not codigo:
    raise ValueError(
        "No se encontró el parámetro 'code' en la URL."
    )

if state_recibido != state:
    raise ValueError(
        "El parámetro state no coincide. Cancela la autorización."
    )

print("\nIntercambiando código por tokens...")

respuesta = requests.post(
    "https://api.mercadolibre.com/oauth/token",
    headers={
        "accept": "application/json",
        "content-type": "application/x-www-form-urlencoded",
    },
    data={
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": codigo,
        "redirect_uri": REDIRECT_URI,
    },
    timeout=30,
)

if not respuesta.ok:
    print("\n❌ Error de Mercado Libre")
    print("HTTP:", respuesta.status_code)
    print(respuesta.text)
    raise SystemExit(1)

datos = respuesta.json()
print("\nCampos recibidos:", list(datos.keys()))
print("Scope:", datos.get("scope"))
print("¿Tiene refresh_token?:", "refresh_token" in datos)

access_token = datos.get("access_token")
refresh_token = datos.get("refresh_token")
expires_in = datos.get("expires_in")

print("\n✅ Autorización correcta.")
print("Duración Access Token:", expires_in, "segundos")

if access_token:
    print("Access Token recibido:", access_token[:12] + "...")

if refresh_token:
    print("Refresh Token recibido:", refresh_token[:12] + "...")

print(
    "\nAhora agrega estos dos valores COMPLETOS a tu .env:\n"
    "ML_ACCESS_TOKEN=<access token recibido>\n"
    "ML_REFRESH_TOKEN=<refresh token recibido>"
)