"""
Carga del dataset publicado, en lugar del scraping en vivo (revisión del 03/11/2026).

Desde el 22/10/2026 el BORA no responde a servidores fuera de Argentina, así que
el servidor ya no puede generar reportes. Los genera una PC en Argentina
(tools/actualizar_desde_pc.py) y los publica en la rama `desarrollo` de GitHub.
Este módulo trae esos Excel al disco del servidor sin esperar un redeploy:

  sincronizar_desde_github()  → baja de GitHub los reporte_/flujo_licitaciones_
                                AAAA-MM-DD.xlsx que falten o hayan cambiado
                                (1 consulta a la API + 1 descarga por archivo).
  validar_excel()             → comprueba que un .xlsx subido a mano sea un
                                reporte del monitor antes de guardarlo.

Endpoints:

  POST /api/datos/actualizar                      Trae el dataset de GitHub (público,
                                                  con un mínimo de espera entre corridas)
  GET  /api/datos/estado                          Última sincronización
  POST /api/admin/subir-reporte?fecha=&tipo=      Carga directa de un .xlsx (cuerpo
                                                  binario, requiere la clave)
"""
import hashlib
import io
import os
import re
import threading
import time

import requests
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from .proteccion import _cookies, clave_valida, respaldar_dia
from .zona_horaria import ahora_ar

GITHUB_REPO = os.getenv("DATASET_REPO", "Viny2030/gob_bo_comprar_tgn")
GITHUB_RAMA = os.getenv("DATASET_RAMA", "desarrollo")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")  # opcional: sin token, 60 consultas/hora por IP
SINCRONIZAR_ESPERA_SEG = int(os.getenv("SINCRONIZAR_ESPERA_SEG", "120"))
MAX_BYTES_SUBIDA = 20 * 1024 * 1024
VERSION_DATASET = "1.0.0"

_RUTA_DATASET = re.compile(r"^data/(\d{4}-\d{2})/((?:reporte|flujo_licitaciones)_(\d{4}-\d{2}-\d{2})\.xlsx)$")
HOJAS_REPORTE = ("📰 BORA Licitaciones", "🏆 Adjudicaciones", "🚨 Flujo Completo", "🔗 Flujo Cruzado")
HOJAS_FLUJO = ("⏳ Licitaciones Abiertas", "✅ Adjudicados con CUIT")

router = APIRouter()
_lock = threading.Lock()
_estado = {"corriendo": False, "ultima": None, "_t": 0.0}


def _main():
    import main
    return main


def sha_blob(contenido: bytes) -> str:
    """El sha que git asigna al archivo: permite saber si la copia local ya es la publicada."""
    return hashlib.sha1(b"blob %d\0" % len(contenido) + contenido).hexdigest()


def _headers() -> dict:
    h = {"Accept": "application/vnd.github+json", "User-Agent": "monitor-xai-dataset"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


def listar_publicados(desde: str = None) -> list:
    """[{'ruta', 'mes', 'nombre', 'fecha', 'sha'}] de los Excel diarios en GitHub."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/git/trees/{GITHUB_RAMA}?recursive=1"
    r = requests.get(url, headers=_headers(), timeout=20)
    if r.status_code == 403 and r.headers.get("x-ratelimit-remaining") == "0":
        raise RuntimeError("GitHub limitó las consultas de este servidor por una hora: "
                           "configurar GITHUB_TOKEN o probar más tarde.")
    r.raise_for_status()
    arbol = r.json()
    publicados = []
    for item in arbol.get("tree", []):
        m = _RUTA_DATASET.match(item.get("path", ""))
        if item.get("type") != "blob" or not m:
            continue
        mes, nombre, fecha = m.groups()
        if desde and fecha < desde:
            continue
        publicados.append({"ruta": item["path"], "mes": mes, "nombre": nombre,
                           "fecha": fecha, "sha": item["sha"]})
    return sorted(publicados, key=lambda p: p["ruta"])


def _descargar(ruta: str) -> bytes:
    url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_RAMA}/{ruta}"
    r = requests.get(url, headers={"User-Agent": "monitor-xai-dataset"}, timeout=60)
    r.raise_for_status()
    return r.content


def _escribir(destino: str, contenido: bytes):
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    temporal = destino + ".tmp"
    with open(temporal, "wb") as f:
        f.write(contenido)
    os.replace(temporal, destino)  # quien lea el archivo nunca ve uno a medio escribir


def sincronizar_desde_github(data_dir: str, desde: str = None) -> dict:
    """Baja los Excel que falten o difieran de los publicados. No borra nada local."""
    nuevos, actualizados, errores = [], [], []
    publicados = listar_publicados(desde)
    for p in publicados:
        destino = os.path.join(data_dir, p["mes"], p["nombre"])
        if os.path.exists(destino):
            with open(destino, "rb") as f:
                if sha_blob(f.read()) == p["sha"]:
                    continue
            existia = True
        else:
            existia = False
        try:
            contenido = _descargar(p["ruta"])
            if sha_blob(contenido) != p["sha"]:
                raise ValueError("el archivo bajado no coincide con el publicado")
            if existia:
                respaldar_dia(p["fecha"])
            _escribir(destino, contenido)
            (actualizados if existia else nuevos).append(p["nombre"])
        except Exception as e:
            errores.append({"archivo": p["nombre"], "error": str(e)[:200]})
    fechas = sorted({p["fecha"] for p in publicados})
    return {"publicados": len(publicados), "nuevos": nuevos, "actualizados": actualizados,
            "errores": errores, "ultimo_dia_publicado": fechas[-1] if fechas else None}


def validar_excel(contenido: bytes, tipo: str) -> list:
    """Hojas del Excel si es un reporte del monitor del `tipo` pedido; si no, ValueError."""
    if not contenido:
        raise ValueError("El archivo está vacío.")
    if len(contenido) > MAX_BYTES_SUBIDA:
        raise ValueError("El archivo supera los 20 MB.")
    if not contenido.startswith(b"PK"):
        raise ValueError("No es un archivo .xlsx.")
    from openpyxl import load_workbook
    try:
        hojas = load_workbook(io.BytesIO(contenido), read_only=True).sheetnames
    except Exception:
        raise ValueError("No se pudo abrir el archivo como Excel.")
    esperadas = HOJAS_REPORTE if tipo == "reporte" else HOJAS_FLUJO
    if not any(h in hojas for h in esperadas):
        raise ValueError(f"No tiene ninguna de las hojas de un {tipo} del monitor "
                         f"({', '.join(esperadas)}).")
    return hojas


def _resumen_dia(fecha: str) -> dict:
    """Cantidades del reporte de un día, para mostrarlas después de actualizar."""
    import pandas as pd
    ruta = os.path.join(_main().DATA_DIR, fecha[:7], f"reporte_{fecha}.xlsx")
    if not os.path.exists(ruta):
        return {}
    # Se abre una sola vez y se cierra al terminar (main.leer_hoja deja el archivo
    # abierto, y en Windows eso impide reemplazarlo enseguida).
    with pd.ExcelFile(ruta) as xl:
        def hoja(*nombres):
            nombre = next((n for n in nombres if n in xl.sheet_names), None)
            return pd.read_excel(xl, nombre, dtype=str).fillna("").to_dict("records") if nombre else []
        adj = hoja("🏆 Adjudicaciones")
        flujo = hoja("🚨 Flujo Completo", "🔗 Flujo Cruzado")
        return {
            "licitaciones_bora": len(hoja("📰 BORA Licitaciones")),
            "adjudicaciones": len(adj),
            "adjudicaciones_con_cuit": sum(1 for r in adj if r.get("cuit_proveedor")),
            "comprar": len(hoja("🛒 Comprar")),
            "tgn": len(hoja("💰 TGN")),
            "flujo_cruzado": len(flujo),
            "flujo_completo": sum(1 for r in flujo if "FLUJO COMPLETO" in (r.get("alerta") or "")),
        }


@router.post("/api/datos/actualizar")
def actualizar_datos():
    with _lock:
        if _estado["corriendo"]:
            return JSONResponse(status_code=409, content={"detail": "Ya hay una actualización en curso."})
        espera = SINCRONIZAR_ESPERA_SEG - (time.monotonic() - _estado["_t"])
        if _estado["ultima"] and espera > 0:
            ultima = dict(_estado["ultima"])
            ultima["reciente"] = True  # se devuelve la última en vez de volver a consultar GitHub
            return ultima
        _estado["corriendo"] = True
    try:
        m = _main()
        resultado = sincronizar_desde_github(m.DATA_DIR)
        archivos = m.buscar_todos_los_xlsx(m.DATA_DIR)
        ultimo = (os.path.basename(archivos[0]).replace("reporte_", "").replace(".xlsx", "")
                  if archivos else None)
        resultado.update({"status": "ok", "fecha": ultimo, "resumen": _resumen_dia(ultimo) if ultimo else {},
                          "actualizado_en": ahora_ar().isoformat(timespec="seconds")})
        with _lock:
            _estado.update({"ultima": resultado, "_t": time.monotonic()})
        return resultado
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo leer el dataset publicado en GitHub: {e}")
    finally:
        with _lock:
            _estado["corriendo"] = False


@router.get("/api/datos/estado")
def estado_datos():
    with _lock:
        return {"version_dataset": VERSION_DATASET, "repositorio": f"{GITHUB_REPO}@{GITHUB_RAMA}",
                "corriendo": _estado["corriendo"], "ultima": _estado["ultima"]}


@router.post("/api/admin/subir-reporte")
async def subir_reporte(request: Request, fecha: str, tipo: str = "reporte"):
    """Carga directa de un Excel diario: el cuerpo de la request es el .xlsx."""
    headers = {k.lower(): v for k, v in request.headers.items()}
    if not clave_valida(headers, _cookies(headers.get("cookie", ""))):
        raise HTTPException(status_code=403, detail="Requiere la clave de administración")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha or ""):
        raise HTTPException(status_code=400, detail="Formato inválido. Use AAAA-MM-DD")
    if tipo not in ("reporte", "flujo"):
        raise HTTPException(status_code=400, detail="tipo debe ser 'reporte' o 'flujo'")
    contenido = await request.body()
    try:
        hojas = validar_excel(contenido, tipo)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    m = _main()
    nombre = f"{'reporte' if tipo == 'reporte' else 'flujo_licitaciones'}_{fecha}.xlsx"
    destino = os.path.join(m.DATA_DIR, fecha[:7], nombre)
    reemplazado = os.path.exists(destino)
    if reemplazado:
        respaldar_dia(fecha)
    _escribir(destino, contenido)
    return {"status": "ok", "archivo": nombre, "reemplazado": reemplazado, "hojas": hojas,
            "resumen": _resumen_dia(fecha) if tipo == "reporte" else {}}
