"""
Falla rápida del análisis en vivo y de la IA (middleware ASGI + endpoint nuevo).

Se suma a ProteccionEjecuciones sin reemplazarla. Reglas:

  * POST /api/licitaciones/ejecutar → antes de lanzar el hilo de main.py se
    prueba la conexión al BORA con timeout corto. Si no responde, se contesta
    503 en segundos con un mensaje claro, en lugar de dejar al visitante
    ~6,5 minutos mirando el spinner para recibir el mismo error.
    El frontend (templates/licitaciones.html) ya muestra `detail` de cualquier
    respuesta que no sea 202, así que no hay que tocarlo.
  * POST /api/ia/clasificar y /api/ia/explicar-riesgo → si la clave de
    Anthropic está revocada o mal cargada, 503 con el motivo (no se gasta una
    de las consultas diarias del visitante en una llamada que va a fallar).
  * GET /api/licitaciones/estado → si un análisis figura "corriendo" hace más
    de ANALISIS_MAX_MIN minutos (el hilo murió, p. ej. por un reinicio del
    proceso a mitad de camino), se lo marca terminado con error para que el
    frontend deje de girar.

Endpoint nuevo:

  GET /api/diagnostico   BORA alcanzable, clave de IA válida, último reporte,
                         días hábiles sin reporte y estado del análisis en vivo.
"""
import asyncio
import json
import os
from datetime import datetime

from fastapi import APIRouter

from .salud_fuentes import bora_alcanzable, clave_ia_valida

RUTA_EJECUTAR = "/api/licitaciones/ejecutar"
RUTA_ESTADO = "/api/licitaciones/estado"
RUTAS_IA = ("/api/ia/clasificar", "/api/ia/explicar-riesgo")
ANALISIS_MAX_MIN = int(os.getenv("ANALISIS_MAX_MIN", "15"))
VERSION_FALLA_RAPIDA = "1.0.0"

MENSAJE_BORA = (
    "El servidor no logra conectarse al Boletín Oficial en este momento: desde el "
    "22/10/2026 el BORA no responde a servidores ubicados fuera de Argentina. Los "
    "reportes diarios se generan desde un equipo en Argentina y se publican acá; "
    "podés consultar los días ya cargados en el selector de fecha."
)

router = APIRouter()


def _main():
    import main
    return main


def liberar_analisis_colgado(ahora: datetime = None) -> bool:
    """Marca como terminado con error un análisis 'corriendo' hace demasiado. True si lo liberó."""
    m = _main()
    ahora = ahora or datetime.now()
    with m._analisis_lock:
        job = m._analisis_job
        if not job.get("corriendo") or not job.get("iniciado_en"):
            return False
        try:
            inicio = datetime.fromisoformat(job["iniciado_en"])
        except ValueError:
            return False
        if (ahora - inicio).total_seconds() < ANALISIS_MAX_MIN * 60:
            return False
        job.update({"corriendo": False, "resultado": None,
                    "error": (f"El análisis iniciado a las {inicio:%H:%M} no terminó en "
                              f"{ANALISIS_MAX_MIN} minutos y se dio por cancelado. Probá de nuevo.")})
        return True


async def evaluar(metodo: str, ruta: str) -> tuple:
    """(status, cuerpo) para cortar la request, o (None, None) para dejarla pasar."""
    if metodo == "GET" and ruta == RUTA_ESTADO:
        liberar_analisis_colgado()
        return None, None
    if metodo != "POST":
        return None, None
    if ruta == RUTA_EJECUTAR:
        if _main()._analisis_job.get("corriendo"):
            return None, None  # main.py responde 409 "ya hay un análisis en curso"
        bora = await asyncio.to_thread(bora_alcanzable)
        if not bora["alcanzable"]:
            return 503, {"status": "bora_inaccesible", "detail": MENSAJE_BORA, "bora": bora}
    elif ruta in RUTAS_IA:
        ia = await asyncio.to_thread(clave_ia_valida)
        if not ia["valida"]:
            # misma forma que agentic_ai ({disponible, motivo}): el frontend la muestra tal cual
            return 503, {"disponible": False, "motivo": ia["motivo"], "detail": ia["motivo"], "ia": ia}
    return None, None


class FallaRapida:
    """Middleware ASGI puro: no altera las requests que deja pasar."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            status, cuerpo = await evaluar(scope["method"], scope["path"])
            if status:
                datos = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
                await send({"type": "http.response.start", "status": status,
                            "headers": [(b"content-type", b"application/json; charset=utf-8"),
                                        (b"content-length", str(len(datos)).encode())]})
                await send({"type": "http.response.body", "body": datos})
                return
        await self.app(scope, receive, send)


@router.get("/api/diagnostico")
async def diagnostico(forzar: bool = False):
    from .rutas import _dias_habiles_sin_reporte
    m = _main()
    bora, ia = await asyncio.gather(asyncio.to_thread(bora_alcanzable, forzar),
                                    asyncio.to_thread(clave_ia_valida, forzar))
    archivos = m.buscar_todos_los_xlsx(m.DATA_DIR)
    with m._analisis_lock:
        job = {k: v for k, v in m._analisis_job.items() if k != "terminado_en"}
    return {
        "version_falla_rapida": VERSION_FALLA_RAPIDA,
        "bora": bora,
        "ia": ia,
        "ultimo_reporte": m.etiqueta_archivo(archivos[0]) if archivos else None,
        "dias_habiles_sin_reporte_30d": _dias_habiles_sin_reporte(30),
        "analisis_en_vivo": job,
    }
