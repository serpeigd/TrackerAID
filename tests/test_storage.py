from types import SimpleNamespace

import httpx
import pytest
import respx

from trackeraid.storage import SupabaseConfigError, SupabaseStorage

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
