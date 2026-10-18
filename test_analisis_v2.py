"""Tests de analisis_v2.py: divisor honesto y escenarios por palabra completa."""
import pandas as pd

from analisis import MODULO_ARS, analizar_adjudicaciones, analizar_boletin
from analisis_v2 import (analizar_adjudicaciones_v2, analizar_boletin_v2, clasificar_texto_v2,
                         peso_max_activable)


def _fila(**kw):
    base = {"fecha": "2026-10-09", "organismo_contratante": "ORG", "tipo_proceso_bora": "Licitación Pública 1/26",
            "cuit_proveedor": "", "monto_adjudicado_bora": "", "link_bora": "x", "etapa": "", "alerta": ""}
    base.update(kw)
    return base


def _monto_limite():
    return f"${int(1_000 * MODULO_ARS * 0.95):,}".replace(",", ".")


# ── Matriz de Riesgo Licitatorio ──────────────────────────────────────────────
def test_divisor_excluye_multi_organismo_sin_cuit_en_tgn():
    assert peso_max_activable(None) == 8.0
    tgn_sin_cuit = pd.DataFrame([{"cuit": "", "beneficiario": "X"}])
    assert peso_max_activable(tgn_sin_cuit) == 8.0
    tgn_con_cuit = pd.DataFrame([{"cuit": "30-71434715-9", "beneficiario": "X"}])
    assert peso_max_activable(tgn_con_cuit) == 9.5


def test_v1_no_llega_a_10_y_v2_si():
    cd = "Contratación Directa 5/26"
    filas = [_fila(tipo_proceso_bora=cd, cuit_proveedor="30-71434715-9", monto_adjudicado_bora=_monto_limite(),
                   link_bora=l) for l in ("a", "b")]
    v1 = analizar_adjudicaciones(pd.DataFrame(filas))
    v2 = analizar_adjudicaciones_v2(pd.DataFrame(filas))
    assert v1.iloc[0]["indice_riesgo_licit"] == 8.42   # 8,0 / 9,5: el máximo real de v1
    assert v2.iloc[0]["indice_riesgo_licit_v2"] == 10.0
    assert v2.iloc[0]["nivel_riesgo_licit_v2"] == "Alto"


def test_v2_conserva_columnas_originales_y_regla_cd():
    df = analizar_adjudicaciones_v2(pd.DataFrame([_fila(tipo_proceso_bora="Contratación Directa 18/26")]))
    assert df.iloc[0]["nivel_riesgo_licit"] == "Medio"       # columna original intacta
    assert df.iloc[0]["indice_riesgo_licit_v2"] == 3.75      # 3,0 / 8,0
    assert df.iloc[0]["nivel_riesgo_licit_v2"] == "Medio"    # piso de Contratación Directa


def test_v2_sin_alertas_queda_en_cero():
    df = analizar_adjudicaciones_v2(pd.DataFrame([_fila()]))
    assert df.iloc[0]["indice_riesgo_licit_v2"] == 0
    assert df.iloc[0]["nivel_riesgo_licit_v2"] == "Bajo"


# ── Matriz teórica de 7 escenarios ────────────────────────────────────────────
def test_iva_dentro_de_otra_palabra_no_es_impuesto():
    texto = "Resolución de la Dirección Ejecutiva sobre la iniciativa de capacitación."
    v1, _, _ = analizar_boletin(pd.DataFrame([{"detalle": texto}]))
    assert v1.iloc[0]["tipo_decision"] == "Traslado de Impuestos"   # falso positivo de v1
    assert clasificar_texto_v2(texto)["tipo_decision"] == "No identificado"


def test_iva_como_palabra_si_es_impuesto():
    assert clasificar_texto_v2("Se modifica la alícuota del IVA.")["tipo_decision"] == "Traslado de Impuestos"


def test_gana_el_escenario_de_mayor_peso():
    r = clasificar_texto_v2("Obra pública financiada por ANSES para la movilidad jubilatoria.")
    assert r["tipo_decision"] == "Jubilaciones / Pensiones"
    assert "Obra Pública / Contratos" in r["escenarios_detectados"]


def test_casos_de_test_auditoria_siguen_igual():
    casos = {
        "Se decreta la nueva fórmula de movilidad jubilatoria con ajuste trimestral.": "Jubilaciones / Pensiones",
        "Apruébase el nuevo cuadro tarifario para la distribución de energía eléctrica.": "Tarifas Servicios Públicos",
        "Autorízase la redeterminación de precios en la obra pública de saneamiento.": "Obra Pública / Contratos",
        "Declaración de interés cultural a la obra de teatro local.": "No identificado",
    }
    df = analizar_boletin_v2(pd.DataFrame([{"detalle": t} for t in casos]))
    assert list(df["tipo_decision"]) == list(casos.values())
