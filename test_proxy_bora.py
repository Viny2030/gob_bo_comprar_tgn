"""
Tests del proxy para el BORA (BORA_PROXY_URL). Ningún test sale a la red.
"""
import diario
from extensiones import salud_fuentes

PROXY = "http://usuario:clave_country-ar@geo.ejemplo.com:12321"


def test_sin_proxy_configurado_todo_va_directo(monkeypatch):
    monkeypatch.delenv("BORA_PROXY_URL", raising=False)
    assert diario.proxies_para("https://www.boletinoficial.gob.ar/seccion/tercera/20261103") is None


def test_solo_el_bora_sale_por_el_proxy(monkeypatch):
    monkeypatch.setenv("BORA_PROXY_URL", PROXY)
    esperado = {"http": PROXY, "https": PROXY}
    assert diario.proxies_para("https://www.boletinoficial.gob.ar/pdf/aviso/tercera/1/20261103") == esperado
    assert diario.proxies_para("https://boletinoficial.gob.ar:443/") == esperado
    assert diario.proxies_para("https://comprar.gob.ar/Compras.aspx") is None
    assert diario.proxies_para("https://www.presupuestoabierto.gob.ar/api/v1/credito") is None
    assert diario.proxies_para("https://boletinoficial.gob.ar.otro.com/") is None


def test_los_errores_no_muestran_la_clave_del_proxy():
    texto = f"ProxyError: no se pudo conectar a {PROXY} (timeout)"
    limpio = diario.sin_credenciales(texto)
    assert "clave_country-ar" not in limpio and "usuario" not in limpio
    assert "http://***@geo.ejemplo.com:12321" in limpio


def test_get_con_reintentos_pasa_el_proxy(monkeypatch):
    monkeypatch.setenv("BORA_PROXY_URL", PROXY)
    llamadas = []

    class _Resp:
        def raise_for_status(self):
            pass

    def falso_get(url, **kw):
        llamadas.append(kw.get("proxies"))
        return _Resp()
    monkeypatch.setattr(diario.requests, "get", falso_get)
    diario.get_con_reintentos("https://www.boletinoficial.gob.ar/seccion/tercera/20261103")
    diario.get_con_reintentos("https://comprar.gob.ar/Compras.aspx")
    assert llamadas == [{"http": PROXY, "https": PROXY}, None]


def test_diagnostico_del_bora_usa_el_proxy(monkeypatch):
    monkeypatch.setenv("BORA_PROXY_URL", PROXY)
    usados = []

    def falso_get(url, **kw):
        usados.append(kw.get("proxies"))
        return type("R", (), {"status_code": 200})()
    monkeypatch.setattr(salud_fuentes.requests, "get", falso_get)
    r = salud_fuentes._probar_bora()
    assert r["alcanzable"] is True and r["via_proxy"] is True and usados[0]["https"] == PROXY
