"""Tests de app_extendida.py: protección de ejecuciones, respaldos, descargas y estado."""
import os

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import app_extendida  # registra router y middleware sobre main.app
import main
from extensiones import proteccion
from extensiones.zona_horaria import hoy_ar_str

CLAVE = "clave-de-prueba"
PASADO = "2026-10-16"


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    """DATA_DIR y RESPALDOS_DIR temporales; el pipeline real nunca corre."""
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(main, "DATA_DIR", str(data))
    monkeypatch.setenv("RESPALDOS_DIR", str(tmp_path / "respaldos"))
    monkeypatch.setattr(main, "ADMIN_KEY", CLAVE)
    corridas = []
    monkeypatch.setattr(main, "_ejecutar_pipeline_licitaciones",
                        lambda fecha: corridas.append(fecha) or {"status": "ok", "fecha": fecha})
    main._analisis_job.clear()
    main._analisis_job.update({"corriendo": False, "fecha": None, "resultado": None,
                               "error": None, "iniciado_en": None})
    return {"data": data, "respaldos": tmp_path / "respaldos", "corridas": corridas}


def _crear_reporte(data_dir, fecha, filas=2):
    carpeta = data_dir / fecha[:7]
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"reporte_{fecha}.xlsx"
    with pd.ExcelWriter(ruta, engine="openpyxl") as w:
        pd.DataFrame({"organismo_contratante": ["ORG"] * filas, "cuit_proveedor": ["30715935577"] * filas,
                      "nivel_riesgo_licit": ["Medio"] * filas, "alerta": ["📋 SOLO BORA"] * filas,
                      "indice_riesgo_licit": [3.16] * filas}).to_excel(w, sheet_name="🚨 Flujo Completo", index=False)
        pd.DataFrame({"organismo": ["ORG"], "aviso_id": ["1"], "link": ["l"]}).to_excel(
            w, sheet_name="📰 BORA Licitaciones", index=False)
    return ruta


def test_pasado_con_reporte_sin_clave_es_403(entorno):
    _crear_reporte(entorno["data"], PASADO)
    r = TestClient(main.app).post(f"/api/licitaciones/ejecutar?fecha={PASADO}")
    assert r.status_code == 403
    assert "ya tiene un reporte" in r.json()["detail"]
    assert entorno["corridas"] == []


def test_pasado_con_reporte_y_clave_respalda_y_ejecuta(entorno):
    _crear_reporte(entorno["data"], PASADO)
    c = TestClient(main.app)
    r = c.post(f"/api/licitaciones/ejecutar?fecha={PASADO}", headers={"X-Admin-Key": CLAVE})
    assert r.status_code == 202
    respaldos = os.listdir(entorno["respaldos"] / PASADO[:7])
    assert len(respaldos) == 1 and respaldos[0].startswith(f"reporte_{PASADO}__")


def test_respaldo_identico_no_se_duplica(entorno):
    _crear_reporte(entorno["data"], PASADO)
    proteccion.respaldar_dia(PASADO)
    assert proteccion.respaldar_dia(PASADO) == []


def test_cookie_de_admin_tambien_vale(entorno):
    _crear_reporte(entorno["data"], PASADO)
    c = TestClient(main.app)
    c.cookies.set(main.ADMIN_COOKIE, CLAVE)
    assert c.post(f"/api/licitaciones/ejecutar?fecha={PASADO}").status_code == 202


def test_clave_incorrecta_es_403(entorno):
    _crear_reporte(entorno["data"], PASADO)
    r = TestClient(main.app).post(f"/api/licitaciones/ejecutar?fecha={PASADO}", headers={"X-Admin-Key": "otra"})
    assert r.status_code == 403


def test_pasado_sin_reporte_no_requiere_clave(entorno):
    r = TestClient(main.app).post("/api/licitaciones/ejecutar?fecha=2026-10-12")
    assert r.status_code == 202


def test_hoy_no_requiere_clave(entorno):
    r = TestClient(main.app).post(f"/api/licitaciones/ejecutar?fecha={hoy_ar_str()}")
    assert r.status_code == 202


def test_fecha_invalida_la_responde_main(entorno):
    r = TestClient(main.app).post("/api/licitaciones/ejecutar?fecha=16-10-2026")
    assert r.status_code == 400


def test_analisis_programatico_requiere_clave(entorno):
    assert TestClient(main.app).post("/api/analisis").status_code == 403


def test_sin_admin_key_configurada_nadie_pisa_reportes(entorno, monkeypatch):
    monkeypatch.setattr(main, "ADMIN_KEY", "")
    _crear_reporte(entorno["data"], PASADO)
    r = TestClient(main.app).post(f"/api/licitaciones/ejecutar?fecha={PASADO}", headers={"X-Admin-Key": ""})
    assert r.status_code == 403


def test_descarga_de_reporte(entorno):
    _crear_reporte(entorno["data"], PASADO)
    c = TestClient(main.app)
    r = c.get(f"/api/reporte/{PASADO}/excel")
    assert r.status_code == 200 and r.content[:2] == b"PK"
    assert c.get(f"/api/reporte/{PASADO}/excel?tipo=flujo").status_code == 404
    assert c.get("/api/reporte/16-10-2026/excel").status_code == 400
    assert c.get(f"/api/reporte/{PASADO}/excel?tipo=otro").status_code == 400


def test_estado_sistema(entorno):
    _crear_reporte(entorno["data"], PASADO)
    c = TestClient(main.app)
    e = c.get("/api/estado-sistema").json()
    assert e["ultimo_reporte"]["fecha"] == PASADO
    assert e["ultimo_reporte"]["hojas"]["🚨 Flujo Completo"] == 2
    assert e["proteccion_ejecuciones"] is True
    assert c.get("/estado").status_code == 200


def test_ia_usos(entorno):
    main._ia_usos.update({"dia": None, "por_ip": {}, "total": 0})
    r = TestClient(main.app).get("/api/ia/usos").json()
    assert r["restantes_hoy"] == main.IA_LIMITE_POR_IP


def test_sincronizar_db_requiere_clave(entorno):
    assert TestClient(main.app).post("/api/admin/sincronizar-db").status_code == 403


def test_leer_dia_para_la_base(entorno):
    from extensiones.sincronizacion import fechas_disponibles, leer_dia
    _crear_reporte(entorno["data"], PASADO, filas=3)
    dia = leer_dia(str(entorno["data"]), PASADO)
    assert dia["resumen"]["total_cruce"] == 3
    assert dia["resumen"]["riesgo_medio"] == 3
    assert dia["resumen"]["total_licit"] == 1
    assert dia["df_cruce"]["cuit_proveedor"].iloc[0] == "30715935577"   # sin pasar a número
    assert fechas_disponibles(str(entorno["data"])) == [PASADO]


def test_manual_v2(entorno):
    c = TestClient(main.app)
    assert c.get("/manual-v2").status_code == 200
    assert c.get("/api/descargar-manual-v2-es").status_code == 200
    assert c.get("/api/descargar-manual-v2-en").status_code == 200
