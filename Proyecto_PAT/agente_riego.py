"""Agente de apoyo técnico para PAT_RIEGO.

El agente NO ejecuta cálculos hidráulicos ni modifica catálogos.
Solo analiza resultados deterministas y entrega una recomendación
estructurada para revisión Human-in-the-Loop (HITL).

Arquitectura:
- GPT-4o-mini: análisis operativo.
- GPT-4o: LLM as a Judge.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv

load_dotenv()


# ============================================================
# CONFIGURACIÓN DE MODELOS
# ============================================================

MODELO_AGENTE_DEFAULT = "gpt-4o-mini"
MODELO_JUDGE_DEFAULT = "gpt-4o"


# ============================================================
# INSTRUCCIONES DEL AGENTE OPERATIVO
# ============================================================

INSTRUCCIONES = """
Eres un asistente técnico para diseño de riego agrícola.

Recibes resultados YA calculados por un motor determinista.
NO debes modificar, recalcular ni inventar:

- caudal Q;
- TDH;
- potencia hidráulica;
- curvas Q-H;
- punto de operación;
- costos calculados;
- scores;
- datos del catálogo maestro;
- disponibilidad comercial.

Tu función es exclusivamente:

1. Explicar los resultados deterministas.
2. Comparar alternativas existentes.
3. Detectar anomalías o inconsistencias.
4. Identificar riesgos técnicos o económicos.
5. Indicar información faltante.
6. Preparar una recomendación para revisión humana.
7. Proponer acciones que un usuario humano pueda revisar.

No inventes especificaciones técnicas.
No afirmes que un equipo está disponible comercialmente si no existe evidencia.
Si falta información, indícalo explícitamente.

La recomendación NO es una aprobación automática.
Toda decisión final debe permanecer bajo revisión Human-in-the-Loop (HITL).

Devuelve EXCLUSIVAMENTE JSON válido con esta estructura exacta:

{
  "recomendacion": "...",
  "alternativa_principal": "...",
  "riesgos": ["..."],
  "advertencias": ["..."],
  "datos_faltantes": ["..."],
  "requiere_hitl": true,
  "acciones_propuestas": ["..."]
}
""".strip()


# ============================================================
# INSTRUCCIONES DEL LLM AS A JUDGE
# ============================================================

INSTRUCCIONES_JUDGE = """
Actúas como evaluador técnico independiente de una recomendación
generada por otro modelo de IA para un sistema de diseño de riego agrícola.

Recibirás:

1. Datos deterministas calculados por el software.
2. La respuesta de un agente técnico.

Debes evaluar exclusivamente si la respuesta del agente:

- respeta los datos deterministas;
- no modifica ni inventa Q, TDH, potencia, costos, curvas Q-H ni scores;
- no afirma disponibilidad comercial sin evidencia;
- distingue correctamente entre estimación preliminar y validación Q-H;
- identifica riesgos y datos faltantes;
- no recomienda una configuración hidráulicamente contradictoria;
- mantiene la necesidad de revisión humana.

NO debes recalcular el proyecto.
NO debes sustituir al motor hidráulico.
NO debes modificar los datos recibidos.

Devuelve EXCLUSIVAMENTE JSON válido con esta estructura exacta:

{
  "aprobado_judge": true,
  "score": 0,
  "consistencia_datos": 0,
  "seguridad_tecnica": 0,
  "trazabilidad": 0,
  "problemas_detectados": [],
  "comentario_judge": "...",
  "requiere_revision": false
}

Todos los scores deben estar entre 0 y 100.

Solo establece "aprobado_judge": true cuando:

- el score global sea >= 80;
- no exista una contradicción técnica crítica;
- la respuesta mantenga la necesidad de HITL cuando corresponda.
""".strip()


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def _extraer_json(texto: str) -> dict[str, Any]:
    """Extrae un objeto JSON desde la respuesta textual del modelo."""

    texto = (texto or "").strip()

    if not texto:
        raise ValueError("OpenAI devolvió una respuesta vacía.")

    # Intento 1: toda la respuesta ya es JSON.
    try:
        resultado = json.loads(texto)

        if not isinstance(resultado, dict):
            raise ValueError(
                "La respuesta JSON no es un objeto/diccionario."
            )

        return resultado

    except json.JSONDecodeError:
        pass

    # Intento 2: elimina ```json ... ```
    texto_limpio = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        texto,
        flags=re.IGNORECASE | re.DOTALL,
    ).strip()

    try:
        resultado = json.loads(texto_limpio)

        if not isinstance(resultado, dict):
            raise ValueError(
                "La respuesta JSON no es un objeto/diccionario."
            )

        return resultado

    except json.JSONDecodeError:
        pass

    # Intento 3: busca un bloque JSON dentro del texto.
    coincidencia = re.search(
        r"\{.*\}",
        texto_limpio,
        re.DOTALL,
    )

    if coincidencia:

        try:
            resultado = json.loads(
                coincidencia.group(0)
            )

            if not isinstance(resultado, dict):
                raise ValueError(
                    "La respuesta JSON no es un objeto/diccionario."
                )

            return resultado

        except json.JSONDecodeError:
            pass

    raise ValueError(
        "La respuesta del modelo no contiene un objeto JSON válido."
    )


def _respuesta_error(
    mensaje: str,
    modelo: str | None,
    texto_modelo: str | None = None,
) -> dict[str, Any]:
    """
    Genera una respuesta de error uniforme.

    De esta forma app.py nunca debería recibir None.
    """

    respuesta = {
        "ok": False,
        "error": mensaje,
        "resultado": None,
        "modelo": modelo,
    }

    # Ayuda para depuración.
    if texto_modelo:
        respuesta["respuesta_cruda"] = texto_modelo[:2000]

    return respuesta


def _validar_resultado_agente(
    resultado: dict[str, Any],
) -> dict[str, Any]:
    """
    Normaliza los campos que app.py espera recibir.
    """

    resultado.setdefault(
        "recomendacion",
        "No se generó una recomendación textual.",
    )

    resultado.setdefault(
        "alternativa_principal",
        "No determinada.",
    )

    resultado.setdefault(
        "riesgos",
        [],
    )

    resultado.setdefault(
        "advertencias",
        [],
    )

    resultado.setdefault(
        "datos_faltantes",
        [],
    )

    resultado.setdefault(
        "acciones_propuestas",
        [],
    )

    resultado["requiere_hitl"] = bool(
        resultado.get(
            "requiere_hitl",
            True,
        )
    )

    # Asegura listas.
    for campo in (
        "riesgos",
        "advertencias",
        "datos_faltantes",
        "acciones_propuestas",
    ):

        if not isinstance(
            resultado[campo],
            list,
        ):
            resultado[campo] = [
                str(resultado[campo])
            ]

    return resultado


def _normalizar_score(
    valor: Any,
) -> int:
    """
    Fuerza un score al rango 0-100.
    """

    try:
        score = int(
            round(
                float(valor)
            )
        )

    except (
        TypeError,
        ValueError,
    ):
        score = 0

    return max(
        0,
        min(
            100,
            score,
        ),
    )


def _validar_resultado_judge(
    resultado: dict[str, Any],
) -> dict[str, Any]:
    """
    Normaliza la salida del Judge.
    """

    resultado["score"] = _normalizar_score(
        resultado.get(
            "score",
            0,
        )
    )

    resultado["consistencia_datos"] = _normalizar_score(
        resultado.get(
            "consistencia_datos",
            0,
        )
    )

    resultado["seguridad_tecnica"] = _normalizar_score(
        resultado.get(
            "seguridad_tecnica",
            0,
        )
    )

    resultado["trazabilidad"] = _normalizar_score(
        resultado.get(
            "trazabilidad",
            0,
        )
    )

    problemas = resultado.get(
        "problemas_detectados",
        [],
    )

    if not isinstance(
        problemas,
        list,
    ):
        problemas = [
            str(problemas)
        ]

    resultado[
        "problemas_detectados"
    ] = problemas

    resultado.setdefault(
        "comentario_judge",
        "Sin comentario adicional.",
    )

    resultado[
        "requiere_revision"
    ] = bool(
        resultado.get(
            "requiere_revision",
            True,
        )
    )

    # --------------------------------------------------------
    # BLINDAJE LOCAL
    # --------------------------------------------------------
    # Aunque el LLM diga aprobado=True,
    # el software no permite aprobar si score < 80.

    aprobado_modelo = bool(
        resultado.get(
            "aprobado_judge",
            False,
        )
    )

    resultado[
        "aprobado_judge"
    ] = bool(
        aprobado_modelo
        and resultado["score"] >= 80
    )

    if not resultado[
        "aprobado_judge"
    ]:
        resultado[
            "requiere_revision"
        ] = True

    return resultado


def _obtener_cliente_openai(
    timeout: float,
):
    """
    Crea el cliente OpenAI.
    """

    api_key = os.getenv(
        "OPENAI_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "No hay OPENAI_API_KEY configurada en el archivo .env."
        )

    try:
        from openai import OpenAI

    except ImportError as exc:
        raise RuntimeError(
            "Falta instalar el paquete openai. "
            "Ejecuta: pip install openai"
        ) from exc

    return OpenAI(
        api_key=api_key,
        timeout=timeout,
    )


# ============================================================
# AGENTE OPERATIVO — GPT-4o-mini
# ============================================================

def analizar_configuracion(
    datos_deterministas: dict[str, Any],
    modelo: str | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """
    Analiza resultados deterministas.

    NO modifica:
    - Q
    - TDH
    - potencia
    - curvas
    - costos
    - catálogo
    """

    modelo_usado = (
        modelo
        or os.getenv(
            "OPENAI_MODEL"
        )
        or MODELO_AGENTE_DEFAULT
    )

    if not isinstance(
        datos_deterministas,
        dict,
    ):
        return _respuesta_error(
            "datos_deterministas debe ser un diccionario.",
            modelo_usado,
        )

    try:
        cliente = _obtener_cliente_openai(
            timeout
        )

    except Exception as exc:
        return _respuesta_error(
            str(exc),
            modelo_usado,
        )

    texto = ""

    try:

        respuesta = cliente.responses.create(
            model=modelo_usado,
            instructions=INSTRUCCIONES,
            input=json.dumps(
                datos_deterministas,
                ensure_ascii=False,
                default=str,
            ),
        )

        texto = getattr(
            respuesta,
            "output_text",
            "",
        ) or ""

        resultado = _extraer_json(
            texto
        )

        resultado = _validar_resultado_agente(
            resultado
        )

        return {
            "ok": True,
            "error": None,
            "resultado": resultado,
            "modelo": modelo_usado,
        }

    except Exception as exc:

        return _respuesta_error(
            f"Error del agente OpenAI: {exc}",
            modelo_usado,
            texto,
        )


# ============================================================
# LLM AS A JUDGE — GPT-4o
# ============================================================

def evaluar_con_judge(
    datos_deterministas: dict[str, Any],
    respuesta_agente: dict[str, Any],
    modelo: str | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """
    Evalúa la respuesta del agente.

    GPT-4o actúa como verificador,
    NO como motor hidráulico.
    """

    modelo_usado = (
        modelo
        or os.getenv(
            "OPENAI_JUDGE_MODEL"
        )
        or MODELO_JUDGE_DEFAULT
    )

    if not isinstance(
        datos_deterministas,
        dict,
    ):
        return _respuesta_error(
            "datos_deterministas debe ser un diccionario.",
            modelo_usado,
        )

    if not isinstance(
        respuesta_agente,
        dict,
    ):
        return _respuesta_error(
            "respuesta_agente debe ser un diccionario.",
            modelo_usado,
        )

    payload = {
        "datos_deterministas":
            datos_deterministas,

        "respuesta_agente":
            respuesta_agente,
    }

    try:
        cliente = _obtener_cliente_openai(
            timeout
        )

    except Exception as exc:
        return _respuesta_error(
            str(exc),
            modelo_usado,
        )

    texto = ""

    try:

        respuesta = cliente.responses.create(
            model=modelo_usado,
            instructions=INSTRUCCIONES_JUDGE,
            input=json.dumps(
                payload,
                ensure_ascii=False,
                default=str,
            ),
        )

        texto = getattr(
            respuesta,
            "output_text",
            "",
        ) or ""

        resultado = _extraer_json(
            texto
        )

        resultado = _validar_resultado_judge(
            resultado
        )

        return {
            "ok": True,
            "error": None,
            "resultado": resultado,
            "modelo": modelo_usado,
        }

    except Exception as exc:

        return _respuesta_error(
            f"Error del Judge OpenAI: {exc}",
            modelo_usado,
            texto,
        )


# ============================================================
# PRUEBA LOCAL OPCIONAL
# ============================================================

if __name__ == "__main__":

    datos_prueba = {
        "accion_solicitada":
            "Revisar riesgo",

        "requerimiento": {
            "caudal_sector_ls":
                35.20,

            "tdh_mca":
                27.24,

            "potencia_requerida_hp":
                20.0,
        },

        "seleccion": {
            "modelo":
                "Bomba de prueba",

            "n_total":
                1,
        },

        "presupuesto_total_clp":
            10_000_000,
    }

    print(
        "\n=== AGENTE OPERATIVO ==="
    )

    respuesta_agente = analizar_configuracion(
        datos_prueba
    )

    print(
        json.dumps(
            respuesta_agente,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )

    if respuesta_agente.get(
        "ok"
    ):

        print(
            "\n=== LLM AS A JUDGE ==="
        )

        respuesta_judge = evaluar_con_judge(
            datos_prueba,
            respuesta_agente[
                "resultado"
            ],
        )

        print(
            json.dumps(
                respuesta_judge,
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )