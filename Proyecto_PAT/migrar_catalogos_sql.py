"""Migración segura de catálogos CSV -> SQL Server.

V2: NO borra catálogos maestros. Hace UPSERT por claves naturales para preservar IDs
históricos y relaciones FK.
"""
from __future__ import annotations

import re
import pandas as pd
from database import conectar_sql


def limpiar_precio(valor):
    if pd.isna(valor):
        return None
    texto = str(valor).replace("$", "").replace(" ", "").strip()
    # En estos CSV los separadores son de miles.
    texto = texto.replace(",", "").replace(".", "")
    try:
        return float(texto)
    except ValueError:
        return None


def valor_o_none(valor):
    return None if pd.isna(valor) else valor


def numero_sql(valor):
    if pd.isna(valor):
        return None
    texto = str(valor).strip().replace(",", ".")
    if not texto:
        return None
    try:
        return float(texto)
    except ValueError:
        return None


def upsert_bomba(cur, fila):
    codigo = str(fila["ID_Bomba"]).strip()
    eficiencia = valor_o_none(fila.get("Eficiencia_Ref"))
    eficiencia_pct = float(eficiencia) * 100 if eficiencia is not None else None
    valores = (
        codigo, str(fila["Tipo"]), valor_o_none(fila["Potencia_HP"]),
        valor_o_none(fila["Caudal_Max_Lmin"]), valor_o_none(fila["Altura_Max_mca"]),
        valor_o_none(fila.get("Diametro_Conexion_Pulgadas")), valor_o_none(fila["Voltaje_V"]),
        eficiencia_pct, limpiar_precio(fila["Precio_Ref_CLP"]), "Bombas.csv", codigo,
    )
    cur.execute(
        """
        UPDATE dbo.Bombas SET modelo=?, tipo=?, potencia_hp=?, caudal_max_lmin=?,
            altura_max_mca=?, diametro_conexion_pulgadas=?, voltaje_v=?, eficiencia_pct=?,
            precio_ref_clp=?, fuente=?, activo=1
        WHERE codigo_bomba=?
        """, valores
    )
    if cur.rowcount == 0:
        cur.execute(
            """
            INSERT INTO dbo.Bombas
            (codigo_bomba, modelo, tipo, potencia_hp, caudal_max_lmin, altura_max_mca,
             diametro_conexion_pulgadas, voltaje_v, eficiencia_pct, precio_ref_clp, fuente, activo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            codigo, codigo, str(fila["Tipo"]), valor_o_none(fila["Potencia_HP"]),
            valor_o_none(fila["Caudal_Max_Lmin"]), valor_o_none(fila["Altura_Max_mca"]),
            valor_o_none(fila.get("Diametro_Conexion_Pulgadas")), valor_o_none(fila["Voltaje_V"]),
            eficiencia_pct, limpiar_precio(fila["Precio_Ref_CLP"]), "Bombas.csv",
        )


def upsert_tuberia(cur, fila):
    codigo = str(fila["ID_Tubo"]).strip()
    material = str(fila["Material"])
    pn = re.search(r"PN\s*\d+", material, re.I)
    presion_nominal = pn.group(0) if pn else None
    precio_tira = limpiar_precio(fila["Precio_Tira_CLP_Ref"])
    largo = valor_o_none(fila["Largo_Tira_m"])
    precio_metro = precio_tira / float(largo) if precio_tira is not None and largo and float(largo) > 0 else None
    cur.execute(
        """
        UPDATE dbo.Tuberias SET material=?, diametro_nominal_mm=?, diametro_pulgadas=?,
            diametro_interior_mm=?, coef_hazen=?, rugosidad_mm=?, largo_tira_m=?,
            precio_tira_clp=?, precio_metro_clp=?, presion_nominal=?, activo=1
        WHERE codigo_tubo=?
        """,
        material, valor_o_none(fila["Diametro_Nominal_mm"]), valor_o_none(fila["Diametro_Pulgadas"]),
        valor_o_none(fila["Diametro_Interior_mm"]), valor_o_none(fila["Factor_C"]),
        valor_o_none(fila["Rugosidad_e_mm"]), largo, precio_tira, precio_metro, presion_nominal, codigo,
    )
    if cur.rowcount == 0:
        cur.execute(
            """
            INSERT INTO dbo.Tuberias
            (codigo_tubo, material, diametro_nominal_mm, diametro_pulgadas, diametro_interior_mm,
             coef_hazen, rugosidad_mm, largo_tira_m, precio_tira_clp, precio_metro_clp,
             presion_nominal, activo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            codigo, material, valor_o_none(fila["Diametro_Nominal_mm"]),
            valor_o_none(fila["Diametro_Pulgadas"]), valor_o_none(fila["Diametro_Interior_mm"]),
            valor_o_none(fila["Factor_C"]), valor_o_none(fila["Rugosidad_e_mm"]), largo,
            precio_tira, precio_metro, presion_nominal,
        )


def upsert_emisor(cur, fila):
    codigo = str(fila["ID_Emisor"]).strip()
    nombre = str(fila["Tipo Emisor"])
    cur.execute(
        """
        UPDATE dbo.Emisores SET nombre=?, tipo=?, caudal_lh=?, presion_operacion_mca=?,
            radio_cobertura_m=?, unidad_venta=?, precio_clp=?, activo=1
        WHERE codigo_emisor=?
        """,
        nombre, nombre, valor_o_none(fila["Caudal Nominal LPH"]),
        valor_o_none(fila["Presion Operación mca"]), valor_o_none(fila["Radio Mojado m"]),
        str(fila["Unidad Venta"]), limpiar_precio(fila["Precio RefCLP"]), codigo,
    )
    if cur.rowcount == 0:
        cur.execute(
            """
            INSERT INTO dbo.Emisores
            (codigo_emisor, nombre, tipo, caudal_lh, presion_operacion_mca,
             radio_cobertura_m, unidad_venta, precio_clp, activo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            codigo, nombre, nombre, valor_o_none(fila["Caudal Nominal LPH"]),
            valor_o_none(fila["Presion Operación mca"]), valor_o_none(fila["Radio Mojado m"]),
            str(fila["Unidad Venta"]), limpiar_precio(fila["Precio RefCLP"]),
        )


def upsert_accesorio(cur, fila):
    nombre = str(fila["Tipo de Accesorio / Válvula"]).strip()
    ld = valor_o_none(fila["Relación Longitud Equivalente (L/D)"])
    cur.execute(
        "UPDATE dbo.Accesorios SET tipo='Accesorio hidráulico', relacion_longitud_equivalente_ld=?, activo=1 WHERE nombre=?",
        ld, nombre,
    )
    if cur.rowcount == 0:
        cur.execute(
            "INSERT INTO dbo.Accesorios(nombre, tipo, relacion_longitud_equivalente_ld, activo) VALUES (?, 'Accesorio hidráulico', ?, 1)",
            nombre, ld,
        )


def upsert_material(cur, material, rug, cmin, cmax):
    cur.execute(
        "UPDATE dbo.MaterialesTuberia SET rugosidad_absoluta_mm=?, factor_c_min=?, factor_c_max=?, activo=1 WHERE material=?",
        rug, cmin, cmax, material,
    )
    if cur.rowcount == 0:
        cur.execute(
            "INSERT INTO dbo.MaterialesTuberia(material, rugosidad_absoluta_mm, factor_c_min, factor_c_max, activo) VALUES (?, ?, ?, ?, 1)",
            material, rug, cmin, cmax,
        )


def main():
    print("=" * 64)
    print("MIGRACIÓN SEGURA DE CATÁLOGOS - PAT RIEGO V2")
    print("IDs maestros se preservan; no se ejecutan DELETE masivos.")
    print("=" * 64)
    conexion = conectar_sql()
    try:
        cur = conexion.cursor()

        df = pd.read_csv("Bombas.csv", encoding="latin1")
        for _, fila in df.iterrows():
            upsert_bomba(cur, fila)
        print(f"✅ Bombas UPSERT: {len(df)}")

        df = pd.read_csv("Emisores.csv", encoding="latin1")  # archivo que contiene tuberías en este proyecto
        for _, fila in df.iterrows():
            upsert_tuberia(cur, fila)
        print(f"✅ Tuberías UPSERT: {len(df)}")

        df = pd.read_csv("Materiales.csv", encoding="latin1")  # archivo que contiene emisores
        for _, fila in df.iterrows():
            upsert_emisor(cur, fila)
        print(f"✅ Emisores UPSERT: {len(df)}")

        df = pd.read_csv("Accesorios.csv", encoding="latin1")
        for _, fila in df.iterrows():
            upsert_accesorio(cur, fila)
        print(f"✅ Accesorios UPSERT: {len(df)}")

        df = pd.read_csv("Tuberias.csv", encoding="utf-8", header=1)
        c_rug = "RUGOSIDAD ABSOLUTA e(mm)"
        c_min = "Factor C (Hazen-Williams) (limite inferior)"
        c_max = "Factor C (Hazen-Williams) (limite superior)"
        for _, fila in df.iterrows():
            upsert_material(
                cur, str(fila["MATERIAL"]).strip(), numero_sql(fila[c_rug]),
                numero_sql(fila[c_min]), numero_sql(fila[c_max]),
            )
        print(f"✅ Materiales tubería UPSERT: {len(df)}")

        conexion.commit()
        print("\n✅ MIGRACIÓN COMPLETADA. IDs históricos preservados.")
    except Exception:
        conexion.rollback()
        print("\n❌ Error: transacción revertida; no quedaron cambios parciales.")
        raise
    finally:
        conexion.close()


if __name__ == "__main__":
    main()
