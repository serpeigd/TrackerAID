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
