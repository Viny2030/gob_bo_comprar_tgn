"""
Tests del cruce con MEACI: una falla de MEACI no debe verse como "sin coincidencias".
Hasta el 03/11/2026 la URL por defecto (Railway, dada de baja) devolvía 404 para
todo y los CUIT sancionados salían limpios. Ningún test sale a la red.
"""
from fastapi.testclient import TestClient

import main
from extensiones import salud_fuentes

c = TestClient(main.app)


class _Resp:
    def __init__(self, status, ctype="application/json", cuerpo=None):
        self.status_code, self.headers, self._cuerpo = status, {"content-type": ctype}, cuerpo or {}

    def json(self):
        return self._cuerpo


class _ClienteFalso:
    def __init__(self, resp):
        self.resp = resp

    def __call__(self, *a, **k):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, *a, **k):
        return self.resp


def test_url_por_defecto_es_la_vigente():
    # main.MEACI_URL puede venir de la variable de entorno: se mira el valor por defecto del código
    assert 'os.getenv("MEACI_URL", "https://meaci.ecosistematransparencia.com.ar")' in open("main.py", encoding="utf-8").read()


def test_cruce_cuit_distingue_no_encontrado_de_meaci_caido(monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", _ClienteFalso(_Resp(404)))
    assert c.get("/api/cruce-cuit", params={"cuit": "1"}).json()["detalle"] == "sin coincidencias"
    monkeypatch.setattr(main.httpx, "AsyncClient", _ClienteFalso(_Resp(404, "text/html")))
    d = c.get("/api/cruce-cuit", params={"cuit": "1"}).json()
    assert "error" in d and "detalle" not in d


def test_cruce_bulk_informa_el_error_y_las_alertas(monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", _ClienteFalso(_Resp(404, "text/html")))
    d = c.get("/api/cruce-cuits-bulk", params={"cuits": "1,2"}).json()
    assert d["alertas"] == {} and "MEACI no disponible" in d["error"]
    sancion = {"33716578939": {"sancionada": True, "empresa": "Siemens AG"}}
    monkeypatch.setattr(main.httpx, "AsyncClient", _ClienteFalso(_Resp(200, cuerpo={"alertas": sancion})))
    d = c.get("/api/cruce-cuits-bulk", params={"cuits": "33716578939"}).json()
    assert d["total_alertas"] == 1 and "error" not in d


def test_diagnostico_detecta_meaci_dado_de_baja(monkeypatch):
    monkeypatch.setattr(salud_fuentes.requests, "get", lambda *a, **k: _Resp(404, "text/html"))
    assert salud_fuentes._probar_meaci()["alcanzable"] is False
    monkeypatch.setattr(salud_fuentes.requests, "get", lambda *a, **k: _Resp(200))
    assert salud_fuentes._probar_meaci()["alcanzable"] is True
