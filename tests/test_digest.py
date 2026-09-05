from unittest.mock import MagicMock

from trackeraid.digest import MODEL_VERSION, generar_digest_usuario


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
    assert resultado["convocatorias"][0]["doc_id"] == 1  # el que solapa sector, mejor puntuado

    filas_guardadas = storage.registrar_impresiones.call_args.args[2]
    assert filas_guardadas[0]["doc_id"] == 1
    assert filas_guardadas[0]["position"] == 0
    assert filas_guardadas[0]["model_version"] == MODEL_VERSION
    assert "score" in filas_guardadas[0]


def test_generar_digest_usuario_sin_cnae_en_el_perfil():
    storage = MagicMock()
    storage.buscar_convocatorias.return_value = []
    storage.afinidad_sectorial.return_value = {}
    storage.crear_digest.return_value = "digest-1"

    generar_digest_usuario(storage, {"user_id": "user-2"})

    storage.buscar_convocatorias.assert_called_once_with(cnae=None, ambito=None, limite=100)
