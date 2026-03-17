# 🚂 Guía de deploy: Railway + PostgreSQL + Variables

## 1. Archivos a subir al repo (rama `desarrollo`)

| Archivo | Destino en el repo |
|---|---|
| `main.py` | raíz del proyecto |
| `requirements.txt` | raíz del proyecto |
| `templates/dashboard.html` | carpeta `templates/` |

---

## 2. Agregar PostgreSQL en Railway

1. Abrí tu proyecto en https://railway.app
2. Click **"+ New"** → **"Database"** → **"Add PostgreSQL"**
3. Railway genera automáticamente la variable `DATABASE_URL`
   - Va a aparecer en el tab **"Variables"** de tu servicio FastAPI
   - **No necesitás copiarla manualmente** — Railway la inyecta sola
4. Redeploy el servicio (o esperar el deploy automático del próximo push)

---

## 3. Variables de entorno a configurar manualmente

Ve a tu servicio FastAPI → **"Variables"** → **"New Variable"**:

| Variable | Valor de ejemplo | Descripción |
|---|---|---|
| `ADMIN_KEY` | `mi-clave-secreta-2026` | Protege el endpoint `/api/donation-stats` |
| `GA_MEASUREMENT_ID` | `G-XXXXXXXXXX` | ID de tu propiedad GA4 |
| `GA_API_SECRET` | `xxxxxxxxxxxx` | Secret de Measurement Protocol (GA4) |

### Cómo obtener GA_API_SECRET
1. Google Analytics → Admin → Data Streams → tu stream
2. "Measurement Protocol API secrets" → Create
3. Copiar el valor generado

---

## 4. Verificar que todo funciona

```bash
# Health check
curl https://gobbocomprartgn-production.up.railway.app/health

# Estadísticas de donaciones (reemplazá TU-CLAVE)
curl -H "x-admin-key: TU-CLAVE" \
  https://gobbocomprartgn-production.up.railway.app/api/donation-stats
```

---

## 5. Flujo de datos de donación

```
Usuario abre modal
    │
    ├─► gtag('event', 'donation_open_modal')   ← GA4 client-side
    └─► POST /api/donation-event               ← FastAPI
            │
            ├─► INSERT INTO donation_events    ← PostgreSQL (Railway)
            └─► GA4 Measurement Protocol       ← server-side (opcional)
```

Eventos registrados:
- `open_modal`      → abrió el modal de donación
- `select_country`  → eligió AR o abroad
- `view_details`    → clickeó "Ver datos para transferir"
- `confirm`         → clickeó "Voy a transferir"

---

## 6. Ver estadísticas

```
GET /api/donation-stats
Header: x-admin-key: TU-CLAVE
```

Respuesta:
```json
{
  "total_events": 47,
  "by_event_type": [{"event_type": "open_modal", "n": 20}, ...],
  "by_country": [{"country": "AR", "n": 15}, ...],
  "by_currency": [{"currency": "ARS", "n": 8}, ...],
  "daily_last_30": [{"day": "2026-03-17", "n": 5}, ...]
}
```
