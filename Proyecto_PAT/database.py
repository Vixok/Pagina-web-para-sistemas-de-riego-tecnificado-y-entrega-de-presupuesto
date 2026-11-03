"""Acceso a SQL Server para PAT_RIEGO.

Todas las escrituras usan commit/rollback/finally y preservan IDs maestros.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from decimal import Decimal

import pandas as pd
import pyodbc


def conectar_sql(timeout=8):
    conexion = pyodbc.connect(
        r"""
        DRIVER={ODBC Driver 18 for SQL Server};
        SERVER=.\SQLEXPRESS;
        DATABASE=PAT_RIEGO;
        Trusted_Connection=yes;
        TrustServerCertificate=yes;
        """,
        timeout=int(timeout),
    )
    cursor = conexion.cursor()
    cursor.execute("SET LOCK_TIMEOUT 10000; SET XACT_ABORT ON;")
    return conexion


def consulta_dataframe(query, parametros=None):
    conexion = conectar_sql()
    try:
        cursor = conexion.cursor()
        if parametros is not None:
            cursor.execute(query, parametros)
        else:
            cursor.execute(query)
        if cursor.description is None:
            return pd.DataFrame()
        columnas = [columna[0] for columna in cursor.description]
        filas = cursor.fetchall()
        return pd.DataFrame([tuple(fila) for fila in filas], columns=columnas)
    finally:
        conexion.close()


def ejecutar_escritura(query, parametros=None, devolver_id=False):
    conexion = conectar_sql()
    try:
        cursor = conexion.cursor()
        if parametros is None:
            cursor.execute(query)
        else:
            cursor.execute(query, parametros)
        nuevo_id = None
        if devolver_id:
            fila = cursor.fetchone()
            nuevo_id = fila[0] if fila else None
        conexion.commit()
        return nuevo_id
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


# -----------------------------------------------------------------------------
# MERCADO / HISTÓRICO DE PRECIOS
# -----------------------------------------------------------------------------

def guardar_cotizaciones_bomba(id_bomba, consulta, resultados, caudal_requerido_ls, tdh_requerida_mca):
    if not resultados:
        return 0
    conexion = conectar_sql()
    cursor = conexion.cursor()
    insertados = 0
    try:
        vistos = set()
        for resultado in resultados:
            url = str(resultado.get("URL") or "").strip()
            fuente = str(resultado.get("Fuente") or "").strip()
            producto = str(resultado.get("Producto") or "").strip()
            precio = resultado.get("Precio_CLP")
            score = float(resultado.get("Score", 0) or 0)
            try:
                precio = float(precio)
            except (TypeError, ValueError):
                continue
            if precio <= 0:
                continue
            llave = (fuente.lower(), url.lower(), producto.lower(), round(precio, 2))
            if llave in vistos:
                continue
            vistos.add(llave)
            cursor.execute(
                """
                INSERT INTO dbo.CotizacionesBombasMercado
                (id_bomba, consulta_busqueda, fuente, producto, precio_clp, url,
                 score_coincidencia, caudal_requerido_ls, tdh_requerida_mca, valida)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                id_bomba, consulta, fuente, producto, precio, url, score,
                float(caudal_requerido_ls), float(tdh_requerida_mca),
                1 if score >= 60 else 0,
            )
            insertados += 1
        conexion.commit()
        return insertados
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def cotizacion_bomba_reciente(id_bomba, horas=24):
    limite = datetime.now() - timedelta(hours=int(horas))
    df = consulta_dataframe(
        """
        SELECT COUNT(*) AS cantidad
        FROM dbo.CotizacionesBombasMercado
        WHERE id_bomba = ? AND fecha_consulta >= ? AND valida = 1
        """,
        (int(id_bomba), limite),
    )
    return bool(not df.empty and int(df.iloc[0]["cantidad"]) > 0)


def cargar_cotizaciones_bombas(horas=168, solo_validas=True):
    limite = datetime.now() - timedelta(hours=int(horas))
    filtro = "AND valida = 1" if solo_validas else ""
    return consulta_dataframe(
        f"""
        SELECT id_cotizacion, id_bomba, consulta_busqueda, fuente, producto,
               precio_clp, url, score_coincidencia, caudal_requerido_ls,
               tdh_requerida_mca, fecha_consulta, valida
        FROM dbo.CotizacionesBombasMercado
        WHERE fecha_consulta >= ? {filtro}
        ORDER BY id_bomba, fecha_consulta DESC
        """,
        (limite,),
    )


def cargar_historial_precios_bomba(id_bomba=None, dias=365):
    limite = datetime.now() - timedelta(days=int(dias))
    if id_bomba is None:
        return consulta_dataframe(
            """
            SELECT c.*, b.codigo_bomba, b.modelo
            FROM dbo.CotizacionesBombasMercado c
            LEFT JOIN dbo.Bombas b ON b.id_bomba=c.id_bomba
            WHERE c.fecha_consulta >= ? AND c.valida=1
            ORDER BY c.fecha_consulta
            """, (limite,)
        )
    return consulta_dataframe(
        """
        SELECT c.*, b.codigo_bomba, b.modelo
        FROM dbo.CotizacionesBombasMercado c
        LEFT JOIN dbo.Bombas b ON b.id_bomba=c.id_bomba
        WHERE c.fecha_consulta >= ? AND c.valida=1 AND c.id_bomba=?
        ORDER BY c.fecha_consulta
        """, (limite, int(id_bomba))
    )


# -----------------------------------------------------------------------------
# CURVAS Q-H
# -----------------------------------------------------------------------------

def cargar_curvas_bombas(solo_activas=True):
    filtro = "WHERE c.activo=1" if solo_activas else ""
    try:
        return consulta_dataframe(
            f"""
            SELECT c.id_punto, c.id_bomba, c.caudal_lmin, c.altura_mca,
                   c.eficiencia_pct, c.potencia_kw, c.fecha_fuente,
                   c.fuente, c.activo, c.validada
            FROM dbo.CurvasBombas c
            {filtro}
            ORDER BY c.id_bomba, c.caudal_lmin
            """
        )
    except pyodbc.Error:
        return pd.DataFrame()


def guardar_punto_curva_bomba(id_bomba, caudal_lmin, altura_mca, eficiencia_pct=None,
                               potencia_kw=None, fuente="Ingreso manual", validada=False):
    return ejecutar_escritura(
        """
        INSERT INTO dbo.CurvasBombas
        (id_bomba, caudal_lmin, altura_mca, eficiencia_pct, potencia_kw, fuente, validada, activo)
        OUTPUT INSERTED.id_punto
        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (int(id_bomba), float(caudal_lmin), float(altura_mca),
         None if eficiencia_pct is None else float(eficiencia_pct),
         None if potencia_kw is None else float(potencia_kw),
         str(fuente), 1 if validada else 0),
        devolver_id=True,
    )


# -----------------------------------------------------------------------------
# CANDIDATOS WEB + HITL
# -----------------------------------------------------------------------------

def guardar_candidato_web(datos: dict):
    return ejecutar_escritura(
        """
        INSERT INTO dbo.CandidatosBombasWeb
        (producto, marca, modelo_detectado, potencia_detectada_hp,
         caudal_detectado_ls, altura_detectada_mca, precio_clp, fuente, url,
         score_coincidencia, consulta_busqueda, estado)
        OUTPUT INSERTED.id_candidato
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datos.get("producto"), datos.get("marca"), datos.get("modelo_detectado"),
            datos.get("potencia_detectada_hp"), datos.get("caudal_detectado_ls"),
            datos.get("altura_detectada_mca"), datos.get("precio_clp"),
            datos.get("fuente"), datos.get("url"), datos.get("score_coincidencia", 0),
            datos.get("consulta_busqueda"), datos.get("estado", "REVISAR"),
        ),
        devolver_id=True,
    )


def cargar_candidatos_web(estado=None):
    if estado:
        return consulta_dataframe(
            "SELECT * FROM dbo.CandidatosBombasWeb WHERE estado=? ORDER BY fecha_consulta DESC",
            (estado,),
        )
    return consulta_dataframe("SELECT * FROM dbo.CandidatosBombasWeb ORDER BY fecha_consulta DESC")


def resolver_candidato_web(id_candidato: int, estado: str):
    estado = str(estado).upper()
    if estado not in {"APROBADO", "RECHAZADO", "REVISAR", "PENDIENTE_HITL"}:
        raise ValueError("Estado de candidato inválido.")
    ejecutar_escritura(
        "UPDATE dbo.CandidatosBombasWeb SET estado=?, fecha_respuesta=SYSDATETIME() WHERE id_candidato=?",
        (estado, int(id_candidato)),
    )


def promover_candidato_a_bomba(id_candidato: int, usuario: str):
    """Promueve SOLO un candidato aprobado y técnicamente completo al catálogo maestro."""
    conexion = conectar_sql()
    try:
        cur = conexion.cursor()
        cur.execute(
            """
            SELECT producto, modelo_detectado, potencia_detectada_hp, caudal_detectado_ls,
                   altura_detectada_mca, precio_clp, fuente, estado
            FROM dbo.CandidatosBombasWeb WITH (UPDLOCK, ROWLOCK)
            WHERE id_candidato=?
            """, int(id_candidato)
        )
        fila = cur.fetchone()
        if not fila:
            raise ValueError("Candidato no existe.")
        producto, modelo, hp, q_ls, h, precio, fuente, estado = fila
        if str(estado).upper() != "APROBADO":
            raise ValueError("El candidato debe estar APROBADO por HITL antes de promoverlo.")
        if hp is None or q_ls is None or h is None:
            raise ValueError("Faltan HP/Q/H; no puede incorporarse al catálogo maestro.")
        codigo = f"WEB-{int(id_candidato):06d}"
        cur.execute("SELECT id_bomba FROM dbo.Bombas WHERE codigo_bomba=?", codigo)
        ex = cur.fetchone()
        if ex:
            conexion.commit()
            return int(ex[0])
        cur.execute(
            """
            INSERT INTO dbo.Bombas
            (codigo_bomba, modelo, tipo, potencia_hp, caudal_max_lmin, altura_max_mca,
             precio_ref_clp, fuente, activo)
            OUTPUT INSERTED.id_bomba
            VALUES (?, ?, 'Centrifuga - candidato web validado', ?, ?, ?, ?, ?, 1)
            """,
            codigo, str(modelo or producto or codigo), float(hp), float(q_ls) * 60.0,
            float(h), float(precio) if precio is not None else None,
            f"{fuente or 'Web'} | aprobado por {usuario}",
        )
        id_bomba = int(cur.fetchone()[0])
        cur.execute(
            "UPDATE dbo.CandidatosBombasWeb SET estado='INCORPORADO', fecha_respuesta=SYSDATETIME() WHERE id_candidato=?",
            int(id_candidato),
        )
        conexion.commit()
        return id_bomba
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


# -----------------------------------------------------------------------------
# PROYECTOS / AGENTE / HITL
# -----------------------------------------------------------------------------

def crear_proyecto_sesion(nombre="Proyecto Streamlit", datos=None):
    """
    Crea un proyecto de sesión usando el mismo mecanismo de snapshot JSON
    que el guardado normal.
    """
    return guardar_proyecto_disenio(
        nombre,
        datos or {},
        id_proyecto=None,
    )


def _normalizar_json_proyecto(valor):
    """
    Convierte recursivamente valores del proyecto a tipos JSON seguros.

    Los NaN/Inf se almacenan como NULL JSON (None) para evitar que
    json.dumps(..., allow_nan=False) falle al guardar snapshots reales.
    """
    if valor is None:
        return None

    try:
        if bool(pd.isna(valor)):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(valor, (str, bool, int)):
        return valor

    if isinstance(valor, Decimal):
        valor = float(valor)

    if isinstance(valor, float):
        numero = float(valor)
        return numero if math.isfinite(numero) else None

    if isinstance(valor, datetime):
        return valor.isoformat()

    if isinstance(valor, dict):
        return {
            str(clave): _normalizar_json_proyecto(contenido)
            for clave, contenido in valor.items()
        }

    if isinstance(valor, (list, tuple, set)):
        return [
            _normalizar_json_proyecto(contenido)
            for contenido in valor
        ]

    if hasattr(valor, "item"):
        try:
            return _normalizar_json_proyecto(valor.item())
        except (TypeError, ValueError):
            pass

    if hasattr(valor, "tolist"):
        try:
            return _normalizar_json_proyecto(valor.tolist())
        except (TypeError, ValueError):
            pass

    raise TypeError(
        f"Tipo no serializable en los datos del proyecto: "
        f"{type(valor).__name__}"
    )


def _preparar_proyecto(nombre, datos):
    """Normaliza y serializa el snapshot del proyecto antes de escribir en SQL."""
    nombre = str(nombre or "").strip()
    if not nombre:
        raise ValueError("El nombre del proyecto no puede estar vacío.")

    if datos is None:
        datos = {}
    if not isinstance(datos, dict):
        raise ValueError("Los datos del proyecto deben ser un diccionario.")

    datos = dict(datos)
    datos_json = json.dumps(
        _normalizar_json_proyecto(datos),
        ensure_ascii=False,
        allow_nan=False,
    )

    area_m2 = datos.get("area_m2")
    superficie_ha = datos.get("superficie_ha")

    if area_m2 is not None:
        area_m2 = float(area_m2)
        if not math.isfinite(area_m2) or area_m2 < 0:
            raise ValueError("area_m2 debe ser un número finito y no negativo.")

    if superficie_ha is None and area_m2 is not None:
        superficie_ha = area_m2 / 10000.0
    elif superficie_ha is not None:
        superficie_ha = float(superficie_ha)
        if not math.isfinite(superficie_ha) or superficie_ha < 0:
            raise ValueError(
                "superficie_ha debe ser un número finito y no negativo."
            )

    valores = (
        nombre,
        datos.get("temporada"),
        datos.get("tecnica_riego"),
        datos.get("latitud"),
        datos.get("longitud"),
        area_m2,
        superficie_ha,
        datos.get("perimetro_m"),
        datos.get("longitud_matriz_m"),
        datos_json,
    )
    return valores


def _guardar_proyecto_cursor(cursor, nombre, datos, id_proyecto=None):
    """Inserta o actualiza un proyecto usando una transacción ya abierta."""
    valores = _preparar_proyecto(nombre, datos)

    if id_proyecto is None:
        cursor.execute(
            """
            INSERT INTO dbo.Proyectos
            (
                nombre,
                temporada,
                tecnica_riego,
                latitud,
                longitud,
                area_m2,
                superficie_ha,
                perimetro_m,
                longitud_matriz_estimada_m,
                datos_json,
                estado
            )
            OUTPUT INSERTED.id_proyecto
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'BORRADOR')
            """,
            valores,
        )
    else:
        try:
            id_proyecto = int(id_proyecto)
        except (TypeError, ValueError) as exc:
            raise ValueError("id_proyecto debe ser un entero válido.") from exc

        if id_proyecto <= 0:
            raise ValueError("id_proyecto debe ser mayor que cero.")

        cursor.execute(
            """
            UPDATE dbo.Proyectos
            SET nombre = ?,
                temporada = ?,
                tecnica_riego = ?,
                latitud = ?,
                longitud = ?,
                area_m2 = ?,
                superficie_ha = ?,
                perimetro_m = ?,
                longitud_matriz_estimada_m = ?,
                datos_json = ?,
                fecha_modificacion = SYSDATETIME()
            OUTPUT INSERTED.id_proyecto
            WHERE id_proyecto = ?
            """,
            (*valores, id_proyecto),
        )

    fila = cursor.fetchone()
    if fila is None:
        if id_proyecto is None:
            raise RuntimeError("SQL Server no devolvió el ID del proyecto.")
        raise ValueError(f"No existe el proyecto con id_proyecto={id_proyecto}.")

    return int(fila[0])


def guardar_proyecto_disenio(nombre, datos, id_proyecto=None):
    """Guarda solo el snapshot del proyecto y retorna su ID."""
    conexion = conectar_sql()
    try:
        cursor = conexion.cursor()
        nuevo_id = _guardar_proyecto_cursor(
            cursor,
            nombre,
            datos,
            id_proyecto=id_proyecto,
        )
        conexion.commit()
        return nuevo_id
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def listar_proyectos_disenio():
    """Lista proyectos recientes sin cargar el contenido completo de datos_json."""
    return consulta_dataframe(
        """
        SELECT TOP (200)
               id_proyecto, nombre, temporada, tecnica_riego, area_m2,
               superficie_ha, estado, fecha_creacion, fecha_modificacion
        FROM dbo.Proyectos
        ORDER BY COALESCE(fecha_modificacion, fecha_creacion) DESC,
                 id_proyecto DESC
        """
    )


def cargar_proyecto_disenio(id_proyecto):
    """Recupera un proyecto por su clave primaria y decodifica datos_json."""
    try:
        id_proyecto = int(id_proyecto)
    except (TypeError, ValueError) as exc:
        raise ValueError("El ID del proyecto debe ser un entero válido.") from exc
    if id_proyecto <= 0:
        raise ValueError("El ID del proyecto debe ser mayor que cero.")

    proyecto_df = consulta_dataframe(
        """
        SELECT id_proyecto, nombre, temporada, tecnica_riego, latitud, longitud,
               area_m2, superficie_ha, perimetro_m,
               longitud_matriz_estimada_m, estado, datos_json
        FROM dbo.Proyectos
        WHERE id_proyecto = ?
        """,
        (id_proyecto,),
    )
    if proyecto_df.empty:
        raise LookupError(f"No se encontró el proyecto con ID {id_proyecto}.")

    fila = proyecto_df.iloc[0]
    json_guardado = fila["datos_json"]
    datos = {}
    if pd.notna(json_guardado):
        try:
            datos = json.loads(json_guardado)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"El proyecto {id_proyecto} tiene datos_json inválido."
            ) from exc
        if not isinstance(datos, dict):
            raise ValueError(
                f"El proyecto {id_proyecto} tiene datos_json que no es un objeto."
            )

    columnas_a_datos = {
        "temporada": "temporada",
        "tecnica_riego": "tecnica_riego",
        "latitud": "latitud",
        "longitud": "longitud",
        "area_m2": "area_m2",
        "superficie_ha": "superficie_ha",
        "perimetro_m": "perimetro_m",
        "longitud_matriz_estimada_m": "longitud_matriz_m",
    }
    for columna, clave in columnas_a_datos.items():
        valor = fila[columna]
        if clave not in datos and pd.notna(valor):
            datos[clave] = float(valor) if clave not in {"temporada", "tecnica_riego"} else valor

    return {
        "id_proyecto": int(fila["id_proyecto"]),
        "nombre": str(fila["nombre"]),
        "estado": fila["estado"],
        "datos": datos,
    }


def guardar_ejecucion_agente(id_proyecto, nombre_agente, modelo, estado, entrada, salida,
                              requiere_hitl=False, version_algoritmo="PAT-V2"):
    return ejecutar_escritura(
        """
        INSERT INTO dbo.EjecucionesAgente
        (id_proyecto, nombre_agente, modelo, estado, entrada, salida, requiere_hitl, version_algoritmo)
        OUTPUT INSERTED.id_ejecucion_agente
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (int(id_proyecto), nombre_agente, modelo, estado,
         json.dumps(entrada, ensure_ascii=False, default=str),
         json.dumps(salida, ensure_ascii=False, default=str),
         1 if requiere_hitl else 0, version_algoritmo),
        devolver_id=True,
    )


def crear_aprobacion_hitl(id_proyecto, id_ejecucion_agente, tipo_decision,
                          comentario=None, accion_solicitada=None, resultado_previo=None):
    return ejecutar_escritura(
        """
        INSERT INTO dbo.AprobacionesHITL
        (id_proyecto, id_ejecucion_agente, tipo_decision, estado, comentario,
         accion_solicitada, resultado_previo)
        OUTPUT INSERTED.id_aprobacion
        VALUES (?, ?, ?, 'PENDIENTE', ?, ?, ?)
        """,
        (int(id_proyecto), id_ejecucion_agente, tipo_decision, comentario,
         accion_solicitada,
         json.dumps(resultado_previo, ensure_ascii=False, default=str) if resultado_previo is not None else None),
        devolver_id=True,
    )


def resolver_aprobacion_hitl(id_aprobacion, estado, usuario, comentario=None, resultado_aprobado=None):
    estado = str(estado).upper()
    if estado not in {"APROBADO", "RECHAZADO", "REVISION"}:
        raise ValueError("Estado HITL inválido.")
    ejecutar_escritura(
        """
        UPDATE dbo.AprobacionesHITL
        SET estado=?, usuario_aprobador=?, comentario=COALESCE(?, comentario),
            resultado_aprobado=?, fecha_respuesta=SYSDATETIME()
        WHERE id_aprobacion=?
        """,
        (estado, usuario, comentario,
         json.dumps(resultado_aprobado, ensure_ascii=False, default=str) if resultado_aprobado is not None else None,
         int(id_aprobacion)),
    )


# -----------------------------------------------------------------------------
# MONTE CARLO
# -----------------------------------------------------------------------------

def guardar_resumen_montecarlo(id_proyecto, n_iteraciones, seed, parametros, resumen):
    conexion = conectar_sql()
    try:
        cur = conexion.cursor()
        cur.execute(
            """
            INSERT INTO dbo.SimulacionesMonteCarlo
            (id_proyecto, n_iteraciones, seed, variables_json, parametros_json, estado)
            OUTPUT INSERTED.id_simulacion
            VALUES (?, ?, ?, ?, ?, 'COMPLETADA')
            """,
            int(id_proyecto), int(n_iteraciones), int(seed),
            json.dumps(list(parametros.keys()), ensure_ascii=False),
            json.dumps(parametros, ensure_ascii=False, default=str),
        )
        id_sim = int(cur.fetchone()[0])
        cur.execute(
            """
            INSERT INTO dbo.ResultadosMonteCarlo
            (id_simulacion, media_clp, desviacion_clp, p05_clp, p10_clp, p50_clp,
             p80_clp, p90_clp, p95_clp, prob_excedencia_pct, presupuesto_objetivo_clp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            id_sim, resumen.get("media"), resumen.get("desviacion"), resumen.get("p05"),
            resumen.get("p10"), resumen.get("p50"), resumen.get("p80"), resumen.get("p90"),
            resumen.get("p95"), resumen.get("prob_excedencia_pct"), resumen.get("presupuesto_objetivo"),
        )
        conexion.commit()
        return id_sim
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()
# ============================================================
# PRESUPUESTOS / HISTÓRICO DE COTIZACIONES
# ============================================================


def _categoria_item_presupuesto(descripcion: str) -> str:
    """Clasifica cada partida para análisis posterior en SQL/Power BI."""
    texto = str(descripcion or "").lower()

    if "matriz" in texto and "tuber" in texto:
        return "TUBERIA_MATRIZ"
    if "lateral" in texto and "tuber" in texto:
        return "TUBERIA_LATERAL"
    if "emisor" in texto:
        return "EMISORES"
    if "filtr" in texto:
        return "FILTRACION"
    if "válvula" in texto or "valvula" in texto or "accesorio" in texto:
        return "ACCESORIOS"
    if any(
        palabra in texto
        for palabra in (
            "obra civil",
            "zanja",
            "excav",
            "relleno",
            "hormig",
            "anclaje",
        )
    ):
        return "OBRA_CIVIL"
    if "bombeo" in texto or "bomba" in texto:
        return "BOMBEO"
    if "instalación" in texto or "instalacion" in texto:
        return "INSTALACION"
    if "iva" in texto:
        return "IMPUESTO"
    return "OTROS"


def _numero_presupuesto(nombre, valor, default=0.0):
    """Convierte un importe/cantidad a float finito y no negativo."""
    if valor is None:
        valor = default
    try:
        numero = float(valor)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{nombre} debe ser numérico.") from exc

    if not math.isfinite(numero):
        raise ValueError(f"{nombre} debe ser un número finito.")
    if numero < 0:
        raise ValueError(f"{nombre} no puede ser negativo.")
    return numero


def _resumen_presupuesto(detalle):
    """Valida la identidad contable del presupuesto y devuelve sus totales."""
    if not isinstance(detalle, dict):
        raise ValueError("detalle debe ser un diccionario.")

    items = detalle.get("items") or []
    if not isinstance(items, list) or not items:
        raise ValueError("El presupuesto no contiene partidas para guardar.")

    costo_instalacion = _numero_presupuesto(
        "costo de instalación",
        detalle.get("p_instalacion"),
    )
    iva = _numero_presupuesto("IVA", detalle.get("iva"))
    total = _numero_presupuesto("total del presupuesto", detalle.get("total"))

    subtotal_materiales = detalle.get("subtotal_materiales")
    if subtotal_materiales is None:
        for item in items:
            if not isinstance(item, dict):
                continue
            descripcion = str(
                item.get("Ítem")
                or item.get("Item")
                or item.get("descripcion")
                or ""
            ).strip()
            if descripcion.lower().startswith("subtotal materiales"):
                subtotal_materiales = item.get(
                    "Subtotal (CLP)",
                    item.get("subtotal_clp"),
                )
                break

    if subtotal_materiales is None:
        subtotal_materiales = total - costo_instalacion - iva

    subtotal_materiales = _numero_presupuesto(
        "subtotal de materiales",
        subtotal_materiales,
    )

    total_reconstruido = subtotal_materiales + costo_instalacion + iva
    tolerancia = max(1.0, abs(total) * 1e-8)
    if not math.isclose(
        total,
        total_reconstruido,
        rel_tol=1e-8,
        abs_tol=tolerancia,
    ):
        raise ValueError(
            "El presupuesto es inconsistente: total != materiales + "
            "instalación + IVA."
        )

    return (
        items,
        subtotal_materiales,
        costo_instalacion,
        iva,
        total,
    )


def _fuente_precio_item(item, categoria, fuente_precio_bomba=None):
    """Determina una fuente trazable para cada partida."""
    fuente = (
        item.get("Fuente")
        or item.get("fuente_precio")
        or item.get("fuente")
    )
    if fuente:
        return str(fuente).strip()[:250]

    if categoria == "BOMBEO":
        return str(
            fuente_precio_bomba or "Catálogo / mercado PAT"
        )[:250]
    if categoria == "OBRA_CIVIL":
        return "Estimación / cubicación obra civil PAT"
    if categoria == "IMPUESTO":
        return "IVA legal aplicado por el motor PAT"
    if categoria == "INSTALACION":
        return "Supuesto porcentual de instalación PAT"
    return "Motor determinista PAT"


def _insertar_presupuesto_cursor(
    cursor,
    id_proyecto,
    detalle,
    incluir_iva=True,
    fuente_precio_bomba=None,
):
    """Inserta cabecera e ítems usando una transacción SQL ya abierta."""
    try:
        id_proyecto = int(id_proyecto)
    except (TypeError, ValueError) as exc:
        raise ValueError("id_proyecto debe ser un entero válido.") from exc

    if id_proyecto <= 0:
        raise ValueError("id_proyecto debe ser mayor que cero.")

    (
        items,
        subtotal_materiales,
        costo_instalacion,
        iva,
        total,
    ) = _resumen_presupuesto(detalle)

    cursor.execute(
        """
        SELECT 1
        FROM dbo.Proyectos
        WHERE id_proyecto = ?
        """,
        (id_proyecto,),
    )
    if cursor.fetchone() is None:
        raise ValueError(f"No existe el proyecto con ID {id_proyecto}.")

    cursor.execute(
        """
        INSERT INTO dbo.Presupuestos
        (
            id_proyecto,
            subtotal_materiales_clp,
            costo_instalacion_clp,
            iva_clp,
            total_clp,
            incluye_iva
        )
        OUTPUT INSERTED.id_presupuesto
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            id_proyecto,
            subtotal_materiales,
            costo_instalacion,
            iva,
            total,
            1 if incluir_iva else 0,
        ),
    )

    fila = cursor.fetchone()
    if fila is None:
        raise RuntimeError("SQL Server no devolvió id_presupuesto.")

    id_presupuesto = int(fila[0])

    for item in items:
        if not isinstance(item, dict):
            continue

        descripcion = str(
            item.get("Ítem")
            or item.get("Item")
            or item.get("descripcion")
            or ""
        ).strip()

        if not descripcion:
            continue

        descripcion_lower = descripcion.lower()

        # Son filas resumen, no partidas.
        if descripcion_lower == "total":
            continue
        if descripcion_lower.startswith("subtotal materiales"):
            continue

        subtotal = _numero_presupuesto(
            f"subtotal de {descripcion}",
            item.get(
                "Subtotal (CLP)",
                item.get("subtotal_clp"),
            ),
        )

        cantidad_raw = item.get(
            "Cantidad",
            item.get("cantidad"),
        )
        if cantidad_raw is None:
            cantidad = 1.0
        else:
            cantidad = _numero_presupuesto(
                f"cantidad de {descripcion}",
                cantidad_raw,
                default=1.0,
            )
            if cantidad <= 0:
                cantidad = 1.0

        unidad = str(
            item.get("Unidad")
            or item.get("unidad")
            or "global"
        ).strip()[:30] or "global"

        precio_unitario_raw = (
            item.get("Precio unitario (CLP/m³)")
            if "Precio unitario (CLP/m³)" in item
            else item.get(
                "Precio unitario (CLP)",
                item.get("precio_unitario_clp"),
            )
        )
        if precio_unitario_raw is None:
            precio_unitario = subtotal / cantidad if cantidad > 0 else subtotal
        else:
            precio_unitario = _numero_presupuesto(
                f"precio unitario de {descripcion}",
                precio_unitario_raw,
            )

        categoria = _categoria_item_presupuesto(descripcion)
        fuente_precio = _fuente_precio_item(
            item,
            categoria,
            fuente_precio_bomba=fuente_precio_bomba,
        )

        cursor.execute(
            """
            INSERT INTO dbo.PresupuestoItems
            (
                id_presupuesto,
                categoria,
                descripcion,
                cantidad,
                unidad,
                precio_unitario_clp,
                subtotal_clp,
                fuente_precio
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                id_presupuesto,
                categoria[:100],
                descripcion[:250],
                cantidad,
                unidad,
                precio_unitario,
                subtotal,
                fuente_precio[:250],
            ),
        )

    return id_presupuesto


def guardar_presupuesto_proyecto(
    id_proyecto,
    detalle,
    incluir_iva=True,
    fuente_precio_bomba=None,
):
    """Guarda una fotografía histórica del presupuesto y retorna su ID."""
    conexion = conectar_sql()
    try:
        cursor = conexion.cursor()
        id_presupuesto = _insertar_presupuesto_cursor(
            cursor,
            id_proyecto=id_proyecto,
            detalle=detalle,
            incluir_iva=incluir_iva,
            fuente_precio_bomba=fuente_precio_bomba,
        )
        conexion.commit()
        return id_presupuesto
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def guardar_proyecto_con_presupuesto(
    nombre,
    datos,
    detalle,
    id_proyecto=None,
    incluir_iva=True,
    fuente_precio_bomba=None,
):
    """
    Guarda proyecto + presupuesto + partidas en una única transacción.

    Si falla cualquier INSERT/UPDATE, se ejecuta rollback y no queda
    persistencia parcial.
    """
    conexion = conectar_sql()
    try:
        cursor = conexion.cursor()

        id_proyecto_guardado = _guardar_proyecto_cursor(
            cursor,
            nombre,
            datos,
            id_proyecto=id_proyecto,
        )

        id_presupuesto = _insertar_presupuesto_cursor(
            cursor,
            id_proyecto=id_proyecto_guardado,
            detalle=detalle,
            incluir_iva=incluir_iva,
            fuente_precio_bomba=fuente_precio_bomba,
        )

        conexion.commit()
        return id_proyecto_guardado, id_presupuesto

    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()

