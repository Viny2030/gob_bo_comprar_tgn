# 🏛️ Monitor de Contratos y Licitaciones Públicas

## Sistema de Detección Automática de Transferencias Regresivas de Ingresos

Sistema automatizado de análisis de decisiones estatales basado en la **Teoría de Fenómenos Corruptivos** del **Ph.D. Vicente Humberto Monteverde** (Journal of Financial Crime, 2020).

🌐 **Sitio en vivo:** https://gobbocomprartgn-production.up.railway.app/

---

## 📋 Tabla de Contenidos

- [Descripción](#-descripción)
- [Fundamento Teórico](#-fundamento-teórico)
- [Características](#-características)
- [Stack Tecnológico](#-stack-tecnológico)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [Instalación](#-instalación)
- [Uso](#-uso)
- [Panel de Administración](#-panel-de-administración)
- [Tests Automáticos](#-tests-automáticos)
- [Variables de Entorno](#-variables-de-entorno)
- [Dockerización](#-dockerización)
- [Referencias Académicas](#-referencias-académicas)
- [Licencia](#-licencia)

---

## 🎯 Descripción

Este sistema realiza **auditoría automatizada de decisiones estatales legales** publicadas en:
- Boletín Oficial de la República Argentina (BORA)
- Portal Comprar.gob.ar
- Tesorería General de la Nación (TGN)

**No detecta delitos penales**, sino **fenómenos corruptivos legales** que generan transferencias regresivas de ingresos según la taxonomía científica del Dr. Monteverde.

### ¿Qué NO es este sistema?

❌ Un detector de sobornos o malversación  
❌ Un sistema de denuncia penal  
❌ Un análisis de corrupción individual  

### ¿Qué SÍ es?

✅ Analizador de decisiones discrecionales del Estado  
✅ Detector de transferencias económicas regresivas  
✅ Herramienta de transparencia basada en evidencia científica  
✅ Sistema de alertas tempranas sobre decisiones de alto impacto social  

---

## 🔬 Fundamento Teórico

### Teoría de Fenómenos Corruptivos (Monteverde, 2020)

La **Gran Corrupción** no se limita a actos ilegales. La corrupción moderna se ha diversificado en **fenómenos legales** que producen las mismas consecuencias económicas.

### Los 7 Escenarios Críticos

| Escenario | Peso XAI | Dirección de Transferencia |
|---|---|---|
| Privatización / Concesión | 9.0 | Estado → Privados |
| Obra Pública / Contratos | 8.5 | Estado → Empresas Contratistas |
| Tarifas Servicios Públicos | 7.5 | Usuarios → Concesionarias |
| Precios Regulados | 6.5 | Consumidores → Productores |
| Salarios y Paritarias | 5.5 | Asalariados → Empleadores |
| **Jubilaciones / Pensiones** | **10.0** | Jubilados → Estado |
| Traslado de Impuestos | 9.5 | Contribuyentes → Estado |

### Matriz de Riesgo Licitatorio (la que se aplica a cada adjudicación)

| Indicador | Peso |
|---|---|
| Contratación Directa | 3.0 |
| Proveedor Único (mismo CUIT, mismo día) | 2.5 |
| Monto Límite (hasta 10% bajo un tope de módulos) | 2.5 |
| Proveedor Multi-Organismo (requiere CUIT en TGN; hoy no se activa) | 1.5 |

Índice = suma / 9,5 × 10. Alto ≥ 7, Medio ≥ 4, Bajo < 4; una Contratación Directa queda como mínimo en Medio. Detalle en el manual (`/manual`) y en `MEJORAS.md`.

**Referencia:** Monteverde, V. H. (2020). *Great corruption – theory of corrupt phenomena*. Journal of Financial Crime, Vol. 28 No. 2, pp. 580-595.

---

## ✨ Características

### 🤖 Automatización Completa
- ✅ Web scraping diario de BORA, Comprar.gob.ar y TGN
- ✅ Análisis automático con matriz XAI (Explainable AI)
- ✅ Cruce de tres fuentes oficiales de datos
- ✅ Generación de reportes Excel
- ✅ Archivado mensual automático

### 📊 Dashboard Interactivo
- ✅ Visualización con Chart.js
- ✅ Gráficos interactivos de riesgo y fenómenos
- ✅ Tabla de auditoría con nivel de riesgo por proceso
- ✅ Modal de donación con tracking GA4

### 📈 Analytics y Estadísticas
- ✅ Google Analytics 4 integrado
- ✅ Tracking de eventos de donación (server-side + client-side)
- ✅ Panel de admin en `/admin` con estadísticas en tiempo real
- ✅ PostgreSQL para persistencia de datos

### 🔒 Seguridad
- ✅ HTTPS automático (Railway)
- ✅ Variables de entorno para secrets
- ✅ Panel admin protegido con clave
- ✅ Rama `desarrollo` protegida en GitHub

### 🧪 Tests Automáticos
- ✅ GitHub Actions corre tests en cada PR
- ✅ Stress testing del algoritmo XAI por grupos demográficos
- ✅ Auditoría de integridad del diccionario de reglas

---

## 🛠️ Stack Tecnológico

| Componente | Tecnología |
|---|---|
| Backend | FastAPI + Python 3.13 |
| Base de datos | PostgreSQL (Railway) |
| Frontend | HTML + Chart.js + Vanilla JS |
| Analytics | Google Analytics 4 + Measurement Protocol |
| Deploy | Railway (Docker) |
| CI/CD | GitHub Actions |
| Scraping | requests + BeautifulSoup4 |
| Data | pandas + openpyxl |

---

## 📁 Estructura del Proyecto

```
gob_bo_comprar_tgn/
│
├── main.py                    # FastAPI app principal
├── app_extendida.py           # main.py + extensiones (punto de entrada del Dockerfile)
├── extensiones/               # Protección de reportes, /estado, descargas, carga en la base
├── analisis.py                # Motor de análisis XAI
├── analisis_v2.py             # Matrices revisadas, para comparar (no se usan en producción)
├── diario.py                  # Scraping y ciclo diario
├── requirements.txt           # Dependencias Python
├── Dockerfile                 # Contenedor Docker
│
├── templates/
│   ├── dashboard.html         # Dashboard principal
│   ├── analisis.html          # Análisis en vivo
│   ├── documentacion.html     # Documentación
│   ├── licitaciones.html      # Licitaciones
│   ├── estado.html            # Estado del sistema
│   ├── manual_v2.html         # Manual ES/EN (generado desde docs/manual/*.md)
│   └── admin.html             # Panel de administración
│
├── static/
│   └── style.css              # Estilos
│
├── data/                      # Reportes organizados por mes
│   └── 2026-03/
│       ├── reporte_2026-03-17.xlsx
│       └── flujo_licitaciones_2026-03-17.xlsx
│
├── tools/                     # backfill_db, recalcular_historico, generar_manual
├── docs/manual/               # Fuente del manual (manual_es.md, manual_en.md)
├── test_*.py                  # Tests automáticos (pytest)
└── .github/workflows/
    ├── test.yml               # CI: tests en cada PR
    ├── tests_extendidos.yml   # CI: todos los tests + manual al día
    └── ejecucion_diaria.yml   # Ciclo diario automático
```

---

## 🚀 Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/Viny2030/gob_bo_comprar_tgn.git
cd gob_bo_comprar_tgn

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno (ver sección Variables)

# 4. Correr localmente
uvicorn app_extendida:app --reload
```

---

## 📖 Uso

### Dashboard
Accedé al sitio en vivo: https://gobbocomprartgn-production.up.railway.app/

### Análisis en Vivo
```
GET /analisis-vivo
```
Ejecuta un ciclo completo de scraping y análisis.

### API
```
GET  /api/status              → Estado del sistema
GET  /api/estado-sistema      → Estado detallado (también en la página /estado)
GET  /api/reportes            → Lista de reportes disponibles
GET  /api/licitaciones/datos  → Datos del último reporte
GET  /api/reporte/{fecha}/excel → Descarga el Excel de un día
POST /api/licitaciones/ejecutar → Ejecutar análisis manual (un día pasado con reporte requiere ADMIN_KEY)
GET  /docs                    → Swagger UI

# Agentic AI (opcional, requiere ANTHROPIC_API_KEY)
GET  /api/ia/status           → Indica si la IA está configurada
GET  /api/ia/usos             → Consultas de IA que le quedan hoy al visitante
POST /api/ia/clasificar       → Segunda opinión de Claude sobre un aviso BORA
POST /api/ia/explicar-riesgo  → Explicación en lenguaje natural de un score de riesgo
```

---

## 🔐 Panel de Administración

Accedé a las estadísticas de donaciones en `https://gobbocomprartgn-production.up.railway.app/admin`
e ingresá la clave (`ADMIN_KEY`) en el formulario. La sesión queda en una cookie: la clave no va en la URL.
Con la sesión iniciada también se puede volver a ejecutar un día pasado desde Análisis en Vivo.

Muestra:
- Total de eventos de donación
- Distribución por país (AR / exterior)
- Gráfico de eventos por día (últimos 30 días)
- Tabla de últimos 20 eventos

---

## 🧪 Tests Automáticos

Los tests corren automáticamente en cada Pull Request via GitHub Actions.

```bash
# Correr localmente (todos los tests)
pip install -r requirements-dev.txt
pytest -v
```

**Qué testean:**
- `test_cobertura_demografica` — Stress test del algoritmo XAI por sector (Jubilados, Usuarios, Empresas, Falsos positivos)
- `test_auditoria_diccionario_completo` — Integridad de la MATRIZ_TEORICA

---

## ⚙️ Variables de Entorno

Configurar en Railway → tu servicio → Variables:

| Variable | Descripción |
|---|---|
| `DATABASE_URL` | URL de PostgreSQL (Railway lo inyecta automáticamente) |
| `ADMIN_KEY` | Clave para acceder al panel `/admin` (login por cookie, no va en la URL) |
| `GA_MEASUREMENT_ID` | ID de Google Analytics 4 (ej: `G-XXXXXXXXXX`) |
| `GA_API_SECRET` | Secret para GA4 Measurement Protocol (server-side) |
| `TGN_TOKEN` | Bearer token de presupuestoabierto.gob.ar para el cruce de pagos TGN |
| `CORS_ORIGINS` | Orígenes permitidos separados por coma (default: el dominio de Railway) |
| `ANTHROPIC_API_KEY` | Habilita los endpoints `/api/ia/*` (agentic AI, opcional) |
| `ANTHROPIC_MODEL` | Modelo a usar en `/api/ia/*` (default: `claude-sonnet-5-5`) |
| `RESPALDOS_DIR` | Carpeta de respaldos de reportes reemplazados (default: `/app/respaldos`) |

---

## 🐳 Dockerización

```bash
# Construir
docker build -t monitor-contratos .

# Ejecutar
docker run -p 8000:8000 monitor-contratos
```

---

## 📚 Referencias Académicas

**Monteverde, V. H. (2020)**  
*Great corruption – theory of corrupt phenomena*  
Journal of Financial Crime, Vol. 28 No. 2, pp. 580-595  
https://doi.org/10.1108/JFC-04-2020-0062

---

## 📄 Licencia

MIT License — Ver archivo LICENSE para detalles.

---

## 📞 Contacto

- **Email:** vhmonte@retina.ar / viny01958@gmail.com
- **Sitio:** https://gobbocomprartgn-production.up.railway.app/

---

⚠️ **Aviso:** Esta herramienta es de carácter experimental y académico. Los datos provienen de fuentes públicas oficiales del Estado argentino. Los resultados son indicadores algorítmicos de riesgo — no implican juicio de valor, acusación ni determinación de responsabilidad sobre ninguna empresa, organismo o persona. El objetivo es promover la transparencia y el debate informado sobre el gasto público.
