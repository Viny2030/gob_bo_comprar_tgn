from fastapi import FastAPI, HTTPException, Request, Depends, Header
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
import os
import json
import logging
import hashlib
import pandas as pd
import httpx
import asyncpg

# ── PostgreSQL ───────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "")
ADMIN_KEY    = os.getenv("ADMIN_KEY", "")

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── DB pool ──────────────────────────────────────────────────────────────────
db_pool: Optional[asyncpg.Pool] = None

# ── Lifespan — solo PostgreSQL, SIN scraping al arrancar ────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool
    if DATABASE_URL:
        try:
            db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
            await init_db(db_pool)
            logger.info("✅ PostgreSQL conectado")
        except Exception as e:
            logger.warning(f"⚠️  PostgreSQL no disponible: {e}")
    else:
        logger.warning("⚠️  DATABASE_URL no configurada – estadísticas desactivadas")

    yield

    if db_pool:
        await db_pool.close()

# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Monitor XAI - Ph.D. Monteverde",
    description="Algoritmos contra la Corrupción",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

DATA_DIR = "/app/data" if os.path.exists("/app") else "data"
os.makedirs(DATA_DIR, exist_ok=True)
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
_df_cache = None

# ── DB helpers ───────────────────────────────────────────────────────────────
async def get_db() -> Optional[asyncpg.Pool]:
    return db_pool

async def init_db(pool: asyncpg.Pool):
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS donation_events (
                id           SERIAL PRIMARY KEY,
                event_type   TEXT        NOT NULL,
                country      TEXT,
                currency     TEXT,
                ip_hash      TEXT,
                referrer     TEXT,
                ga_client_id TEXT,
                user_agent   TEXT,
                created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_donation_events_created
                ON donation_events(created_at);
            CREATE INDEX IF NOT EXISTS idx_donation_events_type
                ON donation_events(event_type);
        """)

# ── Schemas ──────────────────────────────────────────────────────────────────
class DonationEvent(BaseModel):
    event_type:   str
    country:      Optional[str] = None
    currency:     Optional[str] = None
    ga_client_id: Optional[str] = None
    referrer:     Optional[str] = None

def hash_ip(ip: str) -> str:
    return hashlib.sha256(ip.encode()).hexdigest()[:16]

# ── Helpers ──────────────────────────────────────────────────────────────────
def buscar_todos_los_xlsx(base_dir):
    archivos = []
    for root, dirs, files in os.walk(base_dir):
        for f in files:
            if f.startswith("reporte_202") and f.endswith(".xlsx"):
                archivos.append(os.path.join(root, f))
    archivos.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    return archivos

def etiqueta_archivo(ruta):
    partes = ruta.replace("\\", "/").split("/")
    return f"{partes[-2]} / {partes[-1]}" if len(partes) >= 3 else partes[-1]

def leer_hoja(ruta, hojas_preferidas):
    try:
        xl = pd.ExcelFile(ruta)
        hoja = next((h for h in hojas_preferidas if h in xl.sheet_names), None)
        if not hoja:
            return []
        df = xl.parse(hoja).fillna("").astype(str)
        return df.to_dict(orient="records")
    except Exception as e:
        print(f"Error leyendo {ruta}: {e}")
        return []

def cargar_ultimo_reporte():
    global _df_cache
    if _df_cache is not None and not _df_cache.empty:
        return _df_cache
    archivos = buscar_todos_los_xlsx(DATA_DIR)
    if not archivos:
        return pd.DataFrame()
    try:
        xl = pd.ExcelFile(archivos[0])
        hojas = ["🚨 Flujo Completo", "🔗 Flujo Cruzado", "Sheet1"]
        hoja = next((h for h in hojas if h in xl.sheet_names), xl.sheet_names[0])
        return xl.parse(hoja)
    except Exception as e:
        print(f"Error cargando reporte: {e}")
        return pd.DataFrame()

def set_cache(df):
    global _df_cache
    _df_cache = df

def guardar_excels_con_fecha(df_cruce, df_adj, df_licit, df_comprar, df_tgn, fecha_str):
    from analisis import analizar_adjudicaciones
    mes_str = fecha_str[:7]
    carpeta = os.path.join(DATA_DIR, mes_str)
    os.makedirs(carpeta, exist_ok=True)
    df_cruce_con_riesgo = pd.DataFrame()
    if not df_cruce.empty:
        try:
            df_cruce_con_riesgo = analizar_adjudicaciones(df_cruce, df_tgn)
        except Exception:
            df_cruce_con_riesgo = df_cruce.copy()
    archivo1 = os.path.join(carpeta, f"reporte_{fecha_str}.xlsx")
    with pd.ExcelWriter(archivo1, engine="openpyxl") as writer:
        df_out = df_cruce_con_riesgo if not df_cruce_con_riesgo.empty else df_cruce
        if not df_out.empty:
            df_out.to_excel(writer, sheet_name="🚨 Flujo Completo", index=False)
        if not df_adj.empty:
            df_adj.to_excel(writer, sheet_name="🏆 Adjudicaciones", index=False)
        if not df_licit.empty:
            df_licit.to_excel(writer, sheet_name="📰 BORA Licitaciones", index=False)
        if not df_comprar.empty:
            df_comprar.to_excel(writer, sheet_name="🛒 Comprar", index=False)
        if not df_tgn.empty:
            df_tgn.to_excel(writer, sheet_name="💰 TGN", index=False)
    archivo2 = os.path.join(carpeta, f"flujo_licitaciones_{fecha_str}.xlsx")
    with pd.ExcelWriter(archivo2, engine="openpyxl") as writer:
        if not df_adj.empty:
            df_con_cuit = df_adj[df_adj["cuit_proveedor"].astype(bool)].copy()
            if not df_con_cuit.empty:
                df_con_cuit.to_excel(writer, sheet_name="✅ Adjudicados con CUIT", index=False)
        df_flujo = df_cruce_con_riesgo if not df_cruce_con_riesgo.empty else df_cruce
        if not df_flujo.empty:
            df_flujo.to_excel(writer, sheet_name="🔗 Flujo Cruzado", index=False)
        if not df_comprar.empty:
            df_comprar.to_excel(writer, sheet_name="⏳ Licitaciones Abiertas", index=False)
    return archivo1, archivo2

# ── Páginas ──────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    archivos = buscar_todos_los_xlsx(DATA_DIR)
    df = cargar_ultimo_reporte()
    total = len(df) if not df.empty else 0
    indice_prom = (round(df["indice_fenomeno_corruptivo"].mean(), 2)
                   if not df.empty and "indice_fenomeno_corruptivo" in df.columns else 0)
    alto_riesgo = (len(df[df["nivel_riesgo_teorico"] == "Alto"])
                   if not df.empty and "nivel_riesgo_teorico" in df.columns else 0)
    tipo_counts = (df["tipo_decision"].value_counts().to_dict()
                   if not df.empty and "tipo_decision" in df.columns else {})
    riesgo_counts = (df["nivel_riesgo_teorico"].value_counts().to_dict()
                     if not df.empty and "nivel_riesgo_teorico" in df.columns else {})
    tabla = []
    if not df.empty:
        cols = ["nro_proceso", "detalle", "tipo_decision", "indice_fenomeno_corruptivo", "nivel_riesgo_teorico"]
        tabla = df[[c for c in cols if c in df.columns]].head(50).fillna("n/a").to_dict(orient="records")
    ga_id = os.getenv("GA_MEASUREMENT_ID", "")
    return templates.TemplateResponse("dashboard.html", {
        "request": request, "total": total, "indice_prom": indice_prom,
        "alto_riesgo": alto_riesgo, "total_reportes": len(archivos),
        "tipo_counts": tipo_counts, "riesgo_counts": riesgo_counts,
        "tabla": tabla, "sin_datos": df.empty,
        "ultimo_reporte": etiqueta_archivo(archivos[0]) if archivos else "Sin reportes — ejecute Análisis en Vivo",
        "ga_id": ga_id,
    })

@app.get("/analisis-vivo", response_class=HTMLResponse)
async def analisis_vivo(request: Request):
    return templates.TemplateResponse("analisis.html", {"request": request})

@app.get("/documentacion", response_class=HTMLResponse)
async def documentacion(request: Request):
    from analisis import MATRIZ_TEORICA
    escenarios = [{"nombre": k, "transferencia": v["transferencia"], "peso": v["peso"]}
                  for k, v in MATRIZ_TEORICA.items()]
    ga_id = os.getenv("GA_MEASUREMENT_ID", "")
    return templates.TemplateResponse("documentacion.html", {
        "request": request, "escenarios": escenarios, "ga_id": ga_id,
    })

@app.get("/licitaciones", response_class=HTMLResponse)
async def licitaciones(request: Request):
    ga_id = os.getenv("GA_MEASUREMENT_ID", "")
    return templates.TemplateResponse("licitaciones.html", {"request": request, "ga_id": ga_id})

# ── API Status ───────────────────────────────────────────────────────────────
@app.get("/api/status")
def status():
    archivos = buscar_todos_los_xlsx(DATA_DIR)
    return {"status": "activo", "version": "1.0.0", "data_dir": DATA_DIR,
            "reportes_en_disco": len(archivos), "cache_activo": _df_cache is not None and not _df_cache.empty}

@app.get("/api/reportes")
def listar_reportes():
    archivos = buscar_todos_los_xlsx(DATA_DIR)
    return {"total": len(archivos), "reportes": [etiqueta_archivo(r) for r in archivos]}

@app.get("/api/dias-disponibles")
def dias_disponibles():
    inicio = datetime(2026, 2, 23).date()
    hoy    = datetime.now().date()
    dias_todos = []
    dia = inicio
    while dia <= hoy:
        dias_todos.append(dia.strftime("%Y-%m-%d"))
        dia += timedelta(days=1)
    dias_con_datos = []
    for d in dias_todos:
        carpeta = os.path.join(DATA_DIR, d[:7])
        if os.path.exists(os.path.join(carpeta, f"reporte_{d}.xlsx")) or \
           os.path.exists(os.path.join(carpeta, f"flujo_licitaciones_{d}.xlsx")):
            dias_con_datos.append(d)
    return {"dias_todos": dias_todos, "dias": dias_con_datos,
            "total_dias": len(dias_todos), "con_datos": len(dias_con_datos)}

@app.get("/api/licitaciones/datos")
def datos_licitaciones(fecha: str = None):
    if fecha:
        try:
            datetime.strptime(fecha, "%Y-%m-%d")
            fecha_str = fecha
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato inválido. Use YYYY-MM-DD")
    else:
        archivos = buscar_todos_los_xlsx(DATA_DIR)
        if not archivos:
            return {"fecha": None, "flujo": [], "bora_licitaciones": [],
                    "bora_adjudicaciones": [], "comprar": [], "tgn": [], "sin_datos": True}
        fecha_str = os.path.basename(archivos[0]).replace("reporte_", "").replace(".xlsx", "")
    carpeta = os.path.join(DATA_DIR, fecha_str[:7])
    reporte = os.path.join(carpeta, f"reporte_{fecha_str}.xlsx")
    flujo   = os.path.join(carpeta, f"flujo_licitaciones_{fecha_str}.xlsx")
    if not os.path.exists(reporte) and not os.path.exists(flujo):
        return {"fecha": fecha_str, "flujo": [], "bora_licitaciones": [],
                "bora_adjudicaciones": [], "comprar": [], "tgn": [], "sin_datos": True}
    flujo_data   = leer_hoja(reporte, ["🚨 Flujo Completo", "🔗 Flujo Cruzado"]) if os.path.exists(reporte) else []
    bora_licit   = leer_hoja(reporte, ["📰 BORA Licitaciones"])                  if os.path.exists(reporte) else []
    bora_adj     = leer_hoja(reporte, ["🏆 Adjudicaciones"])                     if os.path.exists(reporte) else []
    comprar_data = leer_hoja(reporte, ["🛒 Comprar"])                            if os.path.exists(reporte) else []
    tgn_data     = leer_hoja(reporte, ["💰 TGN"])                                if os.path.exists(reporte) else []
    if not comprar_data and os.path.exists(flujo):
        comprar_data = leer_hoja(flujo, ["⏳ Licitaciones Abiertas"])
    if not bora_adj and os.path.exists(flujo):
        bora_adj = leer_hoja(flujo, ["✅ Adjudicados con CUIT"])
    return {
        "fecha": fecha_str, "flujo": flujo_data, "bora_licitaciones": bora_licit,
        "bora_adjudicaciones": bora_adj, "comprar": comprar_data, "tgn": tgn_data,
        "sin_datos": False,
        "totales": {
            "flujo": len(flujo_data), "licit": len(bora_licit),
            "adj": len(bora_adj), "comprar": len(comprar_data), "tgn": len(tgn_data),
        },
    }

@app.post("/api/analisis")
def ejecutar_analisis():
    try:
        import diario
        from analisis import analizar_boletin
        df_nuevo = diario.extraer_comprar()
        if df_nuevo is None or df_nuevo.empty:
            raise HTTPException(status_code=404, detail="No se pudieron obtener datos del portal.")
        df_res, path_excel, _ = analizar_boletin(df_nuevo)
        set_cache(df_res)
        return {"status": "ok", "reporte": os.path.basename(path_excel) if path_excel else "guardado_en_memoria",
                "total_procesos": len(df_res),
                "indice_promedio": round(df_res["indice_fenomeno_corruptivo"].mean(), 2) if not df_res.empty else 0}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/marco-teorico")
def marco_teorico():
    from analisis import MATRIZ_TEORICA
    return {"escenarios": [{"escenario": k, "transferencia": v.get("transferencia")}
                            for k, v in MATRIZ_TEORICA.items()]}

@app.get("/api/descargar-articulo")
def descargar_articulo():
    from fastapi.responses import FileResponse
    ruta = "articulo_monteverde_español.docx"
    if not os.path.exists(ruta):
        raise HTTPException(status_code=404, detail="Artículo no disponible")
    return FileResponse(path=ruta, filename="articulo_monteverde_español.docx",
                        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

@app.get("/api/descargar-instructivo")
def descargar_instructivo():
    from fastapi.responses import FileResponse
    ruta = "instructivo_dashboard.docx"
    if not os.path.exists(ruta):
        raise HTTPException(status_code=404, detail="Instructivo no disponible")
    return FileResponse(path=ruta, filename="Instructivo_Monitor_XAI.docx",
                        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

@app.post("/api/licitaciones/ejecutar")
def ejecutar_licitaciones(fecha: str = None):
    try:
        from diario import (extraer_bora_licitaciones, extraer_bora_adjudicaciones,
                            extraer_comprar, extraer_pagos_tgn, cruzar_fuentes)
        if fecha:
            try:
                datetime.strptime(fecha, "%Y-%m-%d")
                fecha_str = fecha
            except ValueError:
                raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD")
        else:
            fecha_str = datetime.now().strftime("%Y-%m-%d")
        df_bora    = extraer_bora_licitaciones()
        df_adj     = extraer_bora_adjudicaciones(df_bora)
        df_licit   = (df_bora[df_bora["es_adjudicacion"] == False].copy().reset_index(drop=True)
                      if not df_bora.empty else pd.DataFrame())
        df_comprar = extraer_comprar()
        df_tgn     = extraer_pagos_tgn()
        df_cruce   = cruzar_fuentes(df_adj, df_comprar, df_tgn)
        archivo1, archivo2 = guardar_excels_con_fecha(df_cruce, df_adj, df_licit, df_comprar, df_tgn, fecha_str)
        con_cuit       = int(df_adj["cuit_proveedor"].astype(bool).sum()) if not df_adj.empty else 0
        flujo_completo = (int((df_cruce["alerta"] == "🚨 FLUJO COMPLETO: BORA→COMPRAR→TGN").sum())
                          if not df_cruce.empty else 0)
        riesgo_alto  = int((df_cruce["nivel_riesgo_licit"] == "Alto").sum())  if "nivel_riesgo_licit" in df_cruce.columns else 0
        riesgo_medio = int((df_cruce["nivel_riesgo_licit"] == "Medio").sum()) if "nivel_riesgo_licit" in df_cruce.columns else 0
        return {
            "status": "ok", "fecha": fecha_str,
            "licitaciones_bora": len(df_licit), "adjudicaciones": len(df_adj),
            "adjudicaciones_con_cuit": con_cuit, "comprar": len(df_comprar),
            "tgn": len(df_tgn), "flujo_cruzado": len(df_cruce),
            "flujo_completo": flujo_completo, "riesgo_alto": riesgo_alto, "riesgo_medio": riesgo_medio,
            "archivo_reporte": os.path.basename(archivo1), "archivo_flujo": os.path.basename(archivo2),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── API Donaciones ───────────────────────────────────────────────────────────
@app.post("/api/donation-event")
async def record_donation_event(
    event: DonationEvent,
    request: Request,
    db: asyncpg.Pool = Depends(get_db),
):
    ip_hash = hash_ip(request.client.host if request.client else "unknown")
    ua = request.headers.get("user-agent", "")[:200]
    if db:
        try:
            async with db.acquire() as conn:
                await conn.execute("""
                    INSERT INTO donation_events
                        (event_type, country, currency, ip_hash, referrer, ga_client_id, user_agent)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, event.event_type, event.country, event.currency, ip_hash,
                    event.referrer or str(request.headers.get("referer", "")),
                    event.ga_client_id, ua)
        except Exception as e:
            logger.error(f"DB insert error: {e}")
    ga_api_secret  = os.getenv("GA_API_SECRET", "")
    ga_measurement = os.getenv("GA_MEASUREMENT_ID", "")
    if ga_api_secret and ga_measurement and event.ga_client_id:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                await client.post(
                    f"https://www.google-analytics.com/mp/collect"
                    f"?measurement_id={ga_measurement}&api_secret={ga_api_secret}",
                    json={"client_id": event.ga_client_id, "events": [{
                        "name": f"donation_{event.event_type}",
                        "params": {"country": event.country or "", "currency": event.currency or ""},
                    }]},
                )
        except Exception as e:
            logger.warning(f"GA4 MP error: {e}")
    return {"status": "ok"}

@app.get("/api/donation-stats")
async def donation_stats(
    x_admin_key: str = Header(default=""),
    db: asyncpg.Pool = Depends(get_db),
):
    if not ADMIN_KEY or x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    if not db:
        return {"error": "Base de datos no disponible"}
    async with db.acquire() as conn:
        total       = await conn.fetchval("SELECT COUNT(*) FROM donation_events")
        by_event    = await conn.fetch("SELECT event_type, COUNT(*) as n FROM donation_events GROUP BY event_type ORDER BY n DESC")
        by_country  = await conn.fetch("SELECT country, COUNT(*) as n FROM donation_events WHERE country IS NOT NULL GROUP BY country ORDER BY n DESC")
        by_currency = await conn.fetch("SELECT currency, COUNT(*) as n FROM donation_events WHERE currency IS NOT NULL GROUP BY currency ORDER BY n DESC")
        daily       = await conn.fetch("SELECT DATE(created_at AT TIME ZONE 'America/Argentina/Buenos_Aires') as day, COUNT(*) as n FROM donation_events GROUP BY day ORDER BY day DESC LIMIT 30")
    return {
        "total_events": total,
        "by_event_type": [dict(r) for r in by_event],
        "by_country": [dict(r) for r in by_country],
        "by_currency": [dict(r) for r in by_currency],
        "daily_last_30": [{"day": str(r["day"]), "n": r["n"]} for r in daily],
    }

# ── Healthcheck ──────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "db": db_pool is not None, "ts": datetime.now(timezone.utc).isoformat()}

# ── Admin Dashboard ──────────────────────────────────────────────────────────
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, key: str = ""):
    if not ADMIN_KEY or key != ADMIN_KEY:
        return templates.TemplateResponse("admin.html", {
            "request": request,
            "autenticado": False,
            "stats": None,
        })
    stats = None
    if db_pool:
        async with db_pool.acquire() as conn:
            total       = await conn.fetchval("SELECT COUNT(*) FROM donation_events")
            by_event    = await conn.fetch("SELECT event_type, COUNT(*) as n FROM donation_events GROUP BY event_type ORDER BY n DESC")
            by_country  = await conn.fetch("SELECT country, COUNT(*) as n FROM donation_events WHERE country IS NOT NULL GROUP BY country ORDER BY n DESC")
            by_currency = await conn.fetch("SELECT currency, COUNT(*) as n FROM donation_events WHERE currency IS NOT NULL GROUP BY currency ORDER BY n DESC")
            daily       = await conn.fetch("SELECT DATE(created_at AT TIME ZONE 'America/Argentina/Buenos_Aires') as day, COUNT(*) as n FROM donation_events GROUP BY day ORDER BY day DESC LIMIT 30")
            recientes   = await conn.fetch("SELECT event_type, country, currency, created_at FROM donation_events ORDER BY created_at DESC LIMIT 20")
        stats = {
            "total": total,
            "by_event": [dict(r) for r in by_event],
            "by_country": [dict(r) for r in by_country],
            "by_currency": [dict(r) for r in by_currency],
            "daily": [{"day": str(r["day"]), "n": r["n"]} for r in daily],
            "recientes": [{"event_type": r["event_type"], "country": r["country"] or "-", "currency": r["currency"] or "-", "created_at": r["created_at"].strftime("%d/%m %H:%M")} for r in recientes],
        }
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "autenticado": True,
        "stats": stats,
        "admin_key": key,
    })
