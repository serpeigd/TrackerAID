from types import SimpleNamespace

import pytest

from trackeraid.auth import feedback_valido, firmar_impression_id, verificar_ingest_token


def test_verificar_ingest_token_acepta_el_token_correcto(monkeypatch):
    monkeypatch.setattr("trackeraid.auth.settings", SimpleNamespace(ingest_token="secreto-123"))
    assert verificar_ingest_token("secreto-123") is True


def test_verificar_ingest_token_rechaza_token_incorrecto(monkeypatch):
    monkeypatch.setattr("trackeraid.auth.settings", SimpleNamespace(ingest_token="secreto-123"))
    assert verificar_ingest_token("otro-valor") is False


def test_verificar_ingest_token_falla_cerrado_si_no_hay_token_configurado(monkeypatch):
    # Fail-closed a propósito: sin INGEST_TOKEN en el entorno, nadie pasa
    # -- lo contrario sería un "modo abierto" implícito por variable vacía.
    monkeypatch.setattr("trackeraid.auth.settings", SimpleNamespace(ingest_token=""))
    assert verificar_ingest_token("") is False
    assert verificar_ingest_token("cualquier-cosa") is False


def test_firmar_impression_id_es_determinista(monkeypatch):
    monkeypatch.setattr("trackeraid.auth.settings", SimpleNamespace(feedback_hmac_secret="clave-test"))
    assert firmar_impression_id("imp-1") == firmar_impression_id("imp-1")
    assert firmar_impression_id("imp-1") != firmar_impression_id("imp-2")


def test_firmar_impression_id_sin_secreto_configurado_lanza_error(monkeypatch):
    monkeypatch.setattr("trackeraid.auth.settings", SimpleNamespace(feedback_hmac_secret=""))
    with pytest.raises(RuntimeError):
        firmar_impression_id("imp-1")


def test_feedback_valido_acepta_la_firma_correcta(monkeypatch):
    monkeypatch.setattr("trackeraid.auth.settings", SimpleNamespace(feedback_hmac_secret="clave-test"))
    sig = firmar_impression_id("imp-1")
    assert feedback_valido("imp-1", sig) is True


def test_feedback_valido_rechaza_firma_de_otro_impression_id(monkeypatch):
    monkeypatch.setattr("trackeraid.auth.settings", SimpleNamespace(feedback_hmac_secret="clave-test"))
    sig_de_otro = firmar_impression_id("imp-2")
    assert feedback_valido("imp-1", sig_de_otro) is False


def test_feedback_valido_falla_cerrado_sin_secreto_o_sin_firma(monkeypatch):
    monkeypatch.setattr("trackeraid.auth.settings", SimpleNamespace(feedback_hmac_secret=""))
    assert feedback_valido("imp-1", "cualquier-firma") is False

    monkeypatch.setattr("trackeraid.auth.settings", SimpleNamespace(feedback_hmac_secret="clave-test"))
    assert feedback_valido("imp-1", "") is False
