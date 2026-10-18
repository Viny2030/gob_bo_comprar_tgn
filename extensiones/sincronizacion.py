"""
Carga de los reportes Excel en PostgreSQL.

Hoy la base casi no recibe reportes:
  * el cron de GitHub Actions no tiene DATABASE_URL ni instala asyncpg;
  * la corrida en vivo de main.py usa el pool de la app desde otro event loop
    (asyncio.run dentro de un hilo), algo que asyncpg no admite.

Este módulo lee los Excel (que sí se guardan siempre) y los carga con las
funciones de db_reportes.py, sin modificarlas. Lo usan:
  * tools/backfill_db.py (todo el histórico, desde la línea de comandos), y
  * POST /api/admin/sincronizar-db (un día, desde la app, en el loop correcto).
"""
import os

import pandas as pd

from db_reportes import (_guardar_bora, _guardar_comprar, _guardar_flujo,
                         _guardar_reporte, _init_tables)

ALERTA_FLUJO_COMPLETO = "🚨 FLUJO COMPLETO: BORA→COMPRAR→TGN"


def _hoja(ruta: str, nombres: list) -> pd.DataFrame:
    if not os.path.exists(ruta):
        return pd.DataFrame()
    xl = pd.ExcelFile(ruta)
    hoja = next((h for h in nombres if h in xl.sheet_names), None)
    if not hoja:
        return pd.DataFrame()
    # dtype=str: los CUIT sin guiones no se convierten en número
    return xl.parse(hoja, dtype=str).fillna("")


def leer_dia(data_dir: str, fecha: str) -> dict:
    """Lee los dos Excel de un día y arma lo que necesita db_reportes."""
    carpeta = os.path.join(data_dir, fecha[:7])
    reporte = os.path.join(carpeta, f"reporte_{fecha}.xlsx")
    flujo = os.path.join(carpeta, f"flujo_licitaciones_{fecha}.xlsx")

    df_cruce = _hoja(reporte, ["🚨 Flujo Completo"])
    if df_cruce.empty:
        df_cruce = _hoja(flujo, ["🔗 Flujo Cruzado"])
    df_adj = _hoja(reporte, ["🏆 Adjudicaciones"])
    if df_adj.empty:
        df_adj = _hoja(flujo, ["✅ Adjudicados con CUIT"])
    df_licit = _hoja(reporte, ["📰 BORA Licitaciones"])
    df_comprar = _hoja(reporte, ["🛒 Comprar"])
    if df_comprar.empty:
        df_comprar = _hoja(flujo, ["⏳ Licitaciones Abiertas"])
    df_tgn = _hoja(reporte, ["💰 TGN"])

    # El índice completo del BORA (licitaciones + adjudicaciones) para bora_licitaciones
    filas_bora = []
    for _, r in df_licit.iterrows():
        filas_bora.append({"organismo": r.get("organismo", ""), "tipo_proceso": r.get("tipo_proceso", ""),
                           "categoria": r.get("categoria", ""), "aviso_id": r.get("aviso_id", ""),
                           "es_adjudicacion": False, "link": r.get("link", "")})
    for _, r in df_adj.iterrows():
        filas_bora.append({"organismo": r.get("organismo_contratante", ""), "tipo_proceso": r.get("tipo_proceso", ""),
                           "categoria": "", "aviso_id": r.get("aviso_id", ""),
                           "es_adjudicacion": True, "link": r.get("link", "")})
    df_bora = pd.DataFrame(filas_bora)

    def contar(col, valor):
        return int((df_cruce[col] == valor).sum()) if col in df_cruce.columns else 0

    indice = 0.0
    if "indice_riesgo_licit" in df_cruce.columns and not df_cruce.empty:
        serie = pd.to_numeric(df_cruce["indice_riesgo_licit"], errors="coerce")
        indice = round(float(serie.mean()), 2) if serie.notna().any() else 0.0

    resumen = {
        "total_licit": len(df_licit),
        "total_adj": len(df_adj),
        "adj_con_cuit": int((df_adj.get("cuit_proveedor", pd.Series(dtype=str)) != "").sum()),
        "total_comprar": len(df_comprar),
        "total_tgn": len(df_tgn),
        "total_cruce": len(df_cruce),
        "flujo_completo": contar("alerta", ALERTA_FLUJO_COMPLETO),
        "riesgo_alto": contar("nivel_riesgo_licit", "Alto"),
        "riesgo_medio": contar("nivel_riesgo_licit", "Medio"),
        "riesgo_bajo": contar("nivel_riesgo_licit", "Bajo"),
        "indice_promedio": indice,
    }
    existe = os.path.exists(reporte) or os.path.exists(flujo)
    return {"fecha": fecha, "existe": existe, "resumen": resumen,
            "df_cruce": df_cruce, "df_bora": df_bora, "df_comprar": df_comprar}


def fechas_disponibles(data_dir: str) -> list:
    """Fechas (AAAA-MM-DD) que tienen reporte_ o flujo_licitaciones_ en data_dir."""
    import re
    patron = re.compile(r"^(?:reporte|flujo_licitaciones)_(\d{4}-\d{2}-\d{2})\.xlsx$")
    fechas = set()
    for _, _, archivos in os.walk(data_dir):
        for a in archivos:
            m = patron.match(a)
            if m:
                fechas.add(m.group(1))
    return sorted(fechas)


async def cargar_dia(pool, data_dir: str, fecha: str) -> dict:
    """Carga un día en PostgreSQL (reemplaza las filas de esa fecha). Devuelve el resumen."""
    dia = leer_dia(data_dir, fecha)
    if not dia["existe"]:
        return {"fecha": fecha, "cargado": False, "motivo": "no hay reporte para esa fecha"}
    await _init_tables(pool)
    await _guardar_reporte(pool, fecha, dia["resumen"])
    await _guardar_flujo(pool, fecha, dia["df_cruce"])
    await _guardar_bora(pool, fecha, dia["df_bora"])
    await _guardar_comprar(pool, fecha, dia["df_comprar"])
    return {"fecha": fecha, "cargado": True, **dia["resumen"]}
