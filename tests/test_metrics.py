"""Tests de las métricas de retrieval con valores calculados a mano.

Caso de referencia usado en varios tests: ranked_relevances = [0, 2, 0, 1, 0]
(un sistema devuelve 5 documentos; el 2º es muy relevante, el 4º algo
relevante). total_relevantes en la colección = 2 (los índices con rel >= 1).
"""

import math

import pytest

from trackeraid.retrieval.metrics import mrr, ndcg_at_k, precision_at_k, recall_at_k

RANKED = [0, 2, 0, 1, 0]
TOTAL_RELEVANTES = 2  # los dos documentos con relevance >= 1 en toda la colección


def test_precision_at_k():
    assert precision_at_k(RANKED, k=1) == 0.0  # top1 = [0]
    assert precision_at_k(RANKED, k=3) == pytest.approx(1 / 3)  # top3 = [0,2,0] -> 1 relevante
    assert precision_at_k(RANKED, k=0) == 0.0


def test_recall_at_k():
    assert recall_at_k(RANKED, TOTAL_RELEVANTES, k=1) == 0.0
    assert recall_at_k(RANKED, TOTAL_RELEVANTES, k=3) == pytest.approx(0.5)  # 1 de 2
    assert recall_at_k(RANKED, TOTAL_RELEVANTES, k=5) == pytest.approx(1.0)  # los 2
    assert recall_at_k(RANKED, total_relevantes=0, k=5) == 0.0


def test_mrr():
    assert mrr(RANKED) == pytest.approx(0.5)  # primer relevante en posición 2
    assert mrr([0, 0, 0]) == 0.0
    assert mrr([1, 0, 0]) == 1.0


def test_ndcg_at_k_hand_computed():
    # DCG@3 = (2^0-1)/log2(2) + (2^2-1)/log2(3) + (2^0-1)/log2(4) = 0 + 3/log2(3) + 0
    dcg3 = 3 / math.log2(3)
    # Orden ideal: [2,1,0,0,0] -> IDCG@3 = 3/log2(2) + 1/log2(3) + 0 = 3 + 1/log2(3)
    idcg3 = 3 / math.log2(2) + 1 / math.log2(3)
    esperado = dcg3 / idcg3
    assert ndcg_at_k(RANKED, k=3) == pytest.approx(esperado)


def test_ndcg_at_k_perfect_ranking_is_one():
    assert ndcg_at_k([2, 1, 0], k=3) == pytest.approx(1.0)


def test_ndcg_at_k_no_relevant_docs_is_zero():
    assert ndcg_at_k([0, 0, 0], k=3) == 0.0
