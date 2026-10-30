"""
Chequeos rápidos de las dependencias externas (sin modificar main.py ni diario.py).

Problemas que resuelve (revisión del 30/10/2026):

  * Desde el 22/10/2026 el BORA no responde a las IP de centros de datos
    (GitHub Actions y Railway): la conexión TCP queda sin respuesta hasta el
    timeout. diario.get_con_reintentos espera 3 × 60 s + 2 × 15 s antes de
    rendirse, así que el "análisis en vivo" quedaba ~6,5 minutos girando para
    terminar en "El BORA no tiene avisos ... (sitio caído)". El mismo BORA
    responde en 1-3 s desde una conexión de Argentina.
  * La ANTHROPIC_API_KEY fue revocada el 21/10/2026. /api/ia/status solo mira si
    la variable existe, así que con la clave vieja seguía diciendo "disponible".

Este módulo ofrece dos chequeos con caché, para usar antes de lanzar trabajo largo:

  bora_alcanzable()  → conexión con timeout corto (por defecto 8 s) al BORA
  clave_ia_valida()  → models.retrieve(): valida la clave sin consumir tokens
"""
import os
import threading
import time

import requests

from .zona_horaria import ahora_ar

BORA_URL_PRUEBA = os.getenv("BORA_URL_PRUEBA", "https://www.boletinoficial.gob.ar/")
BORA_TIMEOUT_SEG = float(os.getenv("BORA_TIMEOUT_SEG", "8"))
CACHE_BORA_SEG = int(os.getenv("CACHE_BORA_SEG", "300"))
CACHE_IA_SEG = int(os.getenv("CACHE_IA_SEG", "900"))

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "es-AR,es;q=0.9",
}

_lock = threading.Lock()
_cache = {"bora": None, "ia": None}


def _cacheado(clave: str, vigencia: int, calcular):
    with _lock:
        previo = _cache[clave]
        if previo and time.monotonic() - previo["_t"] < vigencia:
            return {k: v for k, v in previo.items() if k != "_t"}
    nuevo = calcular()
    nuevo["verificado_en"] = ahora_ar().isoformat(timespec="seconds")
    with _lock:
        _cache[clave] = dict(nuevo, _t=time.monotonic())
    return nuevo


def _probar_bora() -> dict:
    t0 = time.monotonic()
    try:
        r = requests.get(BORA_URL_PRUEBA, headers=_HEADERS, verify=False,
                         timeout=(BORA_TIMEOUT_SEG, BORA_TIMEOUT_SEG * 2))
        return {"alcanzable": r.status_code < 500, "http": r.status_code,
                "segundos": round(time.monotonic() - t0, 2)}
    except Exception as e:
        return {"alcanzable": False, "http": None, "segundos": round(time.monotonic() - t0, 2),
                "error": type(e).__name__}


def bora_alcanzable(forzar: bool = False) -> dict:
    """{'alcanzable': bool, 'http', 'segundos', 'verificado_en'[, 'error']}"""
    if forzar:
        with _lock:
            _cache["bora"] = None
    return _cacheado("bora", CACHE_BORA_SEG, _probar_bora)


def _probar_ia() -> dict:
    import agentic_ai
    if not agentic_ai.ia_disponible():
        return {"valida": False, "motivo": "ANTHROPIC_API_KEY no configurada o paquete 'anthropic' no instalado",
                "modelo": agentic_ai.MODEL}
    import anthropic
    try:
        # Consulta de metadatos del modelo: autentica la clave y confirma el model id,
        # sin generar texto (no consume tokens).
        agentic_ai._client.with_options(timeout=10.0, max_retries=0).models.retrieve(agentic_ai.MODEL)
        return {"valida": True, "modelo": agentic_ai.MODEL}
    except anthropic.AuthenticationError:
        motivo = "La clave fue rechazada (401): está revocada o es incorrecta. Cargar una nueva en ANTHROPIC_API_KEY."
    except anthropic.PermissionDeniedError:
        motivo = "La clave no tiene permiso para este modelo (403)."
    except anthropic.NotFoundError:
        motivo = f"El modelo '{agentic_ai.MODEL}' no existe para esta clave (404): revisar ANTHROPIC_MODEL."
    except anthropic.APIConnectionError:
        motivo = "No se pudo conectar con la API de Anthropic."
    except anthropic.APIStatusError as e:
        motivo = f"Error de la API ({e.status_code})."
    return {"valida": False, "motivo": motivo, "modelo": agentic_ai.MODEL}


def clave_ia_valida(forzar: bool = False) -> dict:
    """{'valida': bool, 'modelo', 'verificado_en'[, 'motivo']}"""
    if forzar:
        with _lock:
            _cache["ia"] = None
    return _cacheado("ia", CACHE_IA_SEG, _probar_ia)
