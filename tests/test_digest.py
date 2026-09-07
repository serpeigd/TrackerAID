from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from trackeraid.auth import feedback_valido
from trackeraid.digest import MODEL_VERSION, generar_digest_usuario


@pytest.fixture(autouse=True)
def _feedback_secret(monkeypatch):
    # digest.py firma cada impression_id con auth.firmar_impression_id --
    # sin secreto configurado, lanzaría RuntimeError (fail-closed, ver auth.py).
    monkeypatch.setattr(
        "trackeraid.auth.settings",
        SimpleNamespace(feedback_hmac_secret="test-secret", ingest_token=""),
    )


def test_generar_digest_usuario_orquesta_buscar_rankear_y_guardar():
    storage = MagicMock()
    storage.buscar_convocatorias.return_value = [
        {"doc_id": 1, "cnae": ["COMERCIO"], "fecha_limite": None},
        {"doc_id": 2, "cnae": ["AGRICULTURA"], "fecha_limite": None},
    ]
    storage.afinidad_sectorial.return_value = {}
    storage.crear_digest.return_value = "digest-xyz"

    perfil = {"user_id": "user-1", "cnae": ["comercio"], "ambito": "ES523"}
    resultado = generar_digest_usuario(storage, perfil, top_n=1)

    storage.buscar_convocatorias.assert_called_once_with(cnae=["comercio"], ambito="ES523", limite=100)
    storage.afinidad_sectorial.assert_called_once_with("user-1")
    storage.crear_digest.assert_called_once_with("user-1", n_items=1)

    assert resultado["digest_id"] == "digest-xyz"
    assert resultado["n_items"] == 1
    convocatoria = resultado["convocatorias"][0]
    assert convocatoria["doc_id"] == 1  # el que solapa sector, mejor puntuado

    # impression_id generado en Python (no lo asigna Supabase) y firmado con
    # HMAC -- así el enlace de feedback se puede componer sin releer la fila.
    assert "impression_id" in convocatoria
    assert feedback_valido(convocatoria["impression_id"], convocatoria["feedback_sig"]) is True

    filas_guardadas = storage.registrar_impresiones.call_args.args[2]
    assert filas_guardadas[0]["doc_id"] == 1
    assert filas_guardadas[0]["position"] == 0
    assert filas_guardadas[0]["model_version"] == MODEL_VERSION
    assert filas_guardadas[0]["impression_id"] == convocatoria["impression_id"]
    assert "score" in filas_guardadas[0]


def test_generar_digest_usuario_sin_cnae_en_el_perfil():
    storage = MagicMock()
    storage.buscar_convocatorias.return_value = []
    storage.afinidad_sectorial.return_value = {}
    storage.crear_digest.return_value = "digest-1"

    generar_digest_usuario(storage, {"user_id": "user-2"})

    storage.buscar_convocatorias.assert_called_once_with(cnae=None, ambito=None, limite=100)
