# db_reportes.py
# Persistencia de reportes diarios en PostgreSQL (Railway)
# Se llama desde diario.py después de guardar_excels()
# NO modifica ninguna funcionalidad existente.

import os
import asyncio
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "")


# ── Crear tablas si no existen ────────────────────────────────────────────────
CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS reportes_diarios (
    id               SERIAL PRIMARY KEY,
    fecha            DATE        NOT NULL UNIQUE,
    total_licit      INTEGER     DEFAULT 0,
    total_adj        INTEGER     DEFAULT 0,
    adj_con_cuit     INTEGER     DEFAULT 0,
    total_comprar    INTEGER     DEFAULT 0,
    total_tgn        INTEGER     DEFAULT 0,
    total_cruce      INTEGER     DEFAULT 0,
    flujo_completo   INTEGER     DEFAULT 0,
    riesgo_alto      INTEGER     DEFAULT 0,
    riesgo_medio     INTEGER     DEFAULT 0,
    riesgo_bajo      INTEGER     DEFAULT 0,
    indice_promedio  FLOAT       DEFAULT 0,
    creado_en        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_reportes_fecha ON reportes_diarios(fecha DESC);

CREATE TABLE IF NOT EXISTS flujo_licitaciones (
    id                    SERIAL PRIMARY KEY,
    fecha                 DATE,
    organismo_contratante TEXT,
    tipo_proceso_bora     TEXT,
    link_bora             TEXT,
    proveedor_adjudicado  TEXT,
    cuit_proveedor        TEXT,
    monto_adjudicado_bora TEXT,
    en_comprar            TEXT,
    cobro_en_tgn          TEXT,
    beneficiario_tgn      TEXT,
    monto_cobrado_tgn     FLOAT,
    etapa                 TEXT,
    alerta                TEXT,
    indicadores_riesgo    TEXT,
    score_riesgo_licit    FLOAT,
    indice_riesgo_licit   FLOAT,
    nivel_riesgo_licit    TEXT,
    creado_en             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_flujo_fecha ON flujo_licitaciones(fecha DESC);
CREATE INDEX IF NOT EXISTS idx_flujo_nivel ON flujo_licitaciones(nivel_riesgo_licit);
CREATE INDEX IF NOT EXISTS idx_flujo_cuit  ON flujo_licitaciones(cuit_proveedor);

CREATE TABLE IF NOT EXISTS bora_licitaciones (
    id                SERIAL PRIMARY KEY,
    fecha             DATE,
    organismo         TEXT,
    tipo_proceso      TEXT,
    categoria         TEXT,
    aviso_id          TEXT,
    es_adjudicacion   BOOLEAN DEFAULT FALSE,
    link              TEXT,
    creado_en         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_bora_fecha ON bora_licitaciones(fecha DESC);

CREATE TABLE IF NOT EXISTS comprar_procesos (
    id               SERIAL PRIMARY KEY,
    fecha            DATE,
    nro_proceso      TEXT,
    nombre_proceso   TEXT,
    tipo_proceso     TEXT,
    fecha_apertura   TEXT,
    estado           TEXT,
    unidad_ejecutora TEXT,
    link             TEXT,
    creado_en        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_comprar_fecha ON comprar_procesos(fecha DESC);
"""


async def _init_tables(pool):
    async with pool.acquire() as conn:
        await conn.execute(CREATE_TABLES_SQL)
    logger.info("✅ Tablas DB verificadas/creadas")


async def _guardar_reporte(pool, fecha_str: str, resumen: dict):
    """Inserta o actualiza el resumen diario en reportes_diarios."""
    fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO reportes_diarios
                (fecha, total_licit, total_adj, adj_con_cuit,
                 total_comprar, total_tgn, total_cruce,
                 flujo_completo, riesgo_alto, riesgo_medio, riesgo_bajo,
                 indice_promedio)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            ON CONFLICT (fecha) DO UPDATE SET
                total_licit     = EXCLUDED.total_licit,
                total_adj       = EXCLUDED.total_adj,
                adj_con_cuit    = EXCLUDED.adj_con_cuit,
                total_comprar   = EXCLUDED.total_comprar,
                total_tgn       = EXCLUDED.total_tgn,
                total_cruce     = EXCLUDED.total_cruce,
                flujo_completo  = EXCLUDED.flujo_completo,
                riesgo_alto     = EXCLUDED.riesgo_alto,
                riesgo_medio    = EXCLUDED.riesgo_medio,
                riesgo_bajo     = EXCLUDED.riesgo_bajo,
                indice_promedio = EXCLUDED.indice_promedio,
                creado_en       = NOW()
        """,
            fecha,
            resumen.get("total_licit", 0),
            resumen.get("total_adj", 0),
            resumen.get("adj_con_cuit", 0),
            resumen.get("total_comprar", 0),
            resumen.get("total_tgn", 0),
            resumen.get("total_cruce", 0),
            resumen.get("flujo_completo", 0),
            resumen.get("riesgo_alto", 0),
            resumen.get("riesgo_medio", 0),
            resumen.get("riesgo_bajo", 0),
            float(resumen.get("indice_promedio", 0)),
        )
    logger.info(f"✅ Reporte {fecha_str} guardado en DB")


async def _guardar_flujo(pool, fecha_str: str, df_cruce):
    """Inserta filas de flujo_licitaciones, borrando primero las del día."""
    if df_cruce is None or df_cruce.empty:
        return
    fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM flujo_licitaciones WHERE fecha = $1", fecha)
        rows = []
        for _, row in df_cruce.iterrows():
            rows.append((
                fecha,
                str(row.get("organismo_contratante", "") or ""),
                str(row.get("tipo_proceso_bora", "") or ""),
                str(row.get("link_bora", "") or ""),
                str(row.get("proveedor_adjudicado", "") or ""),
                str(row.get("cuit_proveedor", "") or ""),
                str(row.get("monto_adjudicado_bora", "") or ""),
                str(row.get("en_comprar", "") or ""),
                str(row.get("cobro_en_tgn", "") or ""),
                str(row.get("beneficiario_tgn", "") or ""),
                _to_float(row.get("monto_cobrado_tgn")),
                str(row.get("etapa", "") or ""),
                str(row.get("alerta", "") or ""),
                str(row.get("indicadores_riesgo", "") or ""),
                _to_float(row.get("score_riesgo_licit")),
                _to_float(row.get("indice_riesgo_licit")),
                str(row.get("nivel_riesgo_licit", "") or ""),
            ))
        await conn.executemany("""
            INSERT INTO flujo_licitaciones
                (fecha, organismo_contratante, tipo_proceso_bora, link_bora,
                 proveedor_adjudicado, cuit_proveedor, monto_adjudicado_bora,
                 en_comprar, cobro_en_tgn, beneficiario_tgn, monto_cobrado_tgn,
                 etapa, alerta, indicadores_riesgo, score_riesgo_licit,
                 indice_riesgo_licit, nivel_riesgo_licit)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)
        """, rows)
    logger.info(f"✅ {len(rows)} filas de flujo guardadas en DB para {fecha_str}")


async def _guardar_bora(pool, fecha_str: str, df_bora):
    """Inserta filas de bora_licitaciones."""
    if df_bora is None or df_bora.empty:
        return
    fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM bora_licitaciones WHERE fecha = $1", fecha)
        rows = []
        for _, row in df_bora.iterrows():
            rows.append((
                fecha,
                str(row.get("organismo", "") or ""),
                str(row.get("tipo_proceso", "") or ""),
                str(row.get("categoria", "") or ""),
                str(row.get("aviso_id", "") or ""),
                bool(row.get("es_adjudicacion", False)),
                str(row.get("link", "") or ""),
            ))
        await conn.executemany("""
            INSERT INTO bora_licitaciones
                (fecha, organismo, tipo_proceso, categoria,
                 aviso_id, es_adjudicacion, link)
            VALUES ($1,$2,$3,$4,$5,$6,$7)
        """, rows)
    logger.info(f"✅ {len(rows)} filas BORA guardadas en DB para {fecha_str}")


async def _guardar_comprar(pool, fecha_str: str, df_comprar):
    """Inserta filas de comprar_procesos."""
    if df_comprar is None or df_comprar.empty:
        return
    fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM comprar_procesos WHERE fecha = $1", fecha)
        rows = []
        for _, row in df_comprar.iterrows():
            rows.append((
                fecha,
                str(row.get("nro_proceso", "") or ""),
                str(row.get("nombre_proceso", "") or ""),
                str(row.get("tipo_proceso", "") or ""),
                str(row.get("fecha_apertura", "") or ""),
                str(row.get("estado", "") or ""),
                str(row.get("unidad_ejecutora", "") or ""),
                str(row.get("link", "") or ""),
            ))
        await conn.executemany("""
            INSERT INTO comprar_procesos
                (fecha, nro_proceso, nombre_proceso, tipo_proceso,
                 fecha_apertura, estado, unidad_ejecutora, link)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        """, rows)
    logger.info(f"✅ {len(rows)} filas Comprar guardadas en DB para {fecha_str}")


def _to_float(val) -> Optional[float]:
    try:
        if val is None or str(val).strip() in ("", "nan", "None", "NaN"):
            return None
        return float(val)
    except Exception:
        return None


# ── Función pública síncrona — llamada desde diario.py ───────────────────────
def guardar_en_db(fecha_str: str, resumen: dict,
                  df_cruce=None, df_bora=None, df_comprar=None):
    """
    Punto de entrada síncrono para guardar todo en PostgreSQL.
    Se llama al final de diario.py sin modificar su flujo existente.
    """
    if not DATABASE_URL:
        logger.warning("⚠️  DATABASE_URL no configurada — saltando guardado en DB")
        return

    async def _run():
        import asyncpg
        try:
            pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3)
            await _init_tables(pool)
            await _guardar_reporte(pool, fecha_str, resumen)
            if df_cruce is not None:
                await _guardar_flujo(pool, fecha_str, df_cruce)
            if df_bora is not None:
                await _guardar_bora(pool, fecha_str, df_bora)
            if df_comprar is not None:
                await _guardar_comprar(pool, fecha_str, df_comprar)
            await pool.close()
            print(f"✅ Datos del {fecha_str} persistidos en PostgreSQL")
        except Exception as e:
            logger.error(f"❌ Error guardando en DB: {e}")
            print(f"❌ Error DB (datos guardados en xlsx igualmente): {e}")

    try:
        asyncio.run(_run())
    except RuntimeError:
        # Si ya hay un event loop (FastAPI), usar nest_asyncio
        import nest_asyncio
        nest_asyncio.apply()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(_run())


# ── APIs para el dashboard ────────────────────────────────────────────────────
async def get_ultimo_reporte(pool) -> Optional[dict]:
    """Retorna el último reporte diario de la DB."""
    if not pool:
        return None
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM reportes_diarios ORDER BY fecha DESC LIMIT 1"
            )
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error get_ultimo_reporte: {e}")
        return None


async def get_flujo_reciente(pool, limit: int = 50) -> list:
    """Retorna las filas más recientes de flujo_licitaciones."""
    if not pool:
        return []
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM flujo_licitaciones ORDER BY fecha DESC, id DESC LIMIT $1",
                limit
            )
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error get_flujo_reciente: {e}")
        return []


async def get_stats_globales(pool) -> dict:
    """KPIs globales acumulados para el dashboard."""
    if not pool:
        return {}
    try:
        async with pool.acquire() as conn:
            totales = await conn.fetchrow("""
                SELECT
                    COUNT(*)            AS dias_con_datos,
                    SUM(total_cruce)    AS total_procesos,
                    SUM(riesgo_alto)    AS total_alto,
                    SUM(riesgo_medio)   AS total_medio,
                    AVG(indice_promedio) AS indice_prom_global,
                    MAX(fecha)          AS ultimo_dia
                FROM reportes_diarios
            """)
            return dict(totales) if totales else {}
    except Exception as e:
        logger.error(f"Error get_stats_globales: {e}")
        return {}