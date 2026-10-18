"""
Endpoints nuevos. Ninguno reemplaza a uno existente: todas las rutas son nuevas.

  GET  /api/reporte/{fecha}/excel?tipo=reporte|flujo  Descarga el Excel de un día
  GET  /api/estado-sistema                           Estado del sistema (JSON)
  GET  /estado                                       Estado del sistema (página)
  GET  /api/ia/usos                                  Consultas de IA que le quedan hoy al visitante
  POST /api/admin/sincronizar-db?fecha=AAAA-MM-DD     Carga Excel en PostgreSQL (requiere clave)
  GET  /manual-v2                                    Manual corregido ES/EN
  GET  /api/descargar-manual-v2-es | -en             Manual corregido en .docx
"""
import os
from datetime import datetime, timedelta, timezone

import pandas as pd
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

from .proteccion import _cookies, archivos_del_dia, clave_valida, respaldos_dir
from .zona_horaria import ahora_ar, hoy_ar_str

router = APIRouter()
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
VERSION_EXTENSIONES = "1.1.0"


def _main():
    import main
    return main


def _validar_fecha(fecha: str) -> str:
    try:
        datetime.strptime(fecha, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato inválido. Use AAAA-MM-DD")
    return fecha


# ── Descarga de reportes ─────────────────────────────────────────────────────
@router.get("/api/reporte/{fecha}/excel")
def descargar_reporte(fecha: str, tipo: str = "reporte"):
    """Descarga el Excel de un día. tipo=reporte (todas las hojas) o tipo=flujo."""
    _validar_fecha(fecha)
    if tipo not in ("reporte", "flujo"):
        raise HTTPException(status_code=400, detail="tipo debe ser 'reporte' o 'flujo'")
    prefijo = "reporte" if tipo == "reporte" else "flujo_licitaciones"
    nombre = f"{prefijo}_{fecha}.xlsx"
    ruta = os.path.join(_main().DATA_DIR, fecha[:7], nombre)
    if not os.path.exists(ruta):
        raise HTTPException(status_code=404, detail=f"No hay {tipo} para el {fecha}")
    return FileResponse(path=ruta, filename=nombre, media_type=XLSX)


# ── Estado del sistema ───────────────────────────────────────────────────────
def _dias_habiles_sin_reporte(dias: int = 30) -> list:
    try:
        import holidays
        feriados = holidays.Argentina(years=range(ahora_ar().year - 1, ahora_ar().year + 1))
    except Exception:
        feriados = {}
    faltan = []
    hoy = ahora_ar().date()
    for i in range(1, dias + 1):
        d = hoy - timedelta(days=i)
        if d.weekday() >= 5 or d in feriados:
            continue
        if not archivos_del_dia(d.strftime("%Y-%m-%d")):
            faltan.append(d.strftime("%Y-%m-%d"))
    return faltan


def _fuentes_del_reporte(ruta: str) -> dict:
    """Filas por hoja del Excel: muestra qué fuentes trajeron datos ese día."""
    try:
        xl = pd.ExcelFile(ruta)
        return {h: int(len(xl.parse(h))) for h in xl.sheet_names}
    except Exception as e:
        return {"error": str(e)}


def estado_sistema(request: Request) -> dict:
    m = _main()
    archivos = m.buscar_todos_los_xlsx(m.DATA_DIR)
    ultimo = None
    if archivos:
        fecha = os.path.basename(archivos[0]).replace("reporte_", "").replace(".xlsx", "")
        ultimo = {"fecha": fecha, "archivo": m.etiqueta_archivo(archivos[0]),
                  "hojas": _fuentes_del_reporte(archivos[0]),
                  "descarga": f"/api/reporte/{fecha}/excel"}
    with m._analisis_lock:
        job = dict(m._analisis_job)
    terminado = job.pop("terminado_en", None)
    job["terminado_en"] = terminado.isoformat() if terminado else None
    try:
        from agentic_ai import ia_disponible, MODEL
        ia = {"disponible": ia_disponible(), "modelo": MODEL, "limite_por_dia": m.IA_LIMITE_POR_IP}
    except Exception as e:
        ia = {"disponible": False, "error": str(e)}
    n_respaldos = 0
    if os.path.isdir(respaldos_dir()):
        n_respaldos = sum(len(f) for _, _, f in os.walk(respaldos_dir()))
    return {
        "hora_argentina": ahora_ar().isoformat(timespec="seconds"),
        "hoy_argentina": hoy_ar_str(),
        "version_app": m.app.version,
        "version_extensiones": VERSION_EXTENSIONES,
        "reportes_en_disco": len(archivos),
        "ultimo_reporte": ultimo,
        "dias_habiles_sin_reporte_30d": _dias_habiles_sin_reporte(30),
        "analisis_en_vivo": job,
        "base_de_datos": m.db_pool is not None,
        "ia": ia,
        "respaldos_guardados": n_respaldos,
        "proteccion_ejecuciones": bool(m.ADMIN_KEY),
    }


@router.get("/api/estado-sistema")
def api_estado_sistema(request: Request):
    return estado_sistema(request)


@router.get("/estado", response_class=HTMLResponse)
def pagina_estado(request: Request):
    return _main().templates.TemplateResponse(request, "estado.html", {"e": estado_sistema(request)})


# ── IA: usos restantes ───────────────────────────────────────────────────────
@router.get("/api/ia/usos")
def ia_usos(request: Request):
    m = _main()
    ip = m.hash_ip(m._ip_cliente(request))
    hoy = datetime.now(timezone.utc).date()  # mismo criterio de reinicio que main.py
    with m._ia_lock:
        usados = m._ia_usos["por_ip"].get(ip, 0) if m._ia_usos["dia"] == hoy else 0
        total = m._ia_usos["total"] if m._ia_usos["dia"] == hoy else 0
    return {"usados_hoy": usados, "restantes_hoy": max(m.IA_LIMITE_POR_IP - usados, 0),
            "limite_por_dia": m.IA_LIMITE_POR_IP,
            "cupo_global_restante": max(m.IA_LIMITE_GLOBAL - total, 0)}


# ── Sincronizar Excel → PostgreSQL ───────────────────────────────────────────
@router.post("/api/admin/sincronizar-db")
async def sincronizar_db(request: Request, fecha: str = None, desde: str = None):
    """
    Carga en PostgreSQL el Excel de `fecha`, o todos desde `desde` (inclusive).
    Usa el pool de la app dentro de su propio event loop. Requiere la clave.
    """
    headers = {k.lower(): v for k, v in request.headers.items()}
    if not clave_valida(headers, _cookies(headers.get("cookie", ""))):
        raise HTTPException(status_code=403, detail="Requiere la clave de administración")
    m = _main()
    if not m.db_pool:
        raise HTTPException(status_code=503, detail="PostgreSQL no disponible")
    from .sincronizacion import cargar_dia, fechas_disponibles
    if fecha:
        fechas = [_validar_fecha(fecha)]
    else:
        fechas = [f for f in fechas_disponibles(m.DATA_DIR) if not desde or f >= _validar_fecha(desde)]
    resultados = [await cargar_dia(m.db_pool, m.DATA_DIR, f) for f in fechas]
    return {"dias": len(resultados), "cargados": sum(1 for r in resultados if r.get("cargado")),
            "resultados": resultados}


# ── Manual corregido ─────────────────────────────────────────────────────────
@router.get("/manual-v2", response_class=HTMLResponse)
def manual_v2(request: Request):
    return _main().templates.TemplateResponse(request, "manual_v2.html")


def _docx(ruta: str, detalle: str):
    if not os.path.exists(ruta):
        raise HTTPException(status_code=404, detail=detalle)
    return FileResponse(path=ruta, filename=os.path.basename(ruta), media_type=DOCX)


@router.get("/api/descargar-manual-v2-es")
def descargar_manual_v2_es():
    return _docx("Monitor_XAI_Manual_ES_v2.docx", "Manual en español no disponible")


@router.get("/api/descargar-manual-v2-en")
def descargar_manual_v2_en():
    return _docx("Monitor_XAI_Manual_EN_v2.docx", "Manual not available")
