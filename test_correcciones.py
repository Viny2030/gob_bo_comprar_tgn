"""Tests de la segunda tanda: menú, manual, hora de Argentina, caché y tabla del dashboard."""
import re

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import app_extendida  # noqa: F401  (registra /estado y el resto de las extensiones)
import main

PAGINAS = ["/", "/licitaciones", "/analisis-vivo", "/documentacion", "/manual", "/estado"]


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(main, "db_pool", None)
    monkeypatch.setattr(main, "_df_cache", None)
    monkeypatch.setattr(main, "_df_cache_archivo", None)
    return TestClient(main.app)


def _reporte(data_dir, fecha, filas):
    carpeta = data_dir / fecha[:7]
    carpeta.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(carpeta / f"reporte_{fecha}.xlsx", engine="openpyxl") as w:
        pd.DataFrame(filas).to_excel(w, sheet_name="🚨 Flujo Completo", index=False)


@pytest.mark.parametrize("ruta", PAGINAS)
def test_menu_completo_y_un_solo_activo(cliente, ruta):
    html = cliente.get(ruta).text
    nav = re.search(r"<nav>(.*?)</nav>", html, re.S).group(1)
    for href in ["/", "/licitaciones", "/analisis-vivo", "/documentacion", "/manual", "/estado", "/docs"]:
        assert f'href="{href}"' in nav, f"falta {href} en el menú de {ruta}"
    assert nav.count('class="active"') == 1


def test_manual_es_el_corregido_y_el_anterior_sigue_disponible(cliente):
    assert "Matriz de Riesgo Licitatorio" in cliente.get("/manual").text
    assert cliente.get("/manual-anterior").status_code == 200


def test_dias_disponibles_usa_la_fecha_de_argentina(cliente, monkeypatch):
    monkeypatch.setattr(main, "hoy_ar_str", lambda: "2026-03-01")
    assert cliente.get("/api/dias-disponibles").json()["dias_todos"][-1] == "2026-03-01"


def test_dashboard_sin_nan(cliente, tmp_path):
    _reporte(tmp_path, "2026-10-16", [{"organismo_contratante": "ARCA", "nro_proceso_comprar": None,
                                       "aviso_id": "123", "tipo_proceso_bora": "Licitación Pública",
                                       "indice_riesgo_licit": 0, "nivel_riesgo_licit": "Bajo"}])
    html = cliente.get("/").text
    assert ">nan<" not in html.replace(" ", "").replace("\n", "")
    assert "123" in html


def test_cache_se_descarta_con_un_reporte_nuevo(cliente, tmp_path):
    _reporte(tmp_path, "2026-10-15", [{"organismo_contratante": "VIEJO"}])
    main.set_cache(pd.DataFrame([{"detalle": "cache", "indice_fenomeno_corruptivo": 1.0}]))
    assert list(main.cargar_ultimo_reporte()["detalle"]) == ["cache"]
    _reporte(tmp_path, "2026-10-16", [{"organismo_contratante": "NUEVO"}])
    assert list(main.cargar_ultimo_reporte()["organismo_contratante"]) == ["NUEVO"]
