"""Una coincidencia por organismo no puede mostrarse como que el proveedor cobró."""
import glob
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import diario  # noqa: E402
from extensiones.cobro_tgn import ALERTA_ORGANISMO, ETAPA_ORGANISMO, NO, SI, normalizar_df, normalizar_fila  # noqa: E402

RAIZ = os.path.dirname(os.path.abspath(__file__))


def test_reporte_viejo_por_organismo_deja_de_decir_cobro():
    r = normalizar_fila({
        "cobro_en_tgn": SI, "metodo_cruce_tgn": "organismo",
        "etapa": "💰 ADJUDICADO + COBRÓ", "alerta": "🔶 BORA + TGN (cobró)",
    })
    assert r["cobro_en_tgn"] == NO
    assert r["organismo_con_pagos_tgn"] == SI
    assert r["etapa"] == ETAPA_ORGANISMO
    assert r["alerta"] == ALERTA_ORGANISMO


def test_sin_metodo_no_se_afirma_el_cobro():
    r = normalizar_fila({"cobro_en_tgn": SI, "etapa": "💰 ADJUDICADO + COBRÓ"})
    assert r["cobro_en_tgn"] == NO and "COBRÓ" not in r["etapa"]


def test_hoja_de_riesgo_sin_columna_de_cobro_tambien_se_corrige():
    r = normalizar_fila({"etapa": "💰 ADJUDICADO + COBRÓ", "alerta": "🔶 BORA + TGN (cobró)"})
    assert r["etapa"] == ETAPA_ORGANISMO and r["alerta"] == ALERTA_ORGANISMO
    assert "cobro_en_tgn" not in r


def test_coincidencia_por_cuit_se_conserva():
    f = {"cobro_en_tgn": SI, "metodo_cruce_tgn": "CUIT",
         "etapa": "💰 ADJUDICADO + COBRÓ", "alerta": "🔶 BORA + TGN (cobró)"}
    r = normalizar_fila(f)
    assert r["cobro_en_tgn"] == SI and r["organismo_con_pagos_tgn"] == SI
    assert r["etapa"] == f["etapa"] and r["alerta"] == f["alerta"]


def test_otras_etapas_y_hojas_no_cambian():
    f = {"etapa": "✅ ADJUDICADO (sin pago aún)", "cobro_en_tgn": NO, "metodo_cruce_tgn": ""}
    assert normalizar_fila(f)["etapa"] == f["etapa"]
    assert normalizar_fila(f)["organismo_con_pagos_tgn"] == NO
    otra = {"organismo": "X", "categoria": "Y"}
    assert normalizar_fila(otra) == otra
    assert normalizar_df(pd.DataFrame([otra])).to_dict(orient="records") == [otra]


def test_cruce_nuevo_por_organismo_no_marca_cobro():
    adj = pd.DataFrame([{
        "fecha_publicacion": "2026-11-06",
        "organismo_contratante": "ADMINISTRACIÓN DE PARQUES NACIONALES",
        "tipo_proceso": "LP 1", "link": "l1", "proveedor_adjudicado": "X SA",
        "cuit_proveedor": "30-71434715-9", "monto_adjudicado": "",
    }])
    tgn = pd.DataFrame([{
        "organismo_norm": "ADMINISTRACIÓN DE PARQUES NACIONALES DIRECCIÓN",
        "cuit": "", "beneficiario": "Administración de Parques Nacionales", "monto_pagado": 10.0,
    }])
    fila = diario.cruzar_fuentes(adj, pd.DataFrame(), tgn).iloc[0]
    assert fila["metodo_cruce_tgn"] == "organismo"
    assert fila["cobro_en_tgn"] == NO
    assert fila["organismo_con_pagos_tgn"] == SI


def test_ningun_reporte_publicado_afirma_cobro_al_leerlo():
    """Sobre los Excel reales: después de normalizar, ninguna fila dice que cobró."""
    archivos = sorted(glob.glob(os.path.join(RAIZ, "data", "*", "reporte_*.xlsx")))
    assert archivos
    import main
    con_etiqueta = 0
    for ruta in archivos:
        for fila in main.leer_hoja(ruta, ["🚨 Flujo Completo", "🔗 Flujo Cruzado"]):
            if str(fila.get("metodo_cruce_tgn", "")).upper() == "CUIT":
                continue
            assert "SÍ" not in str(fila.get("cobro_en_tgn", ""))
            assert "COBRÓ" not in str(fila.get("etapa", ""))
            assert "cobró" not in str(fila.get("alerta", ""))
            con_etiqueta += "SÍ" in str(fila.get("organismo_con_pagos_tgn", ""))
    assert con_etiqueta > 0


def test_la_pagina_no_presenta_coincidencias_como_cobros():
    with open(os.path.join(RAIZ, "templates", "licitaciones.html"), encoding="utf-8") as f:
        pagina = f.read()
    assert "Cobros en TGN" not in pagina
    assert "'Cobró TGN'" not in pagina
    assert "Cobros TGN" not in pagina
    assert "r.cobro_en_tgn.includes" not in pagina
