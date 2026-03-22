import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import datetime

# ===============================
# CONFIGURACIÓN Y ESTILO
# ===============================
st.set_page_config(page_title="Monitor de Gran Corrupción", layout="wide")

DATA_DIR = "/app/gob_docker/data" if os.path.exists("/app") else "gob_docker/data"

# ===============================
# FUNCIONES DE GESTIÓN DE ARCHIVOS MENSUALES
# ===============================
def obtener_meses_disponibles():
    if not os.path.exists(DATA_DIR):
        return []
    meses = []
    for item in os.listdir(DATA_DIR):
        item_path = os.path.join(DATA_DIR, item)
        if os.path.isdir(item_path) and len(item) == 7 and item[4] == "-":
            meses.append(item)
    return sorted(meses, reverse=True)

def obtener_archivos_del_mes(mes):
    mes_dir = os.path.join(DATA_DIR, mes)
    if not os.path.exists(mes_dir):
        return []
    archivos = [f for f in os.listdir(mes_dir) if f.endswith(".xlsx")]
    return sorted(archivos, reverse=True)

def formatear_nombre_mes(mes_codigo):
    meses_esp = {
        "01": "Enero", "02": "Febrero", "03": "Marzo", "04": "Abril",
        "05": "Mayo", "06": "Junio", "07": "Julio", "08": "Agosto",
        "09": "Septiembre", "10": "Octubre", "11": "Noviembre", "12": "Diciembre",
    }
    try:
        year, mes = mes_codigo.split("-")
        return f"{meses_esp[mes]} {year}"
    except:
        return mes_codigo

# ===============================
# TRATAMIENTO DE DATOS
# ===============================
@st.cache_data(ttl=3600, show_spinner="Cargando datos...")
def cargar_y_limpiar(ruta):
    df = pd.read_excel(ruta)
    mapeo = {
        "indice_total": "indice_fenomeno_corruptivo",
        "nivel_riesgo": "nivel_riesgo_teorico",
        "origen": "transferencia",
    }
    for viejo, nuevo in mapeo.items():
        if viejo in df.columns and nuevo not in df.columns:
            df = df.rename(columns={viejo: nuevo})
    df = df.loc[:, ~df.columns.duplicated()]
    if "indice_fenomeno_corruptivo" not in df.columns:
        df["indice_fenomeno_corruptivo"] = 0.0
    if "tipo_decision" not in df.columns:
        df["tipo_decision"] = "No identificado"
    return df

# ===============================
# SIDEBAR Y NAVEGACIÓN
# ===============================
st.sidebar.header("Configuracion")
st.sidebar.divider()
st.sidebar.subheader("Navegacion")
pagina = st.sidebar.radio(
    "Seleccione una seccion:",
    ["Dashboard Principal", "Instructivo de Uso"],
    label_visibility="collapsed",
)

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# ===============================
# PÁGINA DE INSTRUCTIVO
# ===============================
if pagina == "Instructivo de Uso":
    st.title("Instructivo de Uso del Dashboard")
    st.markdown("### Guia completa para utilizar el Monitor de Fenomenos Corruptivos")

    st.warning(
        "Nota: Esta herramienta es de caracter experimental y academico. "
        "Los datos provienen de fuentes publicas oficiales del Estado argentino. "
        "Los resultados son indicadores algoritmicos de riesgo - no implican juicio de valor, "
        "acusacion ni determinacion de responsabilidad sobre ninguna empresa, organismo o persona. "
        "El objetivo es promover la transparencia y el debate informado sobre el gasto publico."
    )

    st.divider()
    instructivo_path = "instructivo_dashboard.docx"
    if os.path.exists(instructivo_path):
        with open(instructivo_path, "rb") as file:
            st.download_button(
                label="Descargar Instructivo Completo (Word)",
                data=file,
                file_name="Instructivo_Monitor_Fenomenos_Corruptivos.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
    else:
        st.warning("El instructivo no esta disponible.")
    st.stop()

# ===============================
# DASHBOARD PRINCIPAL
# ===============================
meses_disponibles = obtener_meses_disponibles()

if not meses_disponibles:
    st.error("No se encontraron datos. Ejecute diario.py para generar el primer reporte.")
    st.stop()

st.sidebar.divider()
st.sidebar.subheader("Seleccion de Periodo")
mes_seleccionado = st.sidebar.selectbox(
    "Mes a analizar",
    meses_disponibles,
    format_func=formatear_nombre_mes
)

archivos_del_mes = obtener_archivos_del_mes(mes_seleccionado)
if not archivos_del_mes:
    st.error(f"No se encontraron reportes para {formatear_nombre_mes(mes_seleccionado)}")
    st.stop()

archivo_selec = st.sidebar.selectbox(
    "Reporte Diario",
    archivos_del_mes,
    format_func=lambda x: x.replace("reporte_fenomenos_", "").replace(".xlsx", ""),
)

ruta_completa = os.path.join(DATA_DIR, mes_seleccionado, archivo_selec)
df = cargar_y_limpiar(ruta_completa)

st.sidebar.divider()
st.sidebar.info(f"**Periodo:** {formatear_nombre_mes(mes_seleccionado)}\n**Total reportes:** {len(archivos_del_mes)} dias")

# ===============================
# HEADER, DISCLAIMER Y MÉTRICAS
# ===============================
st.title("Monitor de Fenomenos Corruptivos Legales")
st.markdown("### Implementacion de la Teoria del **Ph.D. Vicente Humberto Monteverde**")

st.warning(
    "\u26a0\ufe0f **Nota:** Esta herramienta es de car\u00e1cter experimental y acad\u00e9mico. "
    "Los datos provienen de fuentes p\u00fablicas oficiales del Estado argentino. "
    "Los resultados son indicadores algor\u00edtmicos de riesgo \u2014 no implican juicio de valor, "
    "acusaci\u00f3n ni determinaci\u00f3n de responsabilidad sobre ninguna empresa, organismo o persona. "
    "El objetivo es promover la transparencia y el debate informado sobre el gasto p\u00fablico."
)

df_detectados = df[df["tipo_decision"] != "No identificado"]

m1, m2, m3, m4 = st.columns(4)
m1.metric("Normas Analizadas", len(df))
m2.metric("Fenomenos Detectados", len(df_detectados))
m3.metric("Riesgo Maximo", f"{df['indice_fenomeno_corruptivo'].max()}/10")
fecha_label = archivo_selec.split("_")[-1].split(".")[0]
m4.metric("Fecha del Reporte", fecha_label)
st.divider()

# ===============================
# VISUALIZACIÓN INTERACTIVA
# ===============================
col_g1, col_g2 = st.columns(2)

with col_g1:
    st.write("### Intensidad por Escenario Teorico")
    if not df_detectados.empty:
        fig_bar = px.bar(
            df_detectados,
            x="indice_fenomeno_corruptivo",
            y="tipo_decision",
            color="nivel_riesgo_teorico",
            orientation="h",
            color_discrete_map={"Alto": "#EF553B", "Medio": "#FECB52", "Bajo": "#636EFA"},
            labels={
                "indice_fenomeno_corruptivo": "Indice de Intensidad (0-10)",
                "tipo_decision": "Escenario de la Teoria",
            },
        )
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("No hay fenomenos detectados en este reporte.")

with col_g2:
    st.write("### Sectores de Transferencia Regresiva")
    if not df_detectados.empty:
        fig_pie = px.pie(
            df_detectados, names="transferencia", hole=0.4,
            title="Distribucion de Impacto Economico",
        )
        st.plotly_chart(fig_pie, use_container_width=True)

# ===============================
# TABLA DE AUDITORÍA
# ===============================
st.write("### Explorador de Decisiones Estatales")
cols_visibles = ["fecha", "tipo_decision", "transferencia", "indice_fenomeno_corruptivo", "nivel_riesgo_teorico", "link"]
df_display = df[[c for c in cols_visibles if c in df.columns]]
st.dataframe(
    df_display,
    use_container_width=True,
    column_config={
        "link": st.column_config.LinkColumn("Norma Original"),
        "indice_fenomeno_corruptivo": st.column_config.ProgressColumn("Intensidad", min_value=0, max_value=10),
    },
)

# ===============================
# FUNDAMENTO CIENTÍFICO
# ===============================
st.divider()
with st.expander("Fundamento Cientifico y Matriz XAI", expanded=False):
    st.markdown("""
#### Nucleo de la Teoria
La corrupcion muta y se diversifica, volviendose **legal** a traves de decisiones discrecionales del Estado.

#### Los 7 Escenarios Criticos Analizados:
1. **Privatizaciones Subvaluadas**
2. **Contratos Publicos** (obras con sobreprecios)
3. **Tarifas y Devaluacion**
4. **Servicios Publicos**
5. **Salud y Educacion**
6. **Calculo Previsional** (Peso 10.0)
7. **Traslacion Impositiva**
""")
    st.info("Referencia: Monteverde, V. H. (2020). Great corruption - theory of corrupt phenomena. Journal of Financial Crime.")

st.caption(f"Sistema validado - Ph.D. Vicente Humberto Monteverde | Ejecucion: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

# ===============================
# DESCARGA DEL ARTÍCULO
# ===============================
st.divider()
col_art1, col_art2 = st.columns(2)
with col_art1:
    articulo_path = "articulo_monteverde_espanol.docx"
    if os.path.exists(articulo_path):
        with open(articulo_path, "rb") as file:
            st.download_button(
                label="Descargar Articulo Original (Word)",
                data=file,
                file_name="articulo_monteverde_espanol.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
    else:
        st.warning("El articulo no esta disponible")
