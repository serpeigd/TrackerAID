from datetime import UTC, datetime, timedelta

from trackeraid.ranking import puntuar, rankear


def _fecha(dias_desde_hoy: int) -> str:
    return (datetime.now(UTC).date() + timedelta(days=dias_desde_hoy)).isoformat()


def test_puntuar_sube_con_mas_solape_de_sector():
    sin_solape = {"cnae": ["AGRICULTURA"], "fecha_limite": None}
    con_solape = {"cnae": ["COMERCIO AL POR MENOR"], "fecha_limite": None}
    base = puntuar(sin_solape, cnae_perfil=["comercio"], afinidad={})
    con = puntuar(con_solape, cnae_perfil=["comercio"], afinidad={})
    assert con > base


def test_puntuar_sube_cuanto_mas_cerca_el_plazo():
    lejos = puntuar({"cnae": None, "fecha_limite": _fecha(29)}, cnae_perfil=None, afinidad={})
    cerca = puntuar({"cnae": None, "fecha_limite": _fecha(1)}, cnae_perfil=None, afinidad={})
    sin_plazo = puntuar({"cnae": None, "fecha_limite": None}, cnae_perfil=None, afinidad={})
    assert cerca > lejos > sin_plazo


def test_puntuar_no_penaliza_plazo_muy_lejano_mas_alla_del_umbral():
    umbral = puntuar({"cnae": None, "fecha_limite": _fecha(30)}, cnae_perfil=None, afinidad={})
    muy_lejos = puntuar({"cnae": None, "fecha_limite": _fecha(200)}, cnae_perfil=None, afinidad={})
    assert umbral == muy_lejos


def test_puntuar_usa_afinidad_historica_de_feedback():
    doc = {"cnae": ["HOSTELERÍA"], "fecha_limite": None}
    sin_historial = puntuar(doc, cnae_perfil=None, afinidad={})
    con_ups_previos = puntuar(doc, cnae_perfil=None, afinidad={"HOSTELERÍA": 3.0})
    con_downs_previos = puntuar(doc, cnae_perfil=None, afinidad={"HOSTELERÍA": -2.0})
    assert con_ups_previos > sin_historial > con_downs_previos


def test_rankear_ordena_por_score_desc_y_respeta_top_n():
    candidatas = [
        {"doc_id": 1, "cnae": ["AGRICULTURA"], "fecha_limite": None},
        {"doc_id": 2, "cnae": ["COMERCIO AL POR MENOR"], "fecha_limite": _fecha(1)},
        {"doc_id": 3, "cnae": ["OTROS SERVICIOS"], "fecha_limite": None},
    ]
    resultado = rankear(candidatas, cnae_perfil=["comercio"], afinidad={}, top_n=2)
    assert len(resultado) == 2
    assert resultado[0]["doc_id"] == 2  # solapa sector + plazo cercano -> el más relevante
    assert resultado[0]["score"] >= resultado[1]["score"]
    assert all("score" in c for c in resultado)
