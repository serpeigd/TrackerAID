"""Métricas de calidad de retrieval sobre relevancia graduada (0/1/2).

Todas las funciones toman `ranked_relevances`: la relevancia de cada
documento en el orden en que el retriever los devolvió (no los doc_id) —
así las métricas no dependen del vocabulario de documentos y se pueden
testear con listas sintéticas.
"""

from __future__ import annotations

import math


def precision_at_k(ranked_relevances: list[int], k: int) -> float:
    """Fracción de los primeros k resultados que son relevantes (relevance >= 1)."""
    if k <= 0:
        return 0.0
    top_k = ranked_relevances[:k]
    relevantes = sum(1 for r in top_k if r >= 1)
    return relevantes / k


def recall_at_k(ranked_relevances: list[int], total_relevantes: int, k: int) -> float:
    """Fracción de TODOS los relevantes de la colección que aparecen en el top k."""
    if total_relevantes <= 0:
        return 0.0
    top_k = ranked_relevances[:k]
    relevantes = sum(1 for r in top_k if r >= 1)
    return relevantes / total_relevantes


def mrr(ranked_relevances: list[int]) -> float:
    """Reciprocal rank del primer resultado relevante (0 si no hay ninguno)."""
    for i, r in enumerate(ranked_relevances, start=1):
        if r >= 1:
            return 1.0 / i
    return 0.0


def _dcg(relevances: list[int], k: int) -> float:
    return sum(
        (2**rel - 1) / math.log2(i + 1) for i, rel in enumerate(relevances[:k], start=1)
    )


def ndcg_at_k(ranked_relevances: list[int], k: int) -> float:
    """nDCG@k con ganancia exponencial (2^rel - 1), estándar en IR."""
    dcg = _dcg(ranked_relevances, k)
    idcg = _dcg(sorted(ranked_relevances, reverse=True), k)
    return dcg / idcg if idcg > 0 else 0.0
