"""
app_extendida.py
================
Punto de entrada alternativo: la misma app de main.py, más las extensiones
(protección de ejecuciones, descargas, página /estado, manual corregido).

    uvicorn app_extendida:app --host 0.0.0.0 --port $PORT

main.py no se modifica. Para volver atrás basta con arrancar `main:app`.
"""
from main import app
from extensiones.proteccion import ProteccionEjecuciones
from extensiones.rutas import router

app.include_router(router)
app.add_middleware(ProteccionEjecuciones)
