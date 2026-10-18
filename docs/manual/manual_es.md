# Monitor XAI — Manual de Usuario

Monitor de Contratos y Licitaciones Públicas. Basado en la Teoría de Fenómenos Corruptivos de Vicente Humberto Monteverde, Ph.D.

Versión del manual: octubre de 2026 · gobbocomprartgn-production.up.railway.app

## 1. ¿Qué es el Monitor XAI?

El Monitor XAI (eXplainable Artificial Intelligence, inteligencia artificial explicable) es una plataforma web de auditoría automatizada de las contrataciones del Estado nacional argentino. Todos los días hábiles lee los avisos del Boletín Oficial (BORA), los cruza con Comprar.gob.ar y con la Tesorería General de la Nación (TGN), y aplica una matriz de indicadores de riesgo. Cada resultado se puede explicar: el sistema muestra qué indicador se activó y por qué.

> **Importante:** el sistema NO detecta delitos penales, no es un canal de denuncia y no analiza la conducta de personas individuales. Analiza decisiones discrecionales del Estado y señala patrones que merecen revisión.

## 2. Qué mide: dos matrices

El sistema usa dos matrices distintas. Es importante no confundirlas.

### 2.1 Matriz de Riesgo Licitatorio (la que ve en Licitaciones y en el Dashboard)

Se aplica a cada adjudicación publicada en el BORA. Suma el peso de los indicadores que se activan:

| Indicador | Peso | Cuándo se activa |
|---|---|---|
| Contratación Directa | 3,0 | El tipo de proceso es contratación directa, por excepción o compulsa abreviada. |
| Proveedor Único | 2,5 | El mismo CUIT aparece en dos o más adjudicaciones del mismo día. |
| Monto Límite | 2,5 | El monto queda hasta un 10% por debajo de un tope que obliga a un procedimiento más competitivo (1.000 o 5.000 módulos, Decreto 1030/2016, art. 27). Sugiere fraccionamiento. |
| Proveedor Multi-Organismo | 1,5 | El mismo CUIT cobra en varios organismos en TGN. Hoy no puede activarse: la API de TGN no informa el CUIT del beneficiario. |

El **índice de riesgo (0 a 10)** es la suma de los pesos dividida por 9,5 y multiplicada por 10. Como el último indicador no puede activarse, el valor máximo posible hoy es 8,42.

| Nivel | Índice | Observación |
|---|---|---|
| Alto | 7 o más | Requiere, en la práctica, que se activen juntos Contratación Directa, Proveedor Único y Monto Límite. |
| Medio | 4 a 6,99 | Una Contratación Directa queda siempre como mínimo en Medio, aunque su índice sea 3,16. |
| Bajo | menos de 4 | Bajo no significa "sin riesgo": significa que no se activó ningún indicador de la matriz. |

### 2.2 Escenarios teóricos de transferencia regresiva

Es el marco conceptual del Dr. Monteverde: la Gran Corrupción no se limita a actos ilegales, sino que incluye decisiones legales que trasladan ingresos desde sectores con menos poder de negociación hacia sectores con más. El sistema clasifica textos en siete escenarios mediante palabras clave:

| Escenario | Peso | Dirección de la transferencia |
|---|---|---|
| Jubilaciones / Pensiones | 10,0 | Jubilados → Estado |
| Traslado de Impuestos | 9,5 | Contribuyentes → Estado |
| Privatización / Concesión | 9,0 | Estado → Privados |
| Obra Pública / Contratos | 8,5 | Estado → Empresas contratistas |
| Tarifas de Servicios Públicos | 7,5 | Usuarios → Concesionarias |
| Precios de Consumo Regulados | 6,5 | Consumidores → Productores |
| Salarios y Paritarias | 5,5 | Asalariados → Empleadores |

Esta clasificación se usa en el endpoint `POST /api/analisis` y en la segunda opinión de la IA (Sección 11). No interviene en el índice de riesgo de las licitaciones.

Referencia: Monteverde, V. H. (2020). Great corruption – theory of corrupt phenomena. Journal of Financial Crime, Vol. 28 No. 2, pp. 580-595. https://doi.org/10.1108/JFC-04-2020-0062

## 3. Fuentes de datos y sus límites

- **Boletín Oficial (BORA), Sección Tercera:** índice de avisos del día y texto de cada adjudicación (a veces un PDF). De ese texto se extraen el proveedor, el CUIT y el monto; la extracción puede fallar.
- **Comprar.gob.ar:** procesos con apertura próxima, tal como figuran en el momento de la consulta. No hay histórico: para días pasados no se consulta.
- **TGN (Presupuesto Abierto):** crédito pagado en el año por cada organismo, en millones de pesos. No informa el CUIT del beneficiario, así que **no confirma que un proveedor puntual haya cobrado**. Tampoco tiene histórico diario.

Los cruces con Comprar y TGN se hacen por coincidencia de palabras en el nombre del organismo (al menos dos palabras significativas). Cada adjudicación recibe una etiqueta:

| Etiqueta | Significado |
|---|---|
| 📋 SOLO BORA | No se encontró el organismo en Comprar ni en TGN. |
| 🔷 BORA + COMPRAR | El organismo tiene procesos abiertos en Comprar. |
| 🔶 BORA + TGN (por organismo) | El organismo tiene pagos ejecutados en el año. No indica que este proveedor haya cobrado. |
| 🔶 BORA + TGN (cobró) | Coincidencia por CUIT en TGN. Hoy no ocurre, por el límite de la API. |
| 🚨 FLUJO COMPLETO | Hay CUIT y el organismo coincide en Comprar y en TGN. Es una coincidencia por organismo, no la trazabilidad de un pago. |

## 4. Actualización automática

El ciclo completo corre solo, de lunes a viernes, a las 08:00 y a las 12:00 (hora de Argentina). La corrida de las 12:00 es un reintento: si a la mañana ya se generó el reporte, no hace nada. Los fines de semana y los días sin edición del BORA no se genera reporte. Cada reporte queda guardado en dos archivos Excel por día y aparece en el sitio con la siguiente actualización del repositorio.

No hace falta ejecutar nada a mano para el seguimiento diario.

## 5. Estructura de navegación

- **Dashboard:** resumen del último reporte.
- **Licitaciones:** flujo cruzado BORA → Comprar → TGN del último reporte, con detalle por adjudicación.
- **Análisis en Vivo:** ejecución manual del ciclo para un día.
- **Documentación:** marco teórico y descargas.
- **Manual:** este documento.
- **Estado:** salud del sistema y días faltantes (Sección 12).
- **API:** documentación interactiva (Swagger) en `/docs`.

## 6. Dashboard

Muestra el último reporte disponible.

- **Tarjetas:** Procesos Analizados, Intensidad Promedio (índice de riesgo promedio, 0 a 10), Alertas Alto Riesgo y Total Reportes guardados.
- **Distribución por tipo:** cantidad de adjudicaciones por tipo de proceso del BORA (licitación pública, contratación directa, etc.).
- **Nivel de riesgo:** cuántas adjudicaciones quedaron en Alto, Medio y Bajo.
- **Detalle del Análisis Algorítmico:** hasta 50 filas con organismo, tipo de proceso, índice y nivel.
- **Último reporte:** el archivo del día más reciente. Se descarga desde la página Estado o con `GET /api/reporte/AAAA-MM-DD/excel`.

## 7. Análisis en Vivo

Permite ejecutar el ciclo para un día elegido.

1. Elija un día en el calendario. Se muestran todos los días desde el 23/02/2026; los que ya tienen reporte aparecen marcados.
2. Pulse 🚀. El análisis corre en segundo plano y la pantalla consulta su avance; suele tardar entre uno y cinco minutos.
3. Al terminar se muestran los totales y enlaces al Dashboard y a Licitaciones.

> **Tenga en cuenta:** solo puede correr un análisis por vez y como máximo uno cada 10 minutos. Para un día pasado se consulta únicamente el BORA, porque Comprar y TGN solo tienen el estado de hoy. Por eso, volver a ejecutar un día pasado que ya tiene reporte lo reemplazaría por uno con menos datos: requiere la clave de administración y, antes de reemplazarlo, el sistema guarda una copia de respaldo. Un día pasado que todavía no tiene reporte se puede completar sin clave.

## 8. Licitaciones — Flujo cruzado BORA → Comprar → TGN

Es la pantalla principal para el seguimiento diario.

- **Barra de estado:** fecha de los datos y fuentes. El botón "Actualizar datos en vivo" ejecuta el ciclo del día de hoy (mismas reglas que la Sección 7).
- **Etapas del flujo:** BORA Licitaciones, Comprar, Adjudicadas y TGN. Al hacer clic en una etapa se filtra la tabla; "Reset" quita el filtro.
- **Métricas:** Total Publicaciones BORA, Con CUIT Extraído, Sin CUIT (pendientes de revisión manual) y Flujo Completo.
- **Pestañas:** BORA Licitaciones, Comprar.gob.ar y Adjudicaciones.
- **Junto a cada CUIT:** ✓ o ⚠️ según el dígito verificador (Sección 9) y 🌍 ALERTA INTERNACIONAL si MEACI encuentra coincidencias (Sección 10).
- **🤖 Explicar con IA:** redacta por qué una fila quedó con ese nivel de riesgo (Sección 11).

## 9. Validación de formato de CUIT

El CUIT se extrae del texto del aviso, así que puede estar mal leído. El sistema verifica el dígito verificador con el algoritmo módulo 11 de AFIP (hoy ARCA).

- ✓ **Confirma** que el número tiene 11 dígitos y un dígito verificador correcto.
- ⚠️ **No consulta** ningún padrón: no confirma la inscripción real, la razón social ni el estado del contribuyente.

```
GET /api/cuit/validar?cuit=30-12345678-1
GET /api/cuit/validar-lote?cuits=30-12345678-1,20-12345678-6   (hasta 200)
```

## 10. Cruce de sanciones internacionales (MEACI)

MEACI es un servicio independiente que busca el CUIT del proveedor en bases de sanciones internacionales. Si hay coincidencia, la fila muestra 🌍 ALERTA INTERNACIONAL. Si MEACI no responde, la pantalla se carga igual, sin esa señal.

```
GET /api/cruce-cuit?cuit=30-68728814-5
GET /api/cruce-cuits-bulk?cuits=cuit1,cuit2,cuit3   (hasta 50)
```

## 11. Segunda opinión con IA

Cuando está configurada, la IA (Claude, de Anthropic) ofrece dos funciones:

- **Explicar riesgo:** redacta en lenguaje simple por qué una adjudicación quedó en su nivel, usando solo los indicadores que ya calculó la matriz.
- **Clasificar aviso:** propone uno de los siete escenarios teóricos para un texto, con su razonamiento.

Cada visitante puede hacer 3 consultas por día, y hay un tope diario para todo el sitio. Las consultas que fallan no se descuentan. La IA es orientativa: **no cambia el índice ni el nivel de riesgo**.

## 12. Estado del sistema

La página `/estado` muestra la hora de Argentina, el último reporte (con enlace de descarga), cuántas filas trajo cada fuente, los días hábiles de los últimos 30 que no tienen reporte, si la base de datos y la IA están disponibles, y si la protección de reportes está activa.

## 13. Cómo interpretar los resultados

- El índice es un **puntaje de indicadores**, no una probabilidad ni una prueba.
- Un nivel Alto o Medio indica que conviene revisar el aviso original; no implica irregularidad.
- "Sin CUIT" suele indicar un aviso en formato PDF o redactado de forma poco habitual: revise el aviso en el BORA.
- Las etiquetas de TGN y "Flujo Completo" son coincidencias por organismo, no pagos confirmados a un proveedor.
- Los reportes anteriores a octubre de 2026 se calcularon con una versión previa de la matriz, que sumaba 1,36 puntos a todas las filas. Para comparar períodos, use los datos recalculados (ver MEJORAS.md).

## 14. API REST

Documentación interactiva en `/docs`.

| Endpoint | Descripción |
|---|---|
| `GET /api/status` | Estado general |
| `GET /api/estado-sistema` | Estado detallado (Sección 12) |
| `GET /api/reportes` | Lista de reportes guardados |
| `GET /api/dias-disponibles` | Días con reporte |
| `GET /api/licitaciones/datos?fecha=AAAA-MM-DD` | Datos de un día (por defecto, el último) |
| `GET /api/reporte/AAAA-MM-DD/excel` | Descarga el Excel del día (`?tipo=flujo` para el de flujo) |
| `POST /api/licitaciones/ejecutar?fecha=AAAA-MM-DD` | Inicia el ciclo para un día |
| `GET /api/licitaciones/estado` | Avance del ciclo en curso |
| `POST /api/analisis` | Clasificación por escenarios teóricos (requiere clave) |
| `GET /api/marco-teorico` | Los siete escenarios |
| `GET /api/cuit/validar` · `GET /api/cuit/validar-lote` | Validación de formato de CUIT |
| `GET /api/cruce-cuit` · `GET /api/cruce-cuits-bulk` | Cruce con MEACI |
| `GET /api/ia/status` · `GET /api/ia/usos` | Disponibilidad de la IA y consultas restantes |
| `POST /api/ia/explicar-riesgo` · `POST /api/ia/clasificar` | Segunda opinión con IA |
| `GET /health` | Healthcheck |

## 15. Flujo de trabajo recomendado

1. Abra **Licitaciones**: el reporte del día se genera solo a las 08:00.
2. Revise primero las filas en Alto y Medio, y las de "Sin CUIT".
3. Verifique el ícono ✓/⚠️ antes de dar por bueno un CUIT.
4. Preste especial atención a cualquier 🌍 ALERTA INTERNACIONAL.
5. Abra el aviso original del BORA (enlace en cada fila) antes de sacar conclusiones.
6. Si falta un día, mírelo en **Estado** y complételo desde **Análisis en Vivo**.

## 16. Descargas

- Manual en español y en inglés (.docx), desde esta página.
- Artículo del Dr. Monteverde (.docx) e instructivo del dashboard (.docx), desde Documentación.
- Excel de cada día, desde Estado o con `GET /api/reporte/AAAA-MM-DD/excel`.

## 17. Aviso

> Esta herramienta es de carácter experimental y académico. Los datos provienen de fuentes públicas oficiales del Estado argentino. Los resultados son indicadores algorítmicos de riesgo: no implican juicio de valor, acusación ni determinación de responsabilidad sobre ninguna empresa, organismo o persona. El objetivo es promover la transparencia y el debate informado sobre el gasto público.

Contacto: vhmonte@retina.ar / viny01958@gmail.com · Licencia MIT
