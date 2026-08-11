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

from trackeraid.ingestion.bdns import BDNSClient, Convocatoria, ConvocatoriaDetalle

BASE_URL = "https://www.infosubvenciones.es/bdnstrans/api"

RAW_DETALLE = {
    "id": 1125953,
    "codigoBDNS": "924392",
    "descripcion": "AYUDAS A LA ASOCIACION DE CENTROS AMBIENTALES Y GRANJAS ESCUELAS",
    "presupuestoTotal": 75000,
    "abierto": True,
    "fechaInicioSolicitud": None,
    "fechaFinSolicitud": "2026-09-30",
    "tipoConvocatoria": "Concurrencia competitiva - canónica",
    "sectores": [{"descripcion": "AGRICULTURA, GANADERÍA, SILVICULTURA Y PESCA", "codigo": "A"}],
    "tiposBeneficiarios": [{"descripcion": "PERSONAS JURÍDICAS QUE NO DESARROLLAN ACTIVIDAD ECONÓMICA"}],
    "urlBasesReguladoras": "http://example.org/bases",
    "sedeElectronica": "www.euskadi.eus",
}

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
    assert sent_params["fechaDesde"] == "01/01/2026"  # BDNS exige dd/mm/yyyy aquí, no ISO
    assert sent_params["vpd"] == "GE"


@respx.mock
def test_regiones_catalogo_accepts_raw_list_response():
    respx.get(f"{BASE_URL}/regiones").mock(
        return_value=httpx.Response(200, json=[{"id": 57, "descripcion": "ES523 - Valencia / València"}])
    )
    client = BDNSClient(base_url=BASE_URL, vpd="GE")
    catalogo = client.regiones_catalogo()
    assert catalogo[0]["id"] == 57


def test_convocatoria_detalle_from_api_parses_structured_fields():
    det = ConvocatoriaDetalle.from_api(RAW_DETALLE)
    assert det.importe == 75000
    assert det.fecha_fin_solicitud == date(2026, 9, 30)
    assert det.sectores == ["AGRICULTURA, GANADERÍA, SILVICULTURA Y PESCA"]
    assert det.abierto is True


@respx.mock
def test_detalle_sends_num_conv_param():
    route = respx.get(f"{BASE_URL}/convocatorias").mock(
        return_value=httpx.Response(200, json=RAW_DETALLE)
    )
    client = BDNSClient(base_url=BASE_URL, vpd="GE")
    det = client.detalle("924392")
    assert det.id == 1125953
    assert dict(route.calls.last.request.url.params)["numConv"] == "924392"


@pytest.mark.integration
def test_ultimas_contra_la_api_real():
    """Smoke test contra la API real de BDNS (no mockeada). Correr con:
    pytest -m integration
    """
    with BDNSClient() as client:
        result = client.ultimas(page_size=5)
    assert len(result) > 0
    assert all(isinstance(c, Convocatoria) for c in result)


@pytest.mark.integration
def test_detalle_contra_la_api_real():
    with BDNSClient() as client:
        ultimas = client.ultimas(page_size=1)
        det = client.detalle(ultimas[0].numero_convocatoria)
    assert isinstance(det, ConvocatoriaDetalle)
    assert det.descripcion
