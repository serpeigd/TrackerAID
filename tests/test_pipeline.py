from datetime import date
from types import SimpleNamespace

import httpx
import respx

from trackeraid.extraction.deadline import ResultadoPlazo
from trackeraid.ingestion.bdns import ConvocatoriaDetalle
from trackeraid.pipeline import _fila_doc_fields, _fila_documento, _hash_contenido, ingerir

BDNS_URL = "https://www.infosubvenciones.es/bdnstrans/api"
SUPABASE_URL = "https://example.supabase.co"

RAW_BUSQUEDA = {
    "content": [
        {
            "id": 1,
            "numeroConvocatoria": "111",
            "descripcion": "Ayudas a pymes digitalización",
            "fechaRecepcion": "2026-08-01",
            "nivel1": "AUTONOMICA",
        }
    ]
}

RAW_DETALLE = {
    "id": 1,
    "codigoBDNS": "111",
    "descripcion": "Ayudas a pymes digitalización",
    "presupuestoTotal": 5000,
    "abierto": True,
    "fechaFinSolicitud": "2026-12-31",
    "fechaRecepcion": "2026-08-01",
    "sectores": [{"descripcion": "COMERCIO"}],
    "tiposBeneficiarios": [{"descripcion": "PYME"}],
    "regiones": [{"descripcion": "ES523 - Valencia / València"}],
    "sedeElectronica": "www.gva.es",
}


def _detalle(**overrides) -> ConvocatoriaDetalle:
    return ConvocatoriaDetalle.from_api({**RAW_DETALLE, **overrides})


def test_hash_contenido_es_estable_para_el_mismo_input():
    det = _detalle()
    assert _hash_contenido(det) == _hash_contenido(det)


def test_hash_contenido_cambia_si_cambia_el_importe():
    a = _detalle(presupuestoTotal=5000)
    b = _detalle(presupuestoTotal=6000)
    assert _hash_contenido(a) != _hash_contenido(b)


def test_fila_documento_tiene_los_campos_esperados():
    fila = _fila_documento(_detalle())
    assert fila["doc_id"] == 1
    assert fila["source"] == "bdns"
    assert fila["title"] == "Ayudas a pymes digitalización"
    assert fila["published_at"] == "2026-08-01"


def test_fila_doc_fields_incluye_plazo_resuelto_y_abierto():
    det = _detalle()
    resultado = ResultadoPlazo(fecha_fin=date(2026, 12, 31), sin_plazo=False, metodo="estructurado")
    fila = _fila_doc_fields(det, resultado)
    assert fila["deadline"] == "2026-12-31"
    assert fila["extractor_version"] == "estructurado"
    assert fila["abierto"] is True
    assert fila["ambito"] == "ES523 - Valencia / València"
    assert fila["cnae"] == ["COMERCIO"]


@respx.mock
def test_ingerir_flujo_completo_sin_llm(monkeypatch):
    # SupabaseStorage() lee trackeraid.storage.settings al construirse — se
    # sustituye por credenciales falsas para no depender de (ni arriesgar)
    # las reales del .env, aunque respx ya interceptaría la llamada igual.
    monkeypatch.setattr(
        "trackeraid.storage.settings",
        SimpleNamespace(supabase_url=SUPABASE_URL, supabase_service_role_key="fake-key"),
    )
    respx.get(f"{BDNS_URL}/convocatorias/busqueda").mock(
        side_effect=[
            httpx.Response(200, json=RAW_BUSQUEDA),
            httpx.Response(200, json={"content": []}),
        ]
    )
    respx.get(f"{BDNS_URL}/convocatorias").mock(return_value=httpx.Response(200, json=RAW_DETALLE))
    docs_route = respx.post(f"{SUPABASE_URL}/rest/v1/documents").mock(return_value=httpx.Response(201))
    fields_route = respx.post(f"{SUPABASE_URL}/rest/v1/doc_fields").mock(return_value=httpx.Response(201))

    resumen = ingerir(dias=7, con_llm=False, max_convocatorias=1)

    assert resumen.procesadas == 1
    assert resumen.guardadas == 1
    assert resumen.con_plazo_resuelto == 1
    assert resumen.metodo_llm_usado == 0
    assert docs_route.called
    assert fields_route.called
