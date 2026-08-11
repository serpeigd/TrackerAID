"""Tests del cliente BDNS.

Los tests unitarios mockean HTTP con respx (deterministas, corren en CI).
El test marcado `integration` golpea la API real de BDNS: sirve para
detectar si el contrato (no documentado oficialmente) cambia, pero no
corre en CI por defecto porque depende de red y de un tercero.
"""

from datetime import date

import httpx
import pytest
import respx

from trackeraid.ingestion.bdns import BDNSClient, Convocatoria

BASE_URL = "https://www.infosubvenciones.es/bdnstrans/api"

RAW_ITEM = {
    "id": 1125953,
    "mrr": False,
    "numeroConvocatoria": "924392",
    "descripcion": "AYUDAS A LA ASOCIACION DE CENTROS AMBIENTALES Y GRANJAS ESCUELAS",
    "descripcionLeng": None,
    "fechaRecepcion": "2026-08-10",
    "nivel1": "AUTONOMICA",
    "nivel2": "PAÍS VASCO",
    "nivel3": "DEPARTAMENTO DE ALIMENTACIÓN, DESARROLLO RURAL, AGRICULTURA Y PESCA",
    "codigoInvente": None,
}


def test_convocatoria_from_api_parses_fields():
    conv = Convocatoria.from_api(RAW_ITEM)
    assert conv.id == 1125953
    assert conv.numero_convocatoria == "924392"
    assert conv.fecha_recepcion == date(2026, 8, 10)
    assert conv.nivel1 == "AUTONOMICA"


@respx.mock
def test_ultimas_parses_list_response():
    respx.get(f"{BASE_URL}/convocatorias/ultimas").mock(
        return_value=httpx.Response(200, json={"content": [RAW_ITEM]})
    )
    client = BDNSClient(base_url=BASE_URL, vpd="GE")
    result = client.ultimas(page_size=1)
    assert len(result) == 1
    assert result[0].id == 1125953


@respx.mock
def test_buscar_sends_expected_query_params():
    route = respx.get(f"{BASE_URL}/convocatorias/busqueda").mock(
        return_value=httpx.Response(200, json={"content": [RAW_ITEM]})
    )
    client = BDNSClient(base_url=BASE_URL, vpd="GE")
    result = client.buscar(
        descripcion="digitalización",
        regiones=[55, 56, 57],
        fecha_desde=date(2026, 1, 1),
        page_size=10,
    )
    assert len(result) == 1
    sent_params = dict(route.calls.last.request.url.params)
    assert sent_params["descripcion"] == "digitalización"
    assert sent_params["regiones"] == "55,56,57"
    assert sent_params["fechaDesde"] == "2026-01-01"
    assert sent_params["vpd"] == "GE"


@respx.mock
def test_regiones_catalogo_accepts_raw_list_response():
    respx.get(f"{BASE_URL}/regiones").mock(
        return_value=httpx.Response(200, json=[{"id": 57, "descripcion": "ES523 - Valencia / València"}])
    )
    client = BDNSClient(base_url=BASE_URL, vpd="GE")
    catalogo = client.regiones_catalogo()
    assert catalogo[0]["id"] == 57


@pytest.mark.integration
def test_ultimas_contra_la_api_real():
    """Smoke test contra la API real de BDNS (no mockeada). Correr con:
    pytest -m integration
    """
    with BDNSClient() as client:
        result = client.ultimas(page_size=5)
    assert len(result) > 0
    assert all(isinstance(c, Convocatoria) for c in result)
