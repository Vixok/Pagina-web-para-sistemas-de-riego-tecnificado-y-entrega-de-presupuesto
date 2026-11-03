from __future__ import annotations

import importlib
import sys

REQUIRED_DATABASE_FUNCS = [
    "conectar_sql",
    "consulta_dataframe",
    "cargar_curvas_bombas",
    "cargar_historial_precios_bomba",
    "crear_proyecto_sesion",
    "guardar_ejecucion_agente",
    "crear_aprobacion_hitl",
    "resolver_aprobacion_hitl",
    "guardar_resumen_montecarlo",
    "cargar_candidatos_web",
    "resolver_candidato_web",
    "promover_candidato_a_bomba",
]

REQUIRED_MODULES = [
    "database",
    "mercado_equipos",
    "optimizador_bombeo",
    "agente_riego",
    "simulacion_montecarlo",
    "proveedor_tavily",
    "proveedor_mercadolibre",
]

REQUIRED_TABLES = [
    "Bombas",
    "CotizacionesBombasMercado",
    "CurvasBombas",
    "CandidatosBombasWeb",
    "EjecucionesAgente",
    "AprobacionesHITL",
    "SimulacionesMonteCarlo",
    "ResultadosMonteCarlo",
    "VersionesEsquemaPAT",
]


def ok(msg):
    print(f"✅ {msg}")


def bad(msg):
    print(f"❌ {msg}")


def main():
    print("=" * 70)
    print("VERIFICACIÓN PAT_RIEGO ARQUITECTURA V2")
    print("=" * 70)

    for name in REQUIRED_MODULES:
        try:
            importlib.import_module(name)
            ok(f"Módulo importable: {name}.py")
        except Exception as exc:
            bad(f"Módulo {name}.py: {type(exc).__name__}: {exc}")

    try:
        db = importlib.import_module("database")
    except Exception as exc:
        bad(f"No se pudo importar database.py: {exc}")
        sys.exit(1)

    missing = [name for name in REQUIRED_DATABASE_FUNCS if not hasattr(db, name)]
    if missing:
        bad("database.py NO es la versión V2. Faltan: " + ", ".join(missing))
    else:
        ok("database.py contiene todas las funciones V2 requeridas")

    try:
        placeholders = ",".join("?" for _ in REQUIRED_TABLES)
        df = db.consulta_dataframe(
            f"""
            SELECT name
            FROM sys.tables
            WHERE name IN ({placeholders})
            ORDER BY name
            """,
            tuple(REQUIRED_TABLES),
        )
        found = set(df["name"].astype(str)) if not df.empty else set()
        for table in REQUIRED_TABLES:
            if table in found:
                ok(f"Tabla SQL: dbo.{table}")
            else:
                bad(f"Falta tabla SQL: dbo.{table}")
    except Exception as exc:
        bad(f"No se pudo comprobar SQL Server: {type(exc).__name__}: {exc}")
        sys.exit(1)

    try:
        version = db.consulta_dataframe(
            "SELECT TOP 1 version_codigo, fecha_aplicacion FROM dbo.VersionesEsquemaPAT ORDER BY fecha_aplicacion DESC"
        )
        if not version.empty:
            ok(f"Versión de esquema registrada: {version.iloc[0]['version_codigo']}")
        else:
            bad("VersionesEsquemaPAT existe, pero no contiene una versión registrada")
    except Exception as exc:
        bad(f"No se pudo leer versión de esquema: {exc}")

    print("=" * 70)
    if missing:
        print("RESULTADO: hay archivos antiguos mezclados con la V2.")
        sys.exit(2)
    print("RESULTADO: estructura Python + SQL V2 verificada.")


if __name__ == "__main__":
    main()
