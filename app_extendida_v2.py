"""
app_extendida_v2.py
===================
La app de app_extendida.py (main.py + extensiones), más la falla rápida del
análisis en vivo y de la IA, y GET /api/diagnostico. Ver REFORMAS_2026-10-30.md.

Desde el 03/11/2026 también suma la carga del dataset publicado en GitHub
(extensiones/dataset.py) y el marco normativo (extensiones/marco_normativo.py).
Ver REFORMAS_2026-11-03.md.

    uvicorn app_extendida_v2:app --host 0.0.0.0 --port $PORT

No modifica main.py ni app_extendida.py. Para volver atrás basta con arrancar
`app_extendida:app` (lo que arranca el Dockerfile).
"""
from app_extendida import app
from extensiones.dataset import router as router_dataset
from extensiones.falla_rapida import FallaRapida, router
from extensiones.marco_normativo import router as router_normativa

app.include_router(router)
app.include_router(router_dataset)
app.include_router(router_normativa)
app.add_middleware(FallaRapida)
