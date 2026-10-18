# Mejoras de la revisión de octubre de 2026

Todo lo de esta rama se **suma** al proyecto: no se modificó ningún archivo
existente (`main.py`, `diario.py`, `analisis.py`, `db_reportes.py`, templates,
workflows, manuales anteriores ni `data/`). Si no se activa nada, el sitio
funciona exactamente igual que antes.

## Cómo activarlo

Las extensiones viven en `app_extendida.py`, que importa la app de `main.py` y
le agrega rutas y un middleware. Para usarlas en Railway, cambiar el comando de
inicio del servicio (Settings → Deploy → Custom Start Command):

```
uvicorn app_extendida:app --host 0.0.0.0 --port $PORT
```

y definir `ADMIN_KEY` si todavía no está. Para volver atrás, borrar el comando
personalizado (vuelve a `main:app`, el del Dockerfile).

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

1. **Dashboard y base de datos.** En cuanto `reportes_diarios` tenga filas (por `backfill_db.py` o por `sincronizar-db`), `main.py` deja de mostrar el último Excel y pasa a mostrar los totales **acumulados** de la base (por ejemplo, Procesos Analizados = 770 en vez de 2). Es el comportamiento que ya tiene `main.py`; conviene decidirlo antes de cargar el histórico.
2. **Sin `ADMIN_KEY` nadie puede reescribir un día pasado** con las extensiones activas. Un día sin reporte sí se puede completar.
3. **Reporte del 16/10/2026 en producción.** El archivo del repositorio está bien (12 procesos de Comprar, 540 organismos de TGN); el del contenedor quedó reemplazado. Se recupera solo con el próximo despliegue, que vuelve a copiar `data/` desde git.
4. **Respaldos en Railway.** `RESPALDOS_DIR` (por defecto `/app/respaldos`) vive en el disco del contenedor y se pierde al redesplegar. Para conservarlos, montar un volumen y apuntar `RESPALDOS_DIR` ahí.

## Pendiente (requiere modificar archivos existentes, no se hizo)

- `ejecucion_diaria.yml`: instalar con `pip install -r requirements.txt` (hoy falta `holidays`, así que el chequeo de feriados queda apagado) y, si se quiere alimentar la base, pasar `DATABASE_URL` como secret.
- `main.py`: usar la hora de Argentina en `es_hoy` y `/api/dias-disponibles`; vaciar `_df_cache` cuando aparece un reporte nuevo; persistir con un pool propio dentro del hilo de fondo.
- `requirements.txt`: fijar versiones (`pip-compile requirements.in`) y agregar `nest_asyncio`, que usa `db_reportes.py`.
- `templates/documentacion.html`: los rangos de riesgo que muestra (Alto 8-10, Medio 5-7) no coinciden con el código (Alto ≥ 7, Medio ≥ 4).
- Navegación: en `/analisis-vivo` y `/licitaciones` aparecen dos enlaces activos, y el dashboard no tiene "Licitaciones" en la barra.
- `README.md`: pesos viejos, login con `?key=` y `tests.yml` en lugar de `test.yml`.
- IA: el modelo por defecto es `claude-sonnet-4-5`; se puede actualizar sin tocar código con la variable `ANTHROPIC_MODEL=claude-sonnet-5-5`.
- Reemplazar `/manual` por `/manual-v2` (o enlazarlo desde la barra) cuando se apruebe el texto nuevo.
