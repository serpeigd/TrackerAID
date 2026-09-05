from types import SimpleNamespace

import httpx
import pytest
import respx

from trackeraid.storage import (
    SupabaseConfigError,
    SupabaseStorage,
    ambito_encaja,
    es_premio_o_concurso,
)

BASE_URL = "https://example.supabase.co"


def test_falla_con_config_vacia(monkeypatch):
    # url/key vacíos explícitos caen al fallback de settings (comportamiento
    # correcto: SupabaseStorage() sin argumentos debe leer del entorno) —
    # para probar el caso "sin configurar de verdad" hay que sustituir el
    # objeto settings entero (es un dataclass frozen, no se puede mutar).
    monkeypatch.setattr(
        "trackeraid.storage.settings",
        SimpleNamespace(supabase_url="", supabase_service_role_key=""),
    )
    with pytest.raises(SupabaseConfigError):
        SupabaseStorage()


def test_falla_sin_key_aunque_haya_url(monkeypatch):
    monkeypatch.setattr(
        "trackeraid.storage.settings",
        SimpleNamespace(supabase_url="", supabase_service_role_key=""),
    )
    with pytest.raises(SupabaseConfigError):
        SupabaseStorage(url=BASE_URL)


@respx.mock
def test_upsert_documents_envia_prefer_merge_duplicates():
    route = respx.post(f"{BASE_URL}/rest/v1/documents").mock(return_value=httpx.Response(201))
    storage = SupabaseStorage(url=BASE_URL, service_role_key="fake-key")
    n = storage.upsert_documents([{"doc_id": 1, "title": "x", "raw_hash": "abc"}])
    assert n == 1
    sent = route.calls.last.request
    assert sent.headers["Prefer"] == "resolution=merge-duplicates,return=minimal"
    assert sent.headers["apikey"] == "fake-key"
    assert "on_conflict=doc_id" in str(sent.url)


@respx.mock
def test_upsert_con_lista_vacia_no_hace_peticion():
    route = respx.post(f"{BASE_URL}/rest/v1/documents")
    storage = SupabaseStorage(url=BASE_URL, service_role_key="fake-key")
    n = storage.upsert_documents([])
    assert n == 0
    assert route.call_count == 0


@respx.mock
def test_contar_lee_content_range():
    respx.head(f"{BASE_URL}/rest/v1/documents").mock(
        return_value=httpx.Response(200, headers={"content-range": "0-0/450"})
    )
    storage = SupabaseStorage(url=BASE_URL, service_role_key="fake-key")
    assert storage.contar("documents") == 450


@respx.mock
def test_buscar_convocatorias_estatal_siempre_encaja_ignora_cnae():
    respx.get(f"{BASE_URL}/rest/v1/doc_fields").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "doc_id": 1,
                    "importe": 1000,
                    "deadline": "2026-12-01",
                    "ambito": None,
                    "nivel1": "ESTATAL",
                    "cnae": ["INDUSTRIA"],
                    "documents": {"title": "Estatal", "source_url": "u1", "published_at": "2026-01-01"},
                },
                {
                    "doc_id": 2,
                    "importe": 500,
                    "deadline": "2026-11-01",
                    "ambito": ["ES523 - Valencia / València"],
                    "nivel1": "AUTONOMICA",
                    # Real de BDNS: descripción larga, mayúsculas inconsistentes,
                    # nunca la palabra suelta que buscaría un usuario.
                    "cnae": ["COMERCIO AL POR MAYOR Y AL POR MENOR"],
                    "documents": {"title": "Autonómica coincide", "source_url": "u2", "published_at": "2026-01-01"},
                },
                {
                    "doc_id": 3,
                    "importe": None,
                    "deadline": None,
                    "ambito": None,
                    "nivel1": "AUTONOMICA",
                    "cnae": ["Agricultura, ganadería, caza y servicios relacionados con las mismas"],
                    "documents": {"title": "Autonómica no coincide", "source_url": "u3", "published_at": "2026-01-01"},
                },
            ],
        )
    )
    storage = SupabaseStorage(url=BASE_URL, service_role_key="fake-key")
    # Palabra corta, en minúscula: así busca de verdad un usuario o un agente,
    # no la descripción completa de BDNS.
    resultado = storage.buscar_convocatorias(cnae=["comercio"])

    # doc 3 no encaja (AUTONOMICA + cnae sin relación) -> fuera
    assert [r["doc_id"] for r in resultado] == [2, 1]
    # orden por deadline ascendente
    assert resultado[0]["fecha_limite"] == "2026-11-01"
    assert resultado[0]["titulo"] == "Autonómica coincide"
    assert resultado[0]["url"] == "u2"
    # cnae va en la respuesta -> se puede depurar por qué algo entró o no
    assert resultado[0]["cnae"] == ["COMERCIO AL POR MAYOR Y AL POR MENOR"]


@respx.mock
def test_buscar_convocatorias_sin_filtro_cnae_no_descarta_nada():
    respx.get(f"{BASE_URL}/rest/v1/doc_fields").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "doc_id": 3,
                    "importe": None,
                    "deadline": None,
                    "ambito": None,
                    "nivel1": "AUTONOMICA",
                    "cnae": ["AGRICULTURA"],
                    "documents": {"title": "Sin filtro", "source_url": "u3", "published_at": "2026-01-01"},
                },
            ],
        )
    )
    storage = SupabaseStorage(url=BASE_URL, service_role_key="fake-key")
    resultado = storage.buscar_convocatorias()
    assert len(resultado) == 1
    assert resultado[0]["fecha_limite"] is None


@respx.mock
def test_buscar_convocatorias_perfil_negocio_excluye_asociaciones_sin_pyme():
    respx.get(f"{BASE_URL}/rest/v1/doc_fields").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "doc_id": 1,
                    "importe": None,
                    "deadline": None,
                    "ambito": None,
                    "nivel1": None,
                    "cnae": None,
                    # Real de BDNS: asociaciones/clubes, no autónomos ni pymes.
                    "beneficiarios": "PERSONAS JURÍDICAS QUE NO DESARROLLAN ACTIVIDAD ECONÓMICA",
                    "documents": {"title": "Solo asociaciones", "source_url": "u1", "published_at": None},
                },
                {
                    "doc_id": 2,
                    "importe": None,
                    "deadline": None,
                    "ambito": None,
                    "nivel1": None,
                    "cnae": None,
                    "beneficiarios": "PYME Y PERSONAS FÍSICAS QUE DESARROLLAN ACTIVIDAD ECONÓMICA",
                    "documents": {"title": "Pyme", "source_url": "u2", "published_at": None},
                },
                {
                    "doc_id": 3,
                    "importe": None,
                    "deadline": None,
                    "ambito": None,
                    "nivel1": None,
                    "cnae": None,
                    "beneficiarios": None,  # desconocido -> permisivo
                    "documents": {"title": "Sin dato", "source_url": "u3", "published_at": None},
                },
            ],
        )
    )
    storage = SupabaseStorage(url=BASE_URL, service_role_key="fake-key")

    negocio = storage.buscar_convocatorias(perfil="negocio")
    assert {r["doc_id"] for r in negocio} == {2, 3}

    particular = storage.buscar_convocatorias(perfil="particular")
    assert {r["doc_id"] for r in particular} == {1, 3}


def test_ambito_encaja_estatal_siempre_encaja_ignora_provincia():
    assert ambito_encaja(["ES521 - Alicante / Alacant"], "ESTATAL", "ES523") is True


def test_ambito_encaja_sin_codigo_de_provincia_reconocido_es_permisivo():
    # Texto libre heredado ("Comunitat Valenciana") o vacío: sin filtro,
    # para no ocultar nada a un perfil que aún no se ha guardado con el
    # desplegable nuevo.
    assert ambito_encaja(["ES521 - Alicante / Alacant"], "LOCAL", "Comunitat Valenciana") is True
    assert ambito_encaja(["ES521 - Alicante / Alacant"], "LOCAL", None) is True


def test_ambito_encaja_convocatoria_sin_ambito_conocido_es_permisiva():
    assert ambito_encaja(None, "LOCAL", "ES523") is True


def test_ambito_encaja_filtra_de_verdad_con_codigo_de_provincia():
    assert ambito_encaja(["ES523 - Valencia / València"], "LOCAL", "ES523") is True
    assert ambito_encaja(["ES521 - Alicante / Alacant"], "LOCAL", "ES523") is False


@respx.mock
def test_buscar_convocatorias_filtra_por_provincia_del_ambito():
    respx.get(f"{BASE_URL}/rest/v1/doc_fields").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "doc_id": 1,
                    "importe": None,
                    "deadline": None,
                    "ambito": ["ES523 - Valencia / València"],
                    "nivel1": "LOCAL",
                    "cnae": None,
                    "documents": {"title": "Valencia", "source_url": "u1", "published_at": None},
                },
                {
                    "doc_id": 2,
                    "importe": None,
                    "deadline": None,
                    "ambito": ["ES521 - Alicante / Alacant"],
                    "nivel1": "LOCAL",
                    "cnae": None,
                    "documents": {"title": "Alicante", "source_url": "u2", "published_at": None},
                },
                {
                    "doc_id": 3,
                    "importe": None,
                    "deadline": None,
                    "ambito": None,
                    "nivel1": "ESTATAL",
                    "cnae": None,
                    "documents": {"title": "Estatal", "source_url": "u3", "published_at": None},
                },
            ],
        )
    )
    storage = SupabaseStorage(url=BASE_URL, service_role_key="fake-key")

    solo_valencia = storage.buscar_convocatorias(ambito="ES523")
    assert {r["doc_id"] for r in solo_valencia} == {1, 3}  # 2 (Alicante) queda fuera, 3 (ESTATAL) siempre entra

    sin_filtro = storage.buscar_convocatorias(ambito="Comunitat Valenciana")  # valor heredado -> permisivo
    assert {r["doc_id"] for r in sin_filtro} == {1, 2, 3}


def test_es_premio_o_concurso_detecta_las_tres_palabras():
    assert es_premio_o_concurso("Premios al uso del valenciano en el comercio local") is True
    assert es_premio_o_concurso("Concurso de escaparatismo y ambientación comercial") is True
    assert es_premio_o_concurso("Certamen Benicàssim Belle Époque - fotografía") is True


def test_es_premio_o_concurso_no_afecta_a_una_ayuda_real():
    assert es_premio_o_concurso("Ayudas a la digitalización de pymes del comercio minorista") is False


@respx.mock
def test_buscar_convocatorias_excluye_premios_y_concursos():
    respx.get(f"{BASE_URL}/rest/v1/doc_fields").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "doc_id": 1,
                    "importe": None,
                    "deadline": None,
                    "ambito": None,
                    "nivel1": None,
                    "cnae": ["COMERCIO AL POR MAYOR Y AL POR MENOR"],
                    "documents": {
                        "title": "Premios al uso del valenciano en el comercio local 2026",
                        "source_url": "u1",
                        "published_at": None,
                    },
                },
                {
                    "doc_id": 2,
                    "importe": None,
                    "deadline": None,
                    "ambito": None,
                    "nivel1": None,
                    "cnae": ["COMERCIO AL POR MAYOR Y AL POR MENOR"],
                    "documents": {
                        "title": "Ayudas a la digitalización del comercio minorista",
                        "source_url": "u2",
                        "published_at": None,
                    },
                },
            ],
        )
    )
    storage = SupabaseStorage(url=BASE_URL, service_role_key="fake-key")
    resultado = storage.buscar_convocatorias(cnae=["comercio"])
    assert [r["doc_id"] for r in resultado] == [2]


@respx.mock
def test_buscar_convocatorias_respeta_el_limite():
    filas = [
        {
            "doc_id": i,
            "importe": None,
            "deadline": None,
            "ambito": None,
            "nivel1": None,
            "cnae": None,
            "documents": {"title": f"Conv {i}", "source_url": None, "published_at": None},
        }
        for i in range(5)
    ]
    respx.get(f"{BASE_URL}/rest/v1/doc_fields").mock(return_value=httpx.Response(200, json=filas))
    storage = SupabaseStorage(url=BASE_URL, service_role_key="fake-key")
    resultado = storage.buscar_convocatorias(limite=2)
    assert len(resultado) == 2


@respx.mock
def test_crear_digest_devuelve_el_digest_id():
    respx.post(f"{BASE_URL}/rest/v1/digests").mock(
        return_value=httpx.Response(201, json=[{"digest_id": "abc-123"}])
    )
    storage = SupabaseStorage(url=BASE_URL, service_role_key="fake-key")
    digest_id = storage.crear_digest("user-1", n_items=5)
    assert digest_id == "abc-123"


@respx.mock
def test_registrar_impresiones_incluye_digest_id_y_user_id():
    route = respx.post(f"{BASE_URL}/rest/v1/impressions").mock(return_value=httpx.Response(201))
    storage = SupabaseStorage(url=BASE_URL, service_role_key="fake-key")
    n = storage.registrar_impresiones(
        "digest-1",
        "user-1",
        [{"doc_id": 42, "position": 0, "score": 1.5, "model_version": "v1", "features_json": {}}],
    )
    assert n == 1
    enviado = route.calls.last.request.content
    assert b'"digest_id":"digest-1"' in enviado
    assert b'"user_id":"user-1"' in enviado


@respx.mock
def test_registrar_impresiones_con_lista_vacia_no_hace_peticion():
    route = respx.post(f"{BASE_URL}/rest/v1/impressions")
    storage = SupabaseStorage(url=BASE_URL, service_role_key="fake-key")
    assert storage.registrar_impresiones("digest-1", "user-1", []) == 0
    assert route.call_count == 0


@respx.mock
def test_registrar_feedback_envia_impression_id_y_label():
    route = respx.post(f"{BASE_URL}/rest/v1/feedback").mock(return_value=httpx.Response(201))
    storage = SupabaseStorage(url=BASE_URL, service_role_key="fake-key")
    storage.registrar_feedback("impresion-1", "up")
    enviado = route.calls.last.request.content
    assert b'"impression_id":"impresion-1"' in enviado
    assert b'"label":"up"' in enviado


@respx.mock
def test_afinidad_sectorial_suma_up_resta_down_ignora_clicked():
    # Dos llamadas reales, no un embed anidado -- impressions no tiene FK
    # a doc_fields (ver docstring de afinidad_sectorial).
    respx.get(f"{BASE_URL}/rest/v1/feedback").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"label": "up", "impressions": {"doc_id": 1}},
                {"label": "up", "impressions": {"doc_id": 2}},
                {"label": "down", "impressions": {"doc_id": 1}},
                {"label": "clicked", "impressions": {"doc_id": 1}},
            ],
        )
    )
    respx.get(f"{BASE_URL}/rest/v1/doc_fields").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"doc_id": 1, "cnae": ["HOSTELERÍA"]},
                {"doc_id": 2, "cnae": ["HOSTELERÍA", "COMERCIO"]},
            ],
        )
    )
    storage = SupabaseStorage(url=BASE_URL, service_role_key="fake-key")
    afinidad = storage.afinidad_sectorial("user-1")
    assert afinidad["HOSTELERÍA"] == 1.0  # doc 1: +1 -1 = 0; doc 2: +1 -> total 1
    assert afinidad["COMERCIO"] == 1.0


@respx.mock
def test_afinidad_sectorial_sin_feedback_no_llama_a_doc_fields():
    respx.get(f"{BASE_URL}/rest/v1/feedback").mock(return_value=httpx.Response(200, json=[]))
    route_doc_fields = respx.get(f"{BASE_URL}/rest/v1/doc_fields")
    storage = SupabaseStorage(url=BASE_URL, service_role_key="fake-key")
    assert storage.afinidad_sectorial("user-1") == {}
    assert route_doc_fields.call_count == 0


@pytest.mark.integration
def test_upsert_y_contar_contra_supabase_real():
    """Smoke test contra el Supabase real del proyecto. Correr con:
    pytest -m integration
    Requiere SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en .env.
    """
    with SupabaseStorage() as storage:
        antes = storage.contar("documents")
        n = storage.upsert_documents(
            [{"doc_id": 999999999, "title": "smoke test", "raw_hash": "smoke-test-hash"}]
        )
        assert n == 1
        despues = storage.contar("documents")
        assert despues >= antes
