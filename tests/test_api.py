from unittest.mock import patch

from fastapi.testclient import TestClient

from trackeraid.api import app
from trackeraid.pipeline import ResumenIngesta

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_pipeline_ingest_devuelve_el_resumen():
    resumen_falso = ResumenIngesta(procesadas=5, guardadas=5, con_plazo_resuelto=4, metodo_llm_usado=1)
    with patch("trackeraid.api.ingerir", return_value=resumen_falso) as mock_ingerir:
        r = client.post("/pipeline/ingest", json={"dias": 7, "con_llm": True, "max_convocatorias": 50})
    assert r.status_code == 200
    body = r.json()
    assert body["procesadas"] == 5
    assert body["guardadas"] == 5
    assert body["metodo_llm_usado"] == 1
    mock_ingerir.assert_called_once_with(dias=7, con_llm=True, max_convocatorias=50)


def test_pipeline_ingest_usa_valores_por_defecto():
    resumen_falso = ResumenIngesta()
    with patch("trackeraid.api.ingerir", return_value=resumen_falso) as mock_ingerir:
        r = client.post("/pipeline/ingest", json={})
    assert r.status_code == 200
    mock_ingerir.assert_called_once_with(dias=14, con_llm=True, max_convocatorias=200)


def test_pipeline_ingest_rechaza_dias_fuera_de_rango():
    r = client.post("/pipeline/ingest", json={"dias": 0})
    assert r.status_code == 422


def test_pipeline_ingest_traduce_excepcion_a_500_con_detalle():
    with patch("trackeraid.api.ingerir", side_effect=RuntimeError("BDNS caído")):
        r = client.post("/pipeline/ingest", json={})
    assert r.status_code == 500
    assert "BDNS caído" in r.json()["detail"]
