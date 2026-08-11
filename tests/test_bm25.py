import pytest

from trackeraid.retrieval.bm25 import BM25Retriever, Documento, tokenize


def test_tokenize_lowercases_and_strips_accents():
    assert tokenize("Ayudas a la Innovación y Digitalización") == [
        "ayudas", "la", "innovacion", "digitalizacion",
    ]


def test_tokenize_drops_single_char_tokens():
    assert "a" not in tokenize("ayudas a la pyme")


def test_buscar_ranks_matching_document_first():
    docs = [
        Documento(doc_id=1, texto="Subvención nominativa a Cáritas Parroquial"),
        Documento(doc_id=2, texto="Ayudas a pymes para digitalización empresarial"),
        Documento(doc_id=3, texto="Premio literario Ciudad de Algemesí"),
    ]
    retriever = BM25Retriever(docs)
    resultados = retriever.buscar("ayudas digitalización pymes", top_k=3)
    assert resultados[0][0] == 2
    assert len(resultados) == 3


def test_buscar_respects_top_k():
    docs = [Documento(doc_id=i, texto=f"documento numero {i} sobre pymes") for i in range(5)]
    retriever = BM25Retriever(docs)
    assert len(retriever.buscar("pymes", top_k=2)) == 2


def test_empty_corpus_raises():
    with pytest.raises(ValueError):
        BM25Retriever([])
