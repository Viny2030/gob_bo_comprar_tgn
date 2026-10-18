"""
tools/recalcular_historico.py
=============================
Vuelve a aplicar la Matriz de Riesgo Licitatorio a todos los reportes de data/
y guarda el resultado en OTRA carpeta (por defecto recalculado/). Los Excel
originales no se tocan.

Por qué: los reportes viejos se calcularon con versiones anteriores de la
matriz (por ejemplo, con el indicador retirado "Adjudicación mismo día de
publicación", que sumaba puntos al 100% de las filas). Así, comparar días de
distintos meses mezcla metodologías.

Para cada día escribe recalculado/AAAA-MM/flujo_recalculado_AAAA-MM-DD.xlsx con:
  * columnas *_original : lo que dice el reporte guardado
  * columnas actuales   : analisis.analizar_adjudicaciones (la matriz de hoy)
  * columnas *_v2       : analisis_v2 (divisor solo con indicadores activables)
y un recalculado/resumen.csv con los conteos Alto/Medio/Bajo de las tres.

Uso:
    python tools/recalcular_historico.py
    python tools/recalcular_historico.py --desde 2026-09-01 --salida /tmp/recalc
"""
import argparse
import contextlib
import io
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import pandas as pd  # noqa: E402

from analisis_v2 import analizar_adjudicaciones_v2  # noqa: E402
from extensiones.sincronizacion import _hoja, fechas_disponibles  # noqa: E402

COLS_RIESGO = ["indicadores_riesgo", "score_riesgo_licit", "indice_riesgo_licit", "nivel_riesgo_licit"]
RETIRADO = "mismo día de publicación"


def _conteo(serie):
    v = serie.value_counts() if serie is not None else {}
    return {n: int(v.get(n, 0)) for n in ("Alto", "Medio", "Bajo")}


def recalcular_dia(data_dir, fecha):
    carpeta = os.path.join(data_dir, fecha[:7])
    reporte = os.path.join(carpeta, f"reporte_{fecha}.xlsx")
    flujo = os.path.join(carpeta, f"flujo_licitaciones_{fecha}.xlsx")
    df = _hoja(reporte, ["🚨 Flujo Completo"])
    if df.empty:
        df = _hoja(flujo, ["🔗 Flujo Cruzado"])
    if df.empty or "organismo_contratante" not in df.columns:
        return None, None
    df_tgn = _hoja(reporte, ["💰 TGN"])

    original = df[[c for c in COLS_RIESGO if c in df.columns]].copy()
    base = df.drop(columns=[c for c in COLS_RIESGO if c in df.columns])
    if "fecha" not in base.columns:
        base["fecha"] = fecha
    with contextlib.redirect_stdout(io.StringIO()):  # analizar_adjudicaciones imprime un resumen
        nuevo = analizar_adjudicaciones_v2(base, df_tgn if not df_tgn.empty else None)
    for c in original.columns:
        nuevo[f"{c}_original"] = original[c].values

    retirado = (original["indicadores_riesgo"].str.contains(RETIRADO, na=False).sum()
                if "indicadores_riesgo" in original.columns else 0)
    fila = {"fecha": fecha, "filas": len(nuevo), "con_indicador_retirado": int(retirado)}
    for nombre, col in (("original", original.get("nivel_riesgo_licit")),
                        ("actual", nuevo["nivel_riesgo_licit"]),
                        ("v2", nuevo["nivel_riesgo_licit_v2"])):
        for nivel, n in _conteo(col).items():
            fila[f"{nivel.lower()}_{nombre}"] = n
    for nombre, col in (("original", original.get("indice_riesgo_licit")),
                        ("actual", nuevo["indice_riesgo_licit"]),
                        ("v2", nuevo["indice_riesgo_licit_v2"])):
        fila[f"suma_indice_{nombre}"] = float(pd.to_numeric(col, errors="coerce").sum()) if col is not None else 0.0
    return nuevo, fila


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", default=os.path.join(RAIZ, "data"))
    p.add_argument("--salida", default=os.path.join(RAIZ, "recalculado"))
    p.add_argument("--desde")
    p.add_argument("--hasta")
    a = p.parse_args()

    if os.path.abspath(a.salida).startswith(os.path.abspath(a.data_dir)):
        print("❌ La salida no puede estar dentro de data/: el sitio la listaría como reportes.")
        return 1

    fechas = [f for f in fechas_disponibles(a.data_dir)
              if (not a.desde or f >= a.desde) and (not a.hasta or f <= a.hasta)]
    resumen = []
    for f in fechas:
        nuevo, fila = recalcular_dia(a.data_dir, f)
        if nuevo is None:
            print(f"  ⏭️  {f}: sin flujo cruzado")
            continue
        destino = os.path.join(a.salida, f[:7])
        os.makedirs(destino, exist_ok=True)
        nuevo.to_excel(os.path.join(destino, f"flujo_recalculado_{f}.xlsx"), index=False, engine="openpyxl")
        resumen.append(fila)
        print(f"  ✅ {f}: {fila['filas']} filas · medio {fila['medio_original']}→{fila['medio_actual']} "
              f"(v2 {fila['medio_v2']}) · alto {fila['alto_original']}→{fila['alto_actual']} (v2 {fila['alto_v2']})")

    if resumen:
        os.makedirs(a.salida, exist_ok=True)
        df = pd.DataFrame(resumen)
        df.to_csv(os.path.join(a.salida, "resumen.csv"), index=False, encoding="utf-8")
        tot = df.drop(columns=["fecha"]).sum()
        print(f"\n📊 {len(df)} días · {int(tot['filas'])} filas · "
              f"{int(tot['con_indicador_retirado'])} filas tenían el indicador retirado")
        for nombre in ("original", "actual", "v2"):
            print(f"   {nombre:>8}: Alto {int(tot[f'alto_{nombre}'])} · Medio {int(tot[f'medio_{nombre}'])} "
                  f"· Bajo {int(tot[f'bajo_{nombre}'])} · índice promedio "
                  f"{tot[f'suma_indice_{nombre}'] / max(tot['filas'], 1):.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
