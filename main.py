import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# ── PostgreSQL ──────────────────────────────────────────────────────────────
import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL")          # set by Railway Postgres plugin
ADMIN_KEY    = os.getenv("ADMIN_KEY", "")          # set manually in Railway vars

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── App ─────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Monitor de Contratos y Licitaciones Públicas",
    description="Algoritmos contra la Corrupción · Ph.D. Monteverde",
    version="2.0.0",
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ── DB pool ─────────────────────────────────────────────────────────────────
db_pool: Optional[asyncpg.Pool] = None

async def get_db() -> asyncpg.Pool:
    return db_pool

@app.on_event("startup")
async def startup():
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

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()

async def init_db(pool: asyncpg.Pool):
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS donation_events (
                id          SERIAL PRIMARY KEY,
                event_type  TEXT        NOT NULL,   -- 'open_modal' | 'select_country' | 'view_details' | 'confirm'
                country     TEXT,                   -- 'AR' | 'abroad'
                currency    TEXT,                   -- 'ARS' | 'USD' | 'USD_wire'
                ip_hash     TEXT,
                referrer    TEXT,
                ga_client_id TEXT,
                user_agent  TEXT,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_donation_events_created
                ON donation_events(created_at);
            CREATE INDEX IF NOT EXISTS idx_donation_events_type
                ON donation_events(event_type);
        """)

# ── Schemas ──────────────────────────────────────────────────────────────────
class DonationEvent(BaseModel):
    event_type:   str               # open_modal | select_country | view_details | confirm
    country:      Optional[str] = None
    currency:     Optional[str] = None
    ga_client_id: Optional[str] = None
    referrer:     Optional[str] = None

# ── Helper: hash IP para privacidad ─────────────────────────────────────────
import hashlib

def hash_ip(ip: str) -> str:
    return hashlib.sha256(ip.encode()).hexdigest()[:16]

# ── Rutas existentes ─────────────────────────────────────────────────────────
DATA_DIR = Path("data")

def get_latest_report():
    """Retorna (mes, archivo) del reporte más reciente."""
    if not DATA_DIR.exists():
        return None, None
    months = sorted([d for d in DATA_DIR.iterdir() if d.is_dir()], reverse=True)
    for month in months:
        files = sorted(month.glob("reporte_*.xlsx"), reverse=True)
        if files:
            return month.name, files[0]
    return None, None

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    mes, archivo = get_latest_report()
    ga_id = os.getenv("GA_MEASUREMENT_ID", "")
    return templates.TemplateResponse("dashboard.html", {
        "request":      request,
        "ultimo_mes":   mes,
        "ultimo_arch":  archivo.name if archivo else None,
        "ga_id":        ga_id,
    })

@app.get("/documentacion", response_class=HTMLResponse)
async def documentacion(request: Request):
    ga_id = os.getenv("GA_MEASUREMENT_ID", "")
    return templates.TemplateResponse("documentacion.html", {
        "request": request,
        "ga_id": ga_id,
    })

@app.get("/licitaciones", response_class=HTMLResponse)
async def licitaciones(request: Request):
    ga_id = os.getenv("GA_MEASUREMENT_ID", "")
    return templates.TemplateResponse("licitaciones.html", {
        "request": request,
        "ga_id": ga_id,
    })

@app.get("/analisis-vivo", response_class=HTMLResponse)
async def analisis_vivo(request: Request):
    ga_id = os.getenv("GA_MEASUREMENT_ID", "")
    return templates.TemplateResponse("analisis_vivo.html", {
        "request": request,
        "ga_id": ga_id,
    })

# ── API: registrar evento de donación ────────────────────────────────────────
@app.post("/api/donation-event")
async def record_donation_event(
    event: DonationEvent,
    request: Request,
    db: asyncpg.Pool = Depends(get_db),
):
    """
    Recibe eventos del modal de donación y los guarda en PostgreSQL.
    También puede reenviarse a GA4 Measurement Protocol del lado servidor.
    """
    ip_raw  = request.client.host if request.client else "unknown"
    ip_hash = hash_ip(ip_raw)
    ua      = request.headers.get("user-agent", "")[:200]

    if db:
        try:
            async with db.acquire() as conn:
                await conn.execute("""
                    INSERT INTO donation_events
                        (event_type, country, currency, ip_hash, referrer, ga_client_id, user_agent)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                    event.event_type,
                    event.country,
                    event.currency,
                    ip_hash,
                    event.referrer or str(request.headers.get("referer", "")),
                    event.ga_client_id,
                    ua,
                )
        except Exception as e:
            logger.error(f"DB insert error: {e}")

    # ── GA4 Measurement Protocol (server-side) ───────────────────────────────
    ga_api_secret  = os.getenv("GA_API_SECRET", "")
    ga_measurement = os.getenv("GA_MEASUREMENT_ID", "")
    if ga_api_secret and ga_measurement and event.ga_client_id:
        payload = {
            "client_id": event.ga_client_id,
            "events": [{
                "name": f"donation_{event.event_type}",
                "params": {
                    "country":  event.country or "",
                    "currency": event.currency or "",
                },
            }],
        }
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                await client.post(
                    f"https://www.google-analytics.com/mp/collect"
                    f"?measurement_id={ga_measurement}&api_secret={ga_api_secret}",
                    json=payload,
                )
        except Exception as e:
            logger.warning(f"GA4 MP error: {e}")

    return {"status": "ok"}

# ── API: estadísticas de donaciones (protegido por ADMIN_KEY) ────────────────
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
        total = await conn.fetchval("SELECT COUNT(*) FROM donation_events")
        by_event = await conn.fetch("""
            SELECT event_type, COUNT(*) as n
            FROM donation_events GROUP BY event_type ORDER BY n DESC
        """)
        by_country = await conn.fetch("""
            SELECT country, COUNT(*) as n
            FROM donation_events WHERE country IS NOT NULL
            GROUP BY country ORDER BY n DESC
        """)
        by_currency = await conn.fetch("""
            SELECT currency, COUNT(*) as n
            FROM donation_events WHERE currency IS NOT NULL
            GROUP BY currency ORDER BY n DESC
        """)
        daily = await conn.fetch("""
            SELECT DATE(created_at AT TIME ZONE 'America/Argentina/Buenos_Aires') as day,
                   COUNT(*) as n
            FROM donation_events
            GROUP BY day ORDER BY day DESC LIMIT 30
        """)

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
    db_ok = db_pool is not None
    return {"status": "ok", "db": db_ok, "ts": datetime.now(timezone.utc).isoformat()}
