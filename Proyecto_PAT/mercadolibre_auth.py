import os
import requests
from pathlib import Path
from dotenv import load_dotenv, set_key

load_dotenv()

ENV_PATH = Path(".env")


def renovar_token_ml():
    client_id = os.getenv("ML_CLIENT_ID")
    client_secret = os.getenv("ML_CLIENT_SECRET")
    refresh_token = os.getenv("ML_REFRESH_TOKEN")

    if not client_id:
        raise RuntimeError("Falta ML_CLIENT_ID")

    if not client_secret:
        raise RuntimeError("Falta ML_CLIENT_SECRET")

    if not refresh_token:
        raise RuntimeError(
            "Falta ML_REFRESH_TOKEN. "
            "Debes realizar una autorización inicial."
        )

    respuesta = requests.post(
        "https://api.mercadolibre.com/oauth/token",
        headers={
            "accept": "application/json",
            "content-type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        },
        timeout=30,
    )

    if not respuesta.ok:
        raise RuntimeError(
            f"Mercado Libre rechazó la renovación: "
            f"{respuesta.status_code} - {respuesta.text}"
        )

    datos = respuesta.json()

    nuevo_access = datos.get("access_token")
    nuevo_refresh = datos.get("refresh_token")

    if not nuevo_access:
        raise RuntimeError(
            "Mercado Libre no devolvió access_token."
        )

    if not nuevo_refresh:
        raise RuntimeError(
            "Mercado Libre no devolvió refresh_token."
        )

    # Actualiza .env
    set_key(
        str(ENV_PATH),
        "ML_ACCESS_TOKEN",
        nuevo_access,
    )

    set_key(
        str(ENV_PATH),
        "ML_REFRESH_TOKEN",
        nuevo_refresh,
    )

    # Actualiza también este proceso de Python
    os.environ["ML_ACCESS_TOKEN"] = nuevo_access
    os.environ["ML_REFRESH_TOKEN"] = nuevo_refresh

    return {
        "access_token": nuevo_access,
        "refresh_token": nuevo_refresh,
        "expires_in": datos.get("expires_in"),
        "scope": datos.get("scope"),
    }