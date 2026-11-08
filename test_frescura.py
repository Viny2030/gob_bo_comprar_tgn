"""/api/frescura: reporte diario."""
from fastapi.testclient import TestClient

import main


def test_frescura_comprar():
    d = TestClient(main.app).get("/api/frescura").json()
    assert d["formato"] == "frescura/1" and d["sitio"] == "comprar"
    assert [x["id"] for x in d["datos"]] == ["reportes"]
