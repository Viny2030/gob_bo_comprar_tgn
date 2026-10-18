"""
analisis_v2.py
==============
Versión revisada de las dos matrices de analisis.py, en un módulo aparte: no
cambia ningún resultado de producción. Sirve para comparar (ver
tools/recalcular_historico.py --v2) y decidir si se adopta.

Cambios respecto de analisis.py
-------------------------------
1. Matriz de Riesgo Licitatorio — divisor honesto.
   analisis.py normaliza dividiendo por la suma de los 4 pesos (9,5), pero
   "Proveedor Multi-Organismo" no puede activarse: la API de Presupuesto
   Abierto no trae CUIT del beneficiario. El índice máximo real queda en
   8,42/10. Acá se divide solo por los indicadores que pueden activarse con
   los datos disponibles (8,0 sin CUIT en TGN, 9,5 si algún día lo hay).
   Los umbrales (Alto >= 7, Medio >= 4) y la regla "Contratación Directa
   queda como mínimo en Medio" no cambian.

2. Matriz teórica de 7 escenarios — palabras completas y mayor peso.
   analisis.py busca subcadenas: "iva" coincide con "iniciativa", "ejecutiva"
   o "definitiva", y cualquier aviso de una "Dirección Ejecutiva" termina como
   "Traslado de Impuestos". Además se queda con la ÚLTIMA categoría que
   coincide, no con la de mayor peso. Acá se buscan palabras completas, se
   elige la categoría de mayor peso y se listan todas las detectadas.
   No guarda archivos (analizar_boletin sí).
"""
import re

import pandas as pd

from analisis import (MATRIZ_LICITACIONES, MATRIZ_TEORICA, analizar_adjudicaciones,
                      evaluar_riesgo, limpiar_texto_curado)


# ── 1. Matriz de Riesgo Licitatorio ───────────────────────────────────────────
def indicadores_activables(df_tgn=None) -> list:
    """Indicadores que pueden activarse con los datos de este día."""
    activos = ["Contratación Directa", "Proveedor Único", "Monto Límite"]
    hay_cuit_tgn = (df_tgn is not None and not df_tgn.empty and "cuit" in df_tgn.columns
                    and df_tgn["cuit"].astype(str).str.strip().ne("").any())
    if hay_cuit_tgn:
        activos.append("Proveedor Multi-Organismo")
    return activos


def peso_max_activable(df_tgn=None) -> float:
    return sum(MATRIZ_LICITACIONES[n]["peso"] for n in indicadores_activables(df_tgn))


def analizar_adjudicaciones_v2(df_adjudicaciones, df_tgn=None):
    """
    Corre la matriz de analisis.py (mismos indicadores y puntajes) y agrega:
        indice_riesgo_licit_v2  — puntaje / peso máximo activable × 10
        nivel_riesgo_licit_v2   — Alto / Medio / Bajo con los mismos umbrales
    Las columnas originales quedan intactas para comparar.
    """
    df = analizar_adjudicaciones(df_adjudicaciones, df_tgn)
    if df is None or df.empty:
        return df
    divisor = peso_max_activable(df_tgn)
    df["indice_riesgo_licit_v2"] = df["score_riesgo_licit"].apply(
        lambda s: round(min(float(s) / divisor * 10, 10), 2))
    df["nivel_riesgo_licit_v2"] = df["indice_riesgo_licit_v2"].apply(evaluar_riesgo)
    es_cd = df["indicadores_riesgo"].str.contains("Contratación Directa", na=False)
    df.loc[es_cd & (df["nivel_riesgo_licit_v2"] == "Bajo"), "nivel_riesgo_licit_v2"] = "Medio"
    return df


# ── 2. Matriz teórica de 7 escenarios ─────────────────────────────────────────
_PATRONES = {
    categoria: re.compile(r"\b(?:" + "|".join(re.escape(k) for k in info["keywords"]) + r")\b")
    for categoria, info in MATRIZ_TEORICA.items()
}


def clasificar_texto_v2(texto: str) -> dict:
    """Clasifica un texto en el escenario de mayor peso cuyas palabras aparecen completas."""
    limpio = limpiar_texto_curado(texto)
    detectados = [c for c, patron in _PATRONES.items() if patron.search(limpio)]
    if not detectados:
        return {"tipo_decision": "No identificado", "transferencia": "No identificado",
                "indice_fenomeno_corruptivo": 0.0, "escenarios_detectados": ""}
    principal = max(detectados, key=lambda c: MATRIZ_TEORICA[c]["peso"])
    return {"tipo_decision": principal,
            "transferencia": MATRIZ_TEORICA[principal]["transferencia"],
            "indice_fenomeno_corruptivo": MATRIZ_TEORICA[principal]["peso"],
            "escenarios_detectados": " | ".join(detectados)}


def analizar_boletin_v2(df):
    """Igual entrada que analisis.analizar_boletin (columna 'detalle'); no escribe archivos."""
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    clasif = df["detalle"].fillna("").astype(str).apply(clasificar_texto_v2).apply(pd.Series)
    for col in clasif.columns:
        df[col] = clasif[col]
    df["nivel_riesgo_teorico"] = df["indice_fenomeno_corruptivo"].apply(evaluar_riesgo)
    return df
