"""Importa puntos Q-H REALES desde CSV y los deja validados solo si se solicita.

CSV esperado: codigo_bomba,caudal_lmin,altura_mca,eficiencia_pct,potencia_kw,fuente,validada
No incluye datos ficticios; usa fichas de fabricante o ingreso técnico validado.
"""
import pandas as pd
from database import conectar_sql

ARCHIVO = "CurvasBombas_template.csv"


def main():
    df = pd.read_csv(ARCHIVO)
    if df.empty:
        print("El archivo no contiene puntos. Carga datos reales del fabricante antes de ejecutar.")
        return
    req = {"codigo_bomba", "caudal_lmin", "altura_mca"}
    if not req.issubset(df.columns):
        raise ValueError(f"Faltan columnas obligatorias: {sorted(req - set(df.columns))}")

    con = conectar_sql()
    try:
        cur = con.cursor()
        total = 0
        for _, r in df.iterrows():
            cur.execute("SELECT id_bomba FROM dbo.Bombas WHERE codigo_bomba=? AND activo=1", str(r["codigo_bomba"]).strip())
            f = cur.fetchone()
            if not f:
                print(f"⚠️ Bomba no encontrada: {r['codigo_bomba']}")
                continue
            id_bomba = int(f[0])
            validada = 1 if str(r.get("validada", "0")).strip().lower() in {"1","true","si","sí","yes"} else 0
            cur.execute(
                """
                INSERT INTO dbo.CurvasBombas
                (id_bomba, caudal_lmin, altura_mca, eficiencia_pct, potencia_kw, fuente, validada, activo)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """,
                id_bomba, float(r["caudal_lmin"]), float(r["altura_mca"]),
                None if pd.isna(r.get("eficiencia_pct")) else float(r.get("eficiencia_pct")),
                None if pd.isna(r.get("potencia_kw")) else float(r.get("potencia_kw")),
                str(r.get("fuente") or "Ficha fabricante"), validada,
            )
            total += 1
        con.commit()
        print(f"✅ {total} puntos Q-H importados.")
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


if __name__ == "__main__":
    main()
