"""
Fecha y hora de Argentina.

El servidor de Railway y los runners de GitHub Actions corren en UTC: entre las
21:00 y las 24:00 de Argentina, datetime.now() ya devuelve el día siguiente.
Las extensiones usan estas funciones para saber qué día es "hoy" en Argentina.
"""
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    TZ_AR = ZoneInfo("America/Argentina/Buenos_Aires")
except Exception:
    # Windows sin el paquete tzdata, o imagen sin base de zonas horarias.
    # Argentina usa UTC-3 fijo, sin horario de verano, desde 2009.
    TZ_AR = timezone(timedelta(hours=-3), "ART")


def ahora_ar() -> datetime:
    return datetime.now(TZ_AR)


def hoy_ar_str() -> str:
    return ahora_ar().strftime("%Y-%m-%d")
