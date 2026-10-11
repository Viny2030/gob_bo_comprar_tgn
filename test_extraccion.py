"""Tests de extracción de avisos BORA, matriz de riesgo, cruce y límite de IA."""
import pandas as pd
import diario
from analisis import analizar_adjudicaciones, MATRIZ_LICITACIONES, MODULO_ARS

AVISO_EJERCITO = ('Texto del Aviso: EJÉRCITO ARGENTINO Objeto: "ADQUISICIÓN DE PRODUCTOS CARNICOS" '
                  'ADJUDICATARIO: TUX S.A CUIT: 30-71434715-9 POR UN TOTAL DE PESOS CIENTO SESENTA Y SEIS '
                  'MILLONES ($ 166.115.250,00) e. 14/09/2026 N° 66066/26')
AVISO_PFA = ('Texto del Aviso: Mediante RESOL-2026-137-APN-S#PFA se resolvio Adjudicar a la firma '
             'SOCIEDAD INTERNACIONAL DE REPRESENTACIONES S.A. el Renglón N° 1 (Alternativa 1) e. 15/09/2026')
AVISO_ARCA = ('Objeto de la contratación: Provisión de reactivos. Adjudicatario: REDBORDER S.A. '
              'CUIT 30715935577 Total Adjudicado: $ 47.683.300 Adjudicatario: QUIALEDO S.A.')


def test_proveedor_no_se_corta_en_sa():
    assert diario.extraer_proveedor(AVISO_EJERCITO) == "TUX S.A"
    assert diario.extraer_proveedor(AVISO_PFA).startswith("SOCIEDAD INTERNACIONAL DE REPRESENTACIONES S.A")
    assert diario.extraer_proveedor(AVISO_ARCA) == "REDBORDER S.A"


def test_monto_y_cuit():
    assert diario.extraer_monto(AVISO_EJERCITO) == "$166.115.250,00"
    assert diario.extraer_monto(AVISO_ARCA) == "$47.683.300"
    assert diario.extraer_cuit(AVISO_EJERCITO) == "30-71434715-9"
    assert diario.extraer_cuit(AVISO_ARCA) == "30715935577"
    # CUIT con dígito verificador inválido se descarta
    assert diario.extraer_cuit("CUIT 30-71434715-8") == ""


def test_monto_sin_adjudicacion_no_toma_cualquier_importe():
    assert diario.extraer_monto("CONTRATACIONES DIRECTAS MAYORES A $75.000 DE ACUERDO CON EL ART.42") == ""


def _fila(**kw):
    base = {"fecha": "2026-10-09", "organismo_contratante": "ORG", "tipo_proceso_bora": "Licitación Pública 1/26",
            "cuit_proveedor": "", "monto_adjudicado_bora": "", "link_bora": "x", "etapa": "", "alerta": ""}
    base.update(kw)
    return base


def test_sin_indicador_falso_de_mismo_dia():
    df = analizar_adjudicaciones(pd.DataFrame([_fila()]))
    assert df.iloc[0]["indicadores_riesgo"] == "✅ Sin alertas"
    assert df.iloc[0]["indice_riesgo_licit"] == 0
    assert "Velocidad Adjudicación" not in MATRIZ_LICITACIONES


def test_monto_limite_justo_bajo_el_tope():
    tope = 1_000 * MODULO_ARS
    justo = f"${int(tope * 0.95):,}".replace(",", ".")
    arriba = f"${int(tope * 1.05):,}".replace(",", ".")
    df = analizar_adjudicaciones(pd.DataFrame([_fila(monto_adjudicado_bora=justo, link_bora="a"),
                                               _fila(monto_adjudicado_bora=arriba, link_bora="b")]))
    assert "Monto Límite" in df.iloc[0]["indicadores_riesgo"]
    assert "Monto Límite" not in df.iloc[1]["indicadores_riesgo"]


def test_cruce_no_fusiona_adjudicaciones_distintas_sin_cuit():
    adj = pd.DataFrame([
        {"fecha_extraccion": "2026-10-09", "fecha_publicacion": "2026-10-09", "organismo_contratante": "BANCO DE LA NACIÓN",
         "tipo_proceso": "LP 1", "link": "l1", "proveedor_adjudicado": "", "cuit_proveedor": "", "monto_adjudicado": ""},
        {"fecha_extraccion": "2026-10-09", "fecha_publicacion": "2026-10-09", "organismo_contratante": "BANCO DE LA NACIÓN",
         "tipo_proceso": "LP 2", "link": "l2", "proveedor_adjudicado": "", "cuit_proveedor": "", "monto_adjudicado": ""},
    ])
    out = diario.cruzar_fuentes(adj, pd.DataFrame(), pd.DataFrame())
    assert len(out) == 2


def test_cruce_tgn_por_organismo_no_dice_cobro():
    adj = pd.DataFrame([{"fecha_extraccion": "2026-10-09", "fecha_publicacion": "2026-10-09",
                         "organismo_contratante": "ADMINISTRACIÓN DE PARQUES NACIONALES - DIRECCIÓN DE INFORMÁTICA",
                         "tipo_proceso": "LP 1", "link": "l1", "proveedor_adjudicado": "X S.A.",
                         "cuit_proveedor": "30-71434715-9", "monto_adjudicado": ""}])
    tgn = pd.DataFrame([{"organismo_norm": "ADMINISTRACIÓN DE PARQUES NACIONALES DIRECCIÓN DE INFORMÁTICA",
                         "cuit": "", "beneficiario": "Administración de Parques Nacionales", "monto_pagado": 1290.9}])
    out = diario.cruzar_fuentes(adj, pd.DataFrame(), tgn)
    assert out.iloc[0]["metodo_cruce_tgn"] == "organismo"
    assert "COBRÓ" not in out.iloc[0]["etapa"]
    assert "cobró" not in out.iloc[0]["alerta"]


def test_limite_ia_3_por_dia(monkeypatch):
    from fastapi.testclient import TestClient
    import main, agentic_ai
    monkeypatch.setattr(agentic_ai, "ia_disponible", lambda: True)
    monkeypatch.setattr(agentic_ai, "explicar_riesgo_licitacion", lambda fila: {"disponible": True, "explicacion": "ok"})
    main._ia_usos.update({"dia": None, "por_ip": {}, "total": 0})
    c = TestClient(main.app)
    codigos = [c.post("/api/ia/explicar-riesgo", json={}).status_code for _ in range(4)]
    assert codigos == [200, 200, 200, 429]


def test_ia_fallida_no_consume_uso(monkeypatch):
    from fastapi.testclient import TestClient
    import main, agentic_ai
    monkeypatch.setattr(agentic_ai, "ia_disponible", lambda: True)
    monkeypatch.setattr(agentic_ai, "explicar_riesgo_licitacion", lambda fila: {"disponible": False, "motivo": "error"})
    main._ia_usos.update({"dia": None, "por_ip": {}, "total": 0})
    c = TestClient(main.app)
    for _ in range(5):
        assert c.post("/api/ia/explicar-riesgo", json={}).status_code == 200
    assert main._ia_usos["total"] == 0


def test_contratacion_directa_sola_es_medio():
    df = analizar_adjudicaciones(pd.DataFrame([_fila(tipo_proceso_bora="Contratación Directa 18/26")]))
    assert df.iloc[0]["nivel_riesgo_licit"] == "Medio"
    assert df.iloc[0]["indice_riesgo_licit"] < 4
