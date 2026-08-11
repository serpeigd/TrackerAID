"""Baseline BM25 para retrieval sobre convocatorias.

Primer escalón de la tabla de ablación prometida en el README (BM25 /
embeddings / híbrido / +reranker). Tokenización simple: minúsculas, sin
tildes, split en no-alfanumérico — sin stopwords ni stemming todavía.
Es la línea base contra la que se compararán embeddings e híbrido, no
la versión final.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from rank_bm25 import BM25Okapi


def tokenize(text: str) -> list[str]:
    normalizado = unicodedata.normalize("NFKD", text.lower())
    sin_tildes = "".join(c for c in normalizado if not unicodedata.combining(c))
    return [tok for tok in re.findall(r"[a-z0-9]+", sin_tildes) if len(tok) > 1]


@dataclass
class Documento:
    doc_id: int
    texto: str


class BM25Retriever:
    """Retriever BM25 sobre una colección fija de documentos en memoria."""

    def __init__(self, documentos: list[Documento]):
        if not documentos:
            raise ValueError("BM25Retriever necesita al menos un documento")
        self._doc_ids = [d.doc_id for d in documentos]
        tokenized = [tokenize(d.texto) for d in documentos]
        self._bm25 = BM25Okapi(tokenized)

    def buscar(self, query: str, top_k: int | None = None) -> list[tuple[int, float]]:
        """Devuelve (doc_id, score) ordenados de mayor a menor score."""
        scores = self._bm25.get_scores(tokenize(query))
        ranking = sorted(zip(self._doc_ids, scores, strict=True), key=lambda x: x[1], reverse=True)
        return ranking[:top_k] if top_k else ranking
