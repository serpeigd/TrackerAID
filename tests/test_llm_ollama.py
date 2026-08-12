from datetime import date

import httpx
import pytest
import respx

from trackeraid.extraction.llm_ollama import (
    OLLAMA_URL,
    OllamaNoDisponibleError,
    calentar_modelo,
    extraer_plazo_llm,
)


@respx.mock
def test_extraer_plazo_llm_parsea_respuesta_valida():
    respx.post(OLLAMA_URL).mock(
        return_value=httpx.Response(200, json={"response": '{"fecha_fin": "2026-11-30", "sin_plazo": false}'})
    )
    r = extraer_plazo_llm("hasta finales de noviembre", fecha_referencia=date(2026, 1, 1))
    assert r.fecha_fin == date(2026, 11, 30)
    assert r.sin_plazo is False


@respx.mock
def test_extraer_plazo_llm_sin_plazo():
    respx.post(OLLAMA_URL).mock(
        return_value=httpx.Response(200, json={"response": '{"fecha_fin": null, "sin_plazo": true}'})
    )
    r = extraer_plazo_llm("convocatoria abierta de forma permanente")
    assert r.fecha_fin is None
    assert r.sin_plazo is True


@respx.mock
def test_extraer_plazo_llm_respuesta_no_json_no_rompe_el_pipeline():
    respx.post(OLLAMA_URL).mock(return_value=httpx.Response(200, json={"response": "no puedo determinarlo"}))
    r = extraer_plazo_llm("texto ambiguo")
    assert r.fecha_fin is None
    assert r.sin_plazo is False


@respx.mock
def test_extraer_plazo_llm_ollama_caido_lanza_error_explicito():
    respx.post(OLLAMA_URL).mock(side_effect=httpx.ConnectError("connection refused"))
    with pytest.raises(OllamaNoDisponibleError):
        extraer_plazo_llm("cualquier texto")


@pytest.mark.integration
def test_extraer_plazo_llm_contra_ollama_real():
    """Smoke test contra un Ollama local real (llama3.1:8b). Correr con:
    pytest -m integration
    Precondición: `ollama serve` corriendo y el modelo descargado.
    """
    calentar_modelo()
    r = extraer_plazo_llm(
        "La convocatoria permanecerá abierta mientras existan fondos disponibles, "
        "sin fecha límite establecida",
        fecha_referencia=date(2026, 8, 1),
    )
    assert r.sin_plazo is True
    assert r.fecha_fin is None
