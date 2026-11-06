# Monitor XAI — Manual de Usuario

Monitor de Contratos y Licitaciones Públicas del Estado nacional argentino.

Versión del manual: noviembre de 2026 · comprar.ecosistematransparencia.com.ar

## 1. ¿Qué es el Monitor XAI?

El Monitor XAI (eXplainable Artificial Intelligence, inteligencia artificial explicable) es una plataforma web de auditoría automatizada de las contrataciones del Estado nacional argentino. Todos los días hábiles lee los avisos del Boletín Oficial (BORA), los cruza con Comprar.gob.ar y con la Tesorería General de la Nación (TGN), aplica una matriz de indicadores de riesgo y ubica cada aviso en su marco normativo. Cada resultado se puede explicar: el sistema muestra qué indicador se activó y por qué.

> **Importante:** el sistema NO detecta delitos penales, no es un canal de denuncia y no analiza la conducta de personas individuales. Analiza decisiones discrecionales del Estado y señala patrones que merecen revisión.

## 2. Qué mide

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

### 2.2 Marco normativo de cada aviso

Además del riesgo, cada aviso se ubica en el régimen legal que le corresponde (detalle en la Sección 9):

- **Régimen:** bienes y servicios (Decreto Delegado 1023/2001), obra pública (Ley 13.064), concesión (Leyes 17.520 y 23.696) o venta de bienes del Estado.
- **Quién contrata:** empresas y sociedades del Estado, Poder Judicial, Ministerio Público, Poder Legislativo y universidades tienen regímenes propios; esos avisos se señalan y no se evalúan contra el Decreto 1030/2016.
- **Procedimiento y monto:** licitación o concurso público o privado, contratación directa o subasta; el monto se expresa en módulos.

## 3. Fuentes de datos y sus límites

- **Boletín Oficial (BORA), Sección Tercera:** índice de avisos del día y texto de cada adjudicación (a veces un PDF). De ese texto se extraen el proveedor, el CUIT y el monto; la extracción puede fallar. Desde el 22/10/2026 el BORA no responde a servidores ubicados fuera de Argentina: por eso los reportes se generan en un equipo en Argentina (Sección 4).
- **Comprar.gob.ar:** procesos con apertura próxima, tal como figuran en el momento de la consulta. No hay histórico: un día que se genera tarde queda sin Comprar.
- **TGN (Presupuesto Abierto):** crédito pagado en el año por cada organismo, en millones de pesos. No informa el CUIT del beneficiario, así que **no confirma que un proveedor puntual haya cobrado**. Tampoco tiene histórico diario.

Los cruces con Comprar y TGN se hacen por coincidencia de palabras en el nombre del organismo (al menos dos palabras significativas). Cada adjudicación recibe una etiqueta:

| Etiqueta | Significado |
|---|---|
| 📋 SOLO BORA | No se encontró el organismo en Comprar ni en TGN. |
| 🔷 BORA + COMPRAR | El organismo tiene procesos abiertos en Comprar. |
| 🔶 BORA + TGN (por organismo) | El organismo tiene pagos ejecutados en el año. No indica que este proveedor haya cobrado. |
| 🔶 BORA + TGN (cobró) | Coincidencia por CUIT en TGN. Hoy no ocurre, por el límite de la API. |
| 🚨 FLUJO COMPLETO | Hay CUIT y el organismo coincide en Comprar y en TGN. Es una coincidencia por organismo, no la trazabilidad de un pago. |

## 4. Procesos

### 4.1 Generación del reporte diario

Corre solo en un equipo con conexión de Argentina, registrado en GitHub como ejecutor ("runner") del proyecto. Se programa de lunes a viernes a las 08:30 y a las 12:30 (hora de Argentina); la corrida de las 12:30 es un reintento y no hace nada si el reporte ya está. Si el equipo está apagado, la corrida queda en espera hasta 24 horas y se ejecuta apenas se enciende.

En cada corrida:

1. Trae la última versión de los reportes publicados.
2. Busca los días hábiles sin reporte (saltea fines de semana y feriados) y comprueba que el BORA responda.
3. Consulta Comprar.gob.ar y TGN, solo para el día de hoy, porque no tienen histórico.
4. Para cada día que falta, lee el índice de la Sección Tercera del BORA y lo separa en licitaciones y adjudicaciones.
5. De cada adjudicación extrae el proveedor, el CUIT y el monto.
6. Cruza BORA → Comprar → TGN por organismo (Sección 3) y aplica la matriz de riesgo (Sección 2.1).
7. Guarda dos archivos Excel: `reporte_AAAA-MM-DD.xlsx` (todas las hojas) y `flujo_licitaciones_AAAA-MM-DD.xlsx`. Si el día se generó tarde, agrega una hoja "ℹ️ Origen" que lo indica.
8. Publica los Excel en el repositorio del proyecto.

### 4.2 Publicación en el sitio

Al publicarse un reporte, el sitio lo toma de dos maneras: el servidor se actualiza solo con el repositorio, y el botón **Actualizar datos en vivo** (Licitaciones) o **Traer reportes publicados** (Carga de Datos) lo baja en segundos sin esperar. El botón compara cada archivo con el publicado y solo baja lo nuevo o lo que cambió; si un día ya existía, guarda una copia de respaldo antes de reemplazarlo.

### 4.3 Control de faltantes

A las 14:00 de cada día hábil un control automático revisa si está el reporte de hoy. Si falta, envía un mail de aviso. Si el equipo se enciende más tarde, el reporte se genera igual y el aviso queda sin efecto.

### 4.4 Generación manual

Para completar un día a mano, en el equipo de Argentina, desde la carpeta del proyecto:

```
python tools/actualizar_desde_pc.py --dry-run      # lista los días que faltan
python tools/actualizar_desde_pc.py --publicar     # los genera y los publica
```

Para que el reporte incluya TGN, el equipo necesita la variable `TGN_TOKEN`.

### 4.5 Carga manual de un Excel

Desde **Carga de Datos**, con la clave de administración, se puede subir un Excel diario generado fuera del circuito automático (Sección 8). El sistema verifica que tenga las hojas de un reporte del monitor antes de guardarlo.

## 5. Estructura de navegación

- **Dashboard:** resumen del último reporte.
- **Licitaciones:** flujo cruzado BORA → Comprar → TGN del día, con detalle por adjudicación y marco normativo.
- **Carga de Datos:** trae los reportes publicados, elige el día y permite la carga manual.
- **Documentación:** descripción del sistema y descargas.
- **Manual:** este documento.
- **Estado:** salud del sistema y días faltantes (Sección 13).
- **API:** documentación interactiva (Swagger) en `/docs`.

## 6. Dashboard

Muestra el último reporte disponible.

- **Tarjetas:** Procesos Analizados, Intensidad Promedio (índice de riesgo promedio, 0 a 10), Alertas Alto Riesgo y Total Reportes guardados.
- **Distribución por tipo:** cantidad de adjudicaciones por tipo de proceso del BORA (licitación pública, contratación directa, etc.).
- **Nivel de riesgo:** cuántas adjudicaciones quedaron en Alto, Medio y Bajo.
- **Detalle del Análisis Algorítmico:** hasta 50 filas con organismo, tipo de proceso, índice y nivel.
- **Último reporte:** el archivo del día más reciente. Se descarga desde la página Estado o con `GET /api/reporte/AAAA-MM-DD/excel`.

## 7. Licitaciones — Flujo cruzado BORA → Comprar → TGN

Es la pantalla principal para el seguimiento diario.

- **Barra de estado:** fecha de los datos y fuentes. El botón 🚀 **Actualizar datos en vivo** trae los reportes publicados que el servidor todavía no tiene (Sección 4.2) y muestra el resumen del último día.
- **Etapas del flujo:** BORA Licitaciones, Comprar, Adjudicadas y TGN. Al hacer clic en una etapa se filtra la tabla; "Reset" quita el filtro.
- **Métricas:** Total Publicaciones BORA, Con CUIT Extraído, Sin CUIT (pendientes de revisión manual) y Flujo Completo.
- **Marco normativo de los avisos:** cuántos avisos hay por régimen y por procedimiento, cuántos son de entes con régimen propio y la lista de los que tienen observaciones (Sección 9).
- **Pestañas:** BORA Licitaciones, Comprar.gob.ar y Adjudicaciones.
- **Junto a cada CUIT:** ✓ o ⚠️ según el dígito verificador (Sección 10) y 🌍 ALERTA INTERNACIONAL si MEACI encuentra coincidencias (Sección 11).
- **🤖 Explicar con IA:** redacta por qué una fila quedó con ese nivel de riesgo (Sección 12).
- Para ver un día anterior: `/licitaciones?fecha=AAAA-MM-DD`, o elíjalo en Carga de Datos.

## 8. Carga de Datos

1. Pulse 🔄 **Traer reportes publicados**: el servidor baja los reportes que todavía no tiene (Sección 4.2). Tarda unos segundos.
2. Elija un día de la lista; solo aparecen los días con reporte, el más reciente primero. El enlace abre ese día en Licitaciones o descarga el Excel.
3. **Carga manual (administración):** indique el día, el tipo de archivo (`reporte` o `flujo_licitaciones`), el archivo y la clave de administración. Si el día ya tenía reporte, el anterior se respalda antes de reemplazarlo.

## 9. Marco normativo

La página `/marco-normativo` lista las normas que usa el sistema, con su estado de verificación (vigente, parcialmente derogada o sin verificar) y las correcciones hechas al listado de partida. Para cada aviso se evalúa:

- **Régimen material** según la categoría y el texto del aviso, con las normas y la plataforma que corresponden (COMPR.AR para bienes y servicios; CONTRAT.AR para obra pública y concesiones).
- **Ámbito subjetivo:** si el organismo contrata con régimen propio.
- **Procedimiento de selección.** Las contrataciones directas llevan la observación de verificar la causal invocada (Decreto Delegado 1023/2001, art. 25, inc. d).
- **Monto en módulos:** módulo de $40.000 (Decreto 666/2024). Los topes por procedimiento solo se controlan si se configuran, porque no se pudo confirmar el texto consolidado vigente.
- **Controles transversales:** transparencia activa (Ley 27.275), declaración jurada de intereses (Decreto 202/2017), habilidad fiscal (RG AFIP 4164/2017) y programa de integridad cuando corresponde (Ley 27.401, art. 24).

> Es un indicador de cumplimiento formal construido a partir del texto del aviso, no un dictamen jurídico.

## 10. Validación de formato de CUIT

El CUIT se extrae del texto del aviso, así que puede estar mal leído. El sistema verifica el dígito verificador con el algoritmo módulo 11 de AFIP (hoy ARCA).

- ✓ **Confirma** que el número tiene 11 dígitos y un dígito verificador correcto.
- ⚠️ **No consulta** ningún padrón: no confirma la inscripción real, la razón social ni el estado del contribuyente.

```
GET /api/cuit/validar?cuit=30-12345678-1
GET /api/cuit/validar-lote?cuits=30-12345678-1,20-12345678-6   (hasta 200)
```

## 11. Cruce de sanciones internacionales (MEACI)

MEACI es un servicio independiente que busca el CUIT del proveedor en bases de sanciones internacionales. Si hay coincidencia, la fila muestra 🌍 ALERTA INTERNACIONAL. Si MEACI no responde, la pantalla se carga igual, sin esa señal.

```
GET /api/cruce-cuit?cuit=30-68728814-5
GET /api/cruce-cuits-bulk?cuits=cuit1,cuit2,cuit3   (hasta 50)
```

## 12. Segunda opinión con IA

Cuando está configurada, la IA (Claude, de Anthropic) ofrece dos funciones:

- **Explicar riesgo:** redacta en lenguaje simple por qué una adjudicación quedó en su nivel, usando solo los indicadores que ya calculó la matriz.
- **Clasificar aviso:** propone una categoría temática para el texto de un aviso (obra pública, concesión, tarifas, etc.), con su razonamiento.

Cada visitante puede hacer 10 consultas por día, y hay un tope diario para todo el sitio. Las consultas que fallan no se descuentan. La IA es orientativa: **no cambia el índice ni el nivel de riesgo**.

## 13. Estado del sistema

La página `/estado` muestra la hora de Argentina, el último reporte (con enlace de descarga), cuántas filas trajo cada fuente, los días hábiles de los últimos 30 que no tienen reporte, si la base de datos y la IA están disponibles, y si la protección de reportes está activa. `GET /api/diagnostico` informa además si el servidor llega al BORA y cómo terminó la última consulta a la IA.

## 14. Cómo interpretar los resultados

- El índice es un **puntaje de indicadores**, no una probabilidad ni una prueba.
- Un nivel Alto o Medio indica que conviene revisar el aviso original; no implica irregularidad.
- "Sin CUIT" suele indicar un aviso en formato PDF o redactado de forma poco habitual: revise el aviso en el BORA.
- Las etiquetas de TGN y "Flujo Completo" son coincidencias por organismo, no pagos confirmados a un proveedor.
- Un aviso de un ente con régimen propio no se evalúa contra el Decreto 1030/2016: compárelo con el reglamento de ese ente.
- Los reportes anteriores a octubre de 2026 se calcularon con una versión previa de la matriz, que sumaba 1,36 puntos a todas las filas. Para comparar períodos, use los datos recalculados (ver MEJORAS.md).

## 15. API REST

Documentación interactiva en `/docs`.

| Endpoint | Descripción |
|---|---|
| `GET /api/status` | Estado general |
| `GET /api/estado-sistema` · `GET /api/diagnostico` | Estado detallado (Sección 13) |
| `GET /api/reportes` | Lista de reportes guardados |
| `GET /api/dias-disponibles` | Días con reporte |
| `GET /api/licitaciones/datos?fecha=AAAA-MM-DD` | Datos de un día (por defecto, el último) |
| `GET /api/reporte/AAAA-MM-DD/excel` | Descarga el Excel del día (`?tipo=flujo` para el de flujo) |
| `POST /api/datos/actualizar` · `GET /api/datos/estado` | Trae los reportes publicados (Sección 4.2) |
| `POST /api/admin/subir-reporte?fecha=AAAA-MM-DD&tipo=reporte` | Carga manual de un Excel (requiere clave) |
| `GET /api/licitaciones/normativa?fecha=AAAA-MM-DD` | Marco normativo de cada aviso del día |
| `GET /api/marco-normativo` | Catálogo de normas |
| `GET /api/cuit/validar` · `GET /api/cuit/validar-lote` | Validación de formato de CUIT |
| `GET /api/cruce-cuit` · `GET /api/cruce-cuits-bulk` | Cruce con MEACI |
| `GET /api/ia/status` · `GET /api/ia/usos` | Disponibilidad de la IA y consultas restantes |
| `POST /api/ia/explicar-riesgo` · `POST /api/ia/clasificar` | Segunda opinión con IA |
| `GET /health` | Healthcheck |

## 16. Flujo de trabajo recomendado

1. Abra **Licitaciones** y pulse 🚀 **Actualizar datos en vivo** para traer el reporte del día.
2. Revise primero las filas en Alto y Medio, y las de "Sin CUIT".
3. Verifique el ícono ✓/⚠️ antes de dar por bueno un CUIT.
4. Preste especial atención a cualquier 🌍 ALERTA INTERNACIONAL.
5. Mire las observaciones del panel de marco normativo, en especial las contrataciones directas.
6. Abra el aviso original del BORA (enlace en cada fila) antes de sacar conclusiones.
7. Si falta un día, mírelo en **Estado**: se completa solo cuando el equipo de Argentina se enciende, o a mano (Sección 4.4).

## 17. 🕸️ Relación con los otros sitios del ecosistema

Este sitio es parte del **Ecosistema de Transparencia**: once monitores que se consultan entre sí. Abajo, con qué sitios intercambia datos ("usa →" = toma datos de ese sitio; "← lo usa" = ese sitio toma datos de este) y de qué fuentes oficiales se alimenta. El grafo es interactivo: hacé clic en cualquier sitio para ver su ficha.

[Abrir el grafo completo ↗](https://mapa.ecosistematransparencia.com.ar/grafo?nodo=comprar)

**Conexiones**

- **usa → Contratos**: Mismas adjudicaciones del BORA; la validación cruzada diaria comprueba que coincidan día por día y en monto.
- **usa → MEACI**: Cruza CUIT de proveedores contra las sancionadas de MEACI y controla que MEACI esté disponible.
- **← lo usa Mapa**: Enlace y estado en vivo. La validación cruzada diaria (lun–vie 13:00) compara Comprar y Contratos día por día y peso por peso.

**Fuentes oficiales**

- Boletín Oficial (BORA), 3.ª sección
- COMPR.AR
- Tesorería General de la Nación (TGN)

Detalle de todas las conexiones y de cómo se verifican las cifras entre sitios: [mapa.ecosistematransparencia.com.ar/manual#conexiones](https://mapa.ecosistematransparencia.com.ar/manual#conexiones)

## 18. Descargas

- Manual en español y en inglés (.docx), desde esta página.
- Instructivo del dashboard (.docx), desde Documentación.
- Excel de cada día, desde Estado, desde Carga de Datos o con `GET /api/reporte/AAAA-MM-DD/excel`.

## 19. Aviso

> Esta herramienta es de carácter experimental y académico. Los datos provienen de fuentes públicas oficiales del Estado argentino. Los resultados son indicadores algorítmicos de riesgo: no implican juicio de valor, acusación ni determinación de responsabilidad sobre ninguna empresa, organismo o persona. El objetivo es promover la transparencia y el debate informado sobre el gasto público.

Contacto: vhmonte@retina.ar / viny01958@gmail.com · Licencia MIT
