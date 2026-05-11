# ── REEMPLAZAR en main.py estas dos funciones ────────────────────────────────

def cargar_ultimo_reporte():
    global _df_cache
    if _df_cache is not None and not _df_cache.empty:
        return _df_cache
    archivos = buscar_todos_los_xlsx(DATA_DIR)
    if not archivos:
        return pd.DataFrame()
    try:
        xl = pd.ExcelFile(archivos[0])
        # Prioridad: hoja con datos XAI → flujo cruzado → cualquiera
        hojas = ["⚠️ Riesgo Licitatorio", "🚨 Flujo Completo", "🔗 Flujo Cruzado", "Sheet1"]
        hoja = next((h for h in hojas if h in xl.sheet_names), xl.sheet_names[0])
        return xl.parse(hoja)
    except Exception as e:
        print(f"Error cargando reporte: {e}")
        return pd.DataFrame()


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    archivos = buscar_todos_los_xlsx(DATA_DIR)
    df = cargar_ultimo_reporte()

    total = len(df) if not df.empty else 0

    # ── Detectar qué columnas tiene el DataFrame ──────────────────────────
    # Hoja "⚠️ Riesgo Licitatorio": indice_riesgo_licit, nivel_riesgo_licit, tipo_proceso_bora
    # Hoja "🚨 Flujo Completo":     alerta, nivel_riesgo_licit, organismo_contratante
    # Hoja XAI original:            indice_fenomeno_corruptivo, nivel_riesgo_teorico, tipo_decision

    tiene_xai    = not df.empty and "indice_fenomeno_corruptivo" in df.columns
    tiene_licit  = not df.empty and "indice_riesgo_licit" in df.columns
    tiene_flujo  = not df.empty and "alerta" in df.columns

    # ── Índice promedio ───────────────────────────────────────────────────
    if tiene_xai:
        indice_prom = round(pd.to_numeric(df["indice_fenomeno_corruptivo"], errors="coerce").mean(), 2)
    elif tiene_licit:
        indice_prom = round(pd.to_numeric(df["indice_riesgo_licit"], errors="coerce").mean(), 2)
    else:
        indice_prom = 0

    # ── Alertas alto riesgo ───────────────────────────────────────────────
    if tiene_xai and "nivel_riesgo_teorico" in df.columns:
        alto_riesgo = int(len(df[df["nivel_riesgo_teorico"] == "Alto"]))
    elif tiene_licit and "nivel_riesgo_licit" in df.columns:
        alto_riesgo = int(len(df[df["nivel_riesgo_licit"] == "Alto"]))
    else:
        alto_riesgo = 0

    # ── Distribución por tipo (gráfico barras) ────────────────────────────
    if tiene_xai and "tipo_decision" in df.columns:
        tipo_counts = df["tipo_decision"].value_counts().to_dict()
    elif tiene_licit and "tipo_proceso_bora" in df.columns:
        tipo_counts = df["tipo_proceso_bora"].fillna("Sin tipo").value_counts().to_dict()
    elif tiene_flujo and "alerta" in df.columns:
        tipo_counts = df["alerta"].value_counts().to_dict()
    else:
        tipo_counts = {}

    # ── Distribución por nivel de riesgo (gráfico dona) ───────────────────
    if tiene_xai and "nivel_riesgo_teorico" in df.columns:
        riesgo_counts = df["nivel_riesgo_teorico"].value_counts().to_dict()
    elif tiene_licit and "nivel_riesgo_licit" in df.columns:
        riesgo_counts = df["nivel_riesgo_licit"].value_counts().to_dict()
    else:
        riesgo_counts = {}

    # ── Tabla del dashboard ───────────────────────────────────────────────
    tabla = []
    if not df.empty:
        if tiene_xai:
            # Hoja XAI original — columnas nativas
            cols = ["nro_proceso", "detalle", "tipo_decision",
                    "indice_fenomeno_corruptivo", "nivel_riesgo_teorico"]
            tabla = df[[c for c in cols if c in df.columns]].head(50).fillna("n/a").to_dict(orient="records")
        else:
            # Hoja flujo cruzado — mapear columnas al formato que espera el template
            df_tabla = df.head(50).copy()
            tabla = []
            for _, row in df_tabla.iterrows():
                tabla.append({
                    "nro_proceso":               row.get("nro_proceso_comprar", row.get("aviso_id", "n/a")),
                    "detalle":                   row.get("organismo_contratante", row.get("beneficiario_tgn", "n/a")),
                    "tipo_decision":             row.get("tipo_proceso_bora", row.get("alerta", "n/a")),
                    "indice_fenomeno_corruptivo": row.get("indice_riesgo_licit", row.get("score_riesgo_licit", 0)),
                    "nivel_riesgo_teorico":       row.get("nivel_riesgo_licit", "Bajo"),
                })

    ga_id = os.getenv("GA_MEASUREMENT_ID", "")
    return templates.TemplateResponse(request, "dashboard.html", {
        "total":          total,
        "indice_prom":    indice_prom if not (isinstance(indice_prom, float) and pd.isna(indice_prom)) else 0,
        "alto_riesgo":    alto_riesgo,
        "total_reportes": len(archivos),
        "tipo_counts":    tipo_counts,
        "riesgo_counts":  riesgo_counts,
        "tabla":          tabla,
        "sin_datos":      df.empty,
        "ultimo_reporte": etiqueta_archivo(archivos[0]) if archivos else "Sin reportes — ejecute Análisis en Vivo",
        "ga_id":          ga_id,
    })
