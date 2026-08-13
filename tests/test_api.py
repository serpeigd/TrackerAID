from unittest.mock import patch

from fastapi.testclient import TestClient

from trackeraid.api import app
from trackeraid.pipeline import ResumenIngesta

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_pipeline_ingest_responde_al_instante_202():
    with patch("trackeraid.api.ingerir", return_value=ResumenIngesta()):
        r = client.post("/pipeline/ingest", json={"dias": 7, "con_llm": True, "max_convocatorias": 50})
    assert r.status_code == 202
    assert r.json()["iniciado"] is True


def test_pipeline_ingest_usa_valores_por_defecto():
    with patch("trackeraid.api.ingerir", return_value=ResumenIngesta()) as mock_ingerir:
        client.post("/pipeline/ingest", json={})
        # TestClient ejecuta las BackgroundTasks antes de devolver la respuesta
        mock_ingerir.assert_called_once_with(dias=14, con_llm=True, max_convocatorias=200)


def test_pipeline_ingest_rechaza_dias_fuera_de_rango():
    r = client.post("/pipeline/ingest", json={"dias": 0})
    assert r.status_code == 422


def test_status_refleja_una_ingesta_completada():
    resumen_falso = ResumenIngesta(procesadas=5, guardadas=5, con_plazo_resuelto=4, metodo_llm_usado=1)
    with patch("trackeraid.api.ingerir", return_value=resumen_falso):
        client.post("/pipeline/ingest", json={})

    r = client.get("/pipeline/status")
    assert r.status_code == 200
    body = r.json()
    assert body["estado"] == "completado"
    assert body["resumen"]["procesadas"] == 5
    assert body["resumen"]["metodo_llm_usado"] == 1
    assert body["error"] is None


def test_status_refleja_un_fallo_sin_tumbar_el_proceso():
    with patch("trackeraid.api.ingerir", side_effect=RuntimeError("BDNS caído")):
        r = client.post("/pipeline/ingest", json={})
    assert r.status_code == 202  # la petición se acepta igual, el fallo es asíncrono

    r = client.get("/pipeline/status")
    body = r.json()
    assert body["estado"] == "error"
    assert "BDNS caído" in body["error"]


def test_status_antes_de_lanzar_nada_es_inactivo():
    # Import fresco del módulo para no arrastrar estado de tests anteriores
    import importlib

    import trackeraid.api as api_module

    importlib.reload(api_module)
    fresh_client = TestClient(api_module.app)
    r = fresh_client.get("/pipeline/status")
    assert r.json()["estado"] == "inactivo"


def test_marcar_inicio_deja_estado_en_curso_antes_de_marcar_completado():
    # Verifica el estado intermedio directamente sobre el objeto, sin
    # depender de condiciones de carrera con un hilo real.
    from trackeraid.api import _EstadoPipeline

    estado = _EstadoPipeline()
    assert estado.estado == "inactivo"
    estado.marcar_inicio()
    assert estado.estado == "en_curso"
    assert estado.resumen is None
    estado.marcar_completado(ResumenIngesta(procesadas=1))
    assert estado.estado == "completado"
    assert estado.resumen.procesadas == 1


def test_marcar_error_no_lanza_excepcion():
    from trackeraid.api import _EstadoPipeline

    estado = _EstadoPipeline()
    estado.marcar_inicio()
    estado.marcar_error("boom")
    assert estado.estado == "error"
    assert estado.error == "boom"
    assert estado.terminado_en is not None
