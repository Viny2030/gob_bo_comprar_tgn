"""Qué se puede afirmar a partir del cruce con TGN.

Presupuesto Abierto no informa el CUIT del beneficiario. Una coincidencia por nombre
de organismo dice que ese organismo tuvo pagos en el año, no que el proveedor adjudicado
haya cobrado. Sólo una coincidencia por CUIT permite decir "cobró".

Los reportes guardados antes de esta corrección tienen `cobro_en_tgn = SÍ` por organismo,
y algunos también etapa y alerta "cobró". No se modifican los Excel: este módulo corrige
lo que muestra el sitio al leerlos.
"""
import pandas as pd

SI = "✅ SÍ"
NO = "❌ NO"
ETAPA_ORGANISMO = "💰 ADJUDICADO + ORGANISMO CON PAGOS TGN"
ALERTA_ORGANISMO = "🔶 BORA + TGN (por organismo)"


def _si(valor) -> bool:
    return "SÍ" in str(valor or "")


def normalizar_fila(fila: dict) -> dict:
    """Devuelve una copia en la que "cobró" sólo queda si el cruce fue por CUIT."""
    if not any(c in fila for c in ("cobro_en_tgn", "etapa", "alerta")):
        return fila
    r = dict(fila)
    por_cuit = str(r.get("metodo_cruce_tgn") or "").strip().upper() == "CUIT"

    if "cobro_en_tgn" in r:
        hubo_pagos = _si(r.get("cobro_en_tgn")) or _si(r.get("organismo_con_pagos_tgn"))
        r["organismo_con_pagos_tgn"] = SI if hubo_pagos else NO
        if not por_cuit:
            r["cobro_en_tgn"] = NO

    if not por_cuit:
        if "COBRÓ" in str(r.get("etapa") or ""):
            r["etapa"] = ETAPA_ORGANISMO
        if "cobró" in str(r.get("alerta") or ""):
            r["alerta"] = ALERTA_ORGANISMO
    return r


def normalizar_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    if not any(c in df.columns for c in ("cobro_en_tgn", "etapa", "alerta")):
        return df
    return pd.DataFrame([normalizar_fila(f) for f in df.to_dict(orient="records")])
