# Mejoras de la revisión de octubre de 2026

Hubo dos tandas:

1. **Extensiones** (PR #11): solo archivos nuevos, sin tocar los existentes.
2. **Correcciones** (rama `mejoras-navegacion-y-correcciones`): menú, `main.py`,
   Documentación, README, Dockerfile, cron y dependencias. Detalle al final.

## Cómo está activado

El `Dockerfile` arranca `app_extendida:app` (la app de `main.py` más las
extensiones), así que no hace falta un comando de inicio personalizado en
Railway: si se configuró uno, se puede borrar. Hay que tener `ADMIN_KEY`
definida en las variables del servicio.

Si en Railway se usa un comando personalizado, tiene que pasar por `sh -c`
para que `$PORT` se expanda (si no, uvicorn recibe el texto `$PORT` y el
contenedor no arranca):

```
sh -c "uvicorn app_extendida:app --host 0.0.0.0 --port ${PORT:-8000}"
```

Localmente:

```
uvicorn app_extendida:app --reload
```

## Qué se agregó

| Problema encontrado | Qué se agregó | Archivo |
|---|---|---|
| Re-ejecutar un día pasado pisaba el reporte del cron con uno sin Comprar ni TGN (pasó con el 16/10/2026 en producción) | Un día pasado **que ya tiene reporte** requiere la clave (`X-Admin-Key` o sesión de `/admin`). Un día sin reporte se completa sin clave. Antes de reescribir cualquier reporte se guarda un respaldo en `RESPALDOS_DIR` (fuera de `data/`) | `extensiones/proteccion.py` |
| `POST /api/analisis` sin clave ni límite, y su resultado quedaba fijo en el dashboard | Requiere la clave | `extensiones/proteccion.py` |
| El manual promete descargar el último reporte, pero no hay endpoint | `GET /api/reporte/AAAA-MM-DD/excel` (`?tipo=flujo`) | `extensiones/rutas.py` |
| No hay forma de ver si el cron corrió ni qué fuentes trajeron datos | Página `/estado` y `GET /api/estado-sistema`: último reporte, filas por fuente, días hábiles faltantes, base, IA, protección | `extensiones/rutas.py`, `templates/estado.html` |
| El visitante no sabe cuántas consultas de IA le quedan | `GET /api/ia/usos` | `extensiones/rutas.py` |
| PostgreSQL casi no recibe reportes (el cron no tiene `DATABASE_URL`; la corrida en vivo usa el pool desde otro event loop) | `POST /api/admin/sincronizar-db?fecha=` o `?desde=` (con clave) y `tools/backfill_db.py` para el histórico | `extensiones/sincronizacion.py`, `tools/backfill_db.py` |
| El histórico mezcla versiones de la matriz | `tools/recalcular_historico.py`: recalcula todo en `recalculado/` y deja un `resumen.csv` | `tools/recalcular_historico.py` |
| La matriz nunca puede llegar a 10 (Multi-Organismo no se activa) y la de 7 escenarios da falsos positivos ("iva" en "ejecutiva") | Versión revisada, en paralelo, para comparar | `analisis_v2.py` |
| Hora del servidor en UTC (a las 22:00 de Argentina ya es "mañana") | Funciones de fecha de Argentina, usadas por las extensiones | `extensiones/zona_horaria.py` |
| El manual web y los .docx dicen cosas distintas, y ninguno coincide con el código | Manual corregido ES/EN en Markdown, con un generador que produce la web (`/manual-v2`) y los dos .docx | `docs/manual/*.md`, `tools/generar_manual.py` |
| CI no corre `test_apis_oficiales.py`, usa Python 3.11 y no instala `requirements.txt` | Workflow nuevo con todos los tests, Python 3.13 (igual que Docker) y control de que el manual generado esté al día | `.github/workflows/tests_extendidos.yml`, `requirements-dev.txt` |

Tests nuevos: `test_extensiones.py` (16) y `test_analisis_v2.py` (8).

## Resultados del recálculo del histórico

`python tools/recalcular_historico.py` sobre los 169 días de `data/` (770 adjudicaciones):

| Matriz | Alto | Medio | Bajo | Índice promedio |
|---|---|---|---|---|
| Como está guardado | 0 | 88 | 682 | 1,65 |
| Matriz actual (`analisis.py`) | 0 | 88 | 682 | 0,39 |
| Revisada (`analisis_v2.py`) | 0 | 88 | 682 | 0,47 |

- 742 de las 770 filas guardadas tienen el indicador retirado "Adjudicación mismo día de publicación". Los **niveles** no cambian, pero el **índice promedio** guardado está inflado unas 4 veces: cualquier gráfico del índice a lo largo del tiempo compara metodologías distintas.
- Ninguna adjudicación llegó a Alto en ocho meses, ni siquiera con la versión revisada: hace falta que coincidan tres indicadores. Calibrar los umbrales es una decisión metodológica que corresponde al autor de la matriz; `analisis_v2.py` solo corrige el divisor.

## Avisos antes de activar

1. **Dashboard y base de datos.** Desde la segunda tanda, el dashboard muestra siempre el último reporte en disco, así que cargar el histórico en la base (`backfill_db.py` o `sincronizar-db`) no cambia lo que se ve. Antes de esa corrección, la base tenía prioridad y el dashboard pasaba a mostrar totales acumulados.
2. **Sin `ADMIN_KEY` nadie puede reescribir un día pasado** con las extensiones activas. Un día sin reporte sí se puede completar.
3. **Reporte del 16/10/2026 en producción.** El archivo del repositorio está bien (12 procesos de Comprar, 540 organismos de TGN); el del contenedor quedó reemplazado. Se recupera solo con el próximo despliegue, que vuelve a copiar `data/` desde git.
4. **Respaldos en Railway.** `RESPALDOS_DIR` (por defecto `/app/respaldos`) vive en el disco del contenedor y se pierde al redesplegar. Para conservarlos, montar un volumen y apuntar `RESPALDOS_DIR` ahí.

## Segunda tanda: correcciones en archivos existentes

| Qué | Dónde |
|---|---|
| Menú igual en todas las páginas: se agregó **Estado**, el Dashboard ahora tiene **Licitaciones**, y cada página marca un solo enlace activo | `templates/*.html` |
| `/manual` muestra el manual corregido; el anterior queda en `/manual-anterior`. Las descargas `.docx` del manual entregan la versión corregida | `main.py` |
| "Hoy" es el día de Argentina (antes, a partir de las 21:00 ya era el día siguiente): análisis en vivo, consulta de Comprar/TGN y calendario de días | `main.py` |
| El resultado de `POST /api/analisis` ya no queda fijo en el dashboard: se descarta cuando aparece un reporte más nuevo | `main.py` |
| El dashboard muestra siempre el último reporte (la base solo se usa si no hay ninguno), y la tabla ya no muestra "nan" | `main.py` |
| El análisis en vivo guarda en PostgreSQL con un pool propio: antes reusaba el de la app desde otro event loop y fallaba | `main.py` |
| Rangos de riesgo de Documentación alineados con el código (Alto ≥ 7, Medio ≥ 4) | `templates/documentacion.html` |
| El contenedor arranca con las extensiones | `Dockerfile`, `docker-compose.yml` |
| El cron instala `requirements.txt` completo (vuelve a funcionar el chequeo de feriados) y usa Python 3.13 | `.github/workflows/ejecucion_diaria.yml` |
| `nest_asyncio` agregado (lo usa `db_reportes.py`) | `requirements.txt`, `requirements.in` |
| Modelo de IA por defecto: `claude-sonnet-5-5` (se puede cambiar con `ANTHROPIC_MODEL`) | `agentic_ai.py` |
| README al día: pesos, matriz licitatoria, login de admin, estructura, endpoints | `Readme.md` |

## Pendiente

- Fijar versiones exactas de dependencias (`pip-compile requirements.in`), para que un deploy no cambie de versión sin aviso.
- Si se quiere que el cron también cargue la base: agregar el secret `DATABASE_URL` en GitHub y pasarlo al paso "Ejecutar Ciclo Integrado".
- Decidir si se adoptan las matrices de `analisis_v2.py` y si se recalibran los umbrales (decisión metodológica del autor).
