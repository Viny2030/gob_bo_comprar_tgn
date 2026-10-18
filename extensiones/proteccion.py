"""
Protección de las ejecuciones manuales (middleware ASGI).

Problema que resuelve: POST /api/licitaciones/ejecutar no pide clave, y para un
día pasado no consulta Comprar ni TGN (solo tienen el estado actual) pero igual
reescribe el Excel. Así, el reporte del 16/10/2026 que había generado el cron
(12 procesos de Comprar, 540 organismos de TGN) quedó en producción con 0 y 0.

Reglas (se aplican antes de llegar a main.py, que no se modifica):

  * POST /api/licitaciones/ejecutar para un día PASADO que YA tiene reporte
    → requiere la clave de administración (header X-Admin-Key o la cookie de
      sesión del panel /admin). Un día pasado SIN reporte se puede completar
      sin clave: no pisa nada.
  * POST /api/analisis → requiere la clave (corre el scraping sin límite de uso
    y deja su resultado fijo en el dashboard hasta el próximo reinicio).
  * Antes de cualquier ejecución que vaya a reescribir un reporte existente,
    se copia el Excel actual a RESPALDOS_DIR (fuera de DATA_DIR, para que el
    sitio no lo liste como un reporte más).
"""
import hashlib
import json
import os
import re
import secrets
import shutil
from datetime import datetime
from urllib.parse import parse_qs

from .zona_horaria import ahora_ar, hoy_ar_str

RUTA_EJECUTAR = "/api/licitaciones/ejecutar"
RUTA_ANALISIS = "/api/analisis"
_FECHA_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def respaldos_dir() -> str:
    defecto = "/app/respaldos" if os.path.exists("/app") else "respaldos"
    return os.getenv("RESPALDOS_DIR", defecto)


def _main():
    import main  # import diferido: main ya está cargado cuando llega una request
    return main


def archivos_del_dia(fecha: str) -> list:
    """Rutas existentes de reporte_ y flujo_licitaciones_ para una fecha."""
    carpeta = os.path.join(_main().DATA_DIR, fecha[:7])
    rutas = [os.path.join(carpeta, f"reporte_{fecha}.xlsx"),
             os.path.join(carpeta, f"flujo_licitaciones_{fecha}.xlsx")]
    return [r for r in rutas if os.path.exists(r)]


def _sha256(ruta: str) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 16), b""):
            h.update(bloque)
    return h.hexdigest()


def respaldar_dia(fecha: str) -> list:
    """
    Copia los Excel existentes del día a RESPALDOS_DIR/AAAA-MM/ con la hora en el
    nombre. Si ya hay un respaldo idéntico (mismo contenido) no lo duplica.
    Devuelve las rutas de los respaldos nuevos.
    """
    nuevos = []
    destino = os.path.join(respaldos_dir(), fecha[:7])
    for ruta in archivos_del_dia(fecha):
        os.makedirs(destino, exist_ok=True)
        base = os.path.basename(ruta)[:-len(".xlsx")]
        huella = _sha256(ruta)
        ya_respaldado = any(
            n.startswith(base + "__") and _sha256(os.path.join(destino, n)) == huella
            for n in os.listdir(destino)
        )
        if ya_respaldado:
            continue
        marca = ahora_ar().strftime("%Y%m%dT%H%M%S")
        copia = os.path.join(destino, f"{base}__{marca}.xlsx")
        shutil.copy2(ruta, copia)
        nuevos.append(copia)
    return nuevos


def clave_valida(headers: dict, cookies: dict) -> bool:
    """X-Admin-Key o la cookie del panel /admin, comparadas en tiempo constante."""
    admin_key = _main().ADMIN_KEY
    if not admin_key:
        return False
    candidatos = [headers.get("x-admin-key", ""), cookies.get(_main().ADMIN_COOKIE, "")]
    return any(c and secrets.compare_digest(c.encode(), admin_key.encode()) for c in candidatos)


def _cookies(raw: str) -> dict:
    out = {}
    for parte in raw.split(";"):
        if "=" in parte:
            k, v = parte.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def evaluar(metodo: str, ruta: str, query: str, headers: dict) -> tuple:
    """
    Decide qué hacer con una request. Devuelve (status, detalle) para cortarla,
    o (None, None) para dejarla pasar. Separado del middleware para testearlo.
    """
    if metodo != "POST":
        return None, None
    cookies = _cookies(headers.get("cookie", ""))

    if ruta == RUTA_ANALISIS:
        if not clave_valida(headers, cookies):
            return 403, ("El análisis programático requiere la clave de administración "
                         "(header X-Admin-Key o sesión iniciada en /admin).")
        return None, None

    if ruta == RUTA_EJECUTAR:
        fecha = (parse_qs(query).get("fecha") or [""])[0]
        if fecha and not _FECHA_RE.match(fecha):
            return None, None  # main.py responde 400 con su propio mensaje
        hoy = hoy_ar_str()
        fecha = fecha or datetime.now().strftime("%Y-%m-%d")  # mismo defecto que main.py
        es_pasado = fecha < hoy
        existe = bool(archivos_del_dia(fecha))
        if es_pasado and existe and not clave_valida(headers, cookies):
            return 403, (f"El día {fecha} ya tiene un reporte guardado. Volver a ejecutarlo "
                         "lo reemplaza por uno sin datos de Comprar ni TGN (esas fuentes solo "
                         "tienen el estado de hoy), así que requiere la clave de administración.")
        if existe:
            respaldar_dia(fecha)
    return None, None


class ProteccionEjecuciones:
    """Middleware ASGI puro: no altera las requests que deja pasar."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = {k.decode("latin-1").lower(): v.decode("latin-1")
                       for k, v in scope.get("headers", [])}
            status, detalle = evaluar(scope["method"], scope["path"],
                                      scope.get("query_string", b"").decode("latin-1"), headers)
            if status:
                cuerpo = json.dumps({"status": "denegado", "detail": detalle},
                                    ensure_ascii=False).encode("utf-8")
                await send({"type": "http.response.start", "status": status,
                            "headers": [(b"content-type", b"application/json; charset=utf-8"),
                                        (b"content-length", str(len(cuerpo)).encode())]})
                await send({"type": "http.response.body", "body": cuerpo})
                return
        await self.app(scope, receive, send)
