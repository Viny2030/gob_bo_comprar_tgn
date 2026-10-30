"""
app_extendida_v2.py
===================
La app de app_extendida.py (main.py + extensiones), más la falla rápida del
análisis en vivo y de la IA, y GET /api/diagnostico. Ver REFORMAS_2026-10-30.md.

    uvicorn app_extendida_v2:app --host 0.0.0.0 --port $PORT

No modifica main.py ni app_extendida.py. Para volver atrás basta con arrancar
`app_extendida:app` (lo que arranca el Dockerfile).
"""
from app_extendida import app
from extensiones.falla_rapida import FallaRapida, router

app.include_router(router)
app.add_middleware(FallaRapida)
