"""F1 — corre el baseline BM25 sobre el gold set y reporta las métricas.

Usa la columna `relevance` de data/gold/candidates.csv si Sergio ya la ha
revisado; si está vacía, cae a `heuristic_relevance` y lo dice a gritos en
la salida — esos números NO son el resultado final del harness, solo
sirven para comprobar que el mecanismo funciona de punta a punta.

Uso:
    python scripts/run_eval.py [--k 5,10,20]
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from trackeraid.retrieval import (
    BM25Retriever,
    Documento,
    mrr,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)

CANDIDATES = Path("data/gold/candidates.csv")

# Consulta fija que representa el perfil genérico "autónomo/pyme de la
# Comunitat Valenciana" (ver docs/gold-labeling-criteria.md). Personalizar
# por perfil real es trabajo de F6 (reranker), no de este baseline.
QUERY_GENERICA = (
    "ayudas subvenciones autónomos pymes Comunitat Valenciana inversión "
    "digitalización comercio hostelería agricultura empresas"
)


def cargar_corpus_y_relevancias() -> tuple[list[Documento], dict[int, int], bool]:
    with CANDIDATES.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    usa_provisional = not any(r["relevance"].strip() for r in rows)
    columna = "heuristic_relevance" if usa_provisional else "relevance"

    documentos, relevancias = [], {}
    for r in rows:
        valor = r[columna].strip()
        if not valor:
            continue  # fila sin etiqueta en la columna elegida -> fuera del eval
        doc_id = int(r["doc_id"])
        texto = " ".join([r["descripcion"], r["tipos_beneficiarios"], r["sectores"]])
        documentos.append(Documento(doc_id=doc_id, texto=texto))
        relevancias[doc_id] = int(valor)

    return documentos, relevancias, usa_provisional


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--k", default="5,10,20")
    args = parser.parse_args()
    ks = [int(k) for k in args.k.split(",")]

    documentos, relevancias, provisional = cargar_corpus_y_relevancias()
    if not documentos:
        print("No hay filas etiquetadas todavía. Nada que evaluar.")
        return

    retriever = BM25Retriever(documentos)
    ranking = retriever.buscar(QUERY_GENERICA)
    ranked_relevances = [relevancias[doc_id] for doc_id, _score in ranking]
    total_relevantes = sum(1 for v in relevancias.values() if v >= 1)

    if provisional:
        print("=" * 78)
        print("AVISO: 'relevance' está vacía todavía -> usando 'heuristic_relevance'.")
        print("Estos NO son los resultados finales del harness, solo confirman que")
        print("el mecanismo (tokenizar, indexar, rankear, medir) funciona de punta a")
        print("punta. Los números reales llegan cuando se revise el CSV a mano.")
        print("=" * 78)

    print(f"\nDocumentos evaluados: {len(documentos)} | relevantes (rel>=1): {total_relevantes}")
    print(f"{'k':>4} | {'precision@k':>12} | {'recall@k':>10} | {'nDCG@k':>8}")
    for k in ks:
        p = precision_at_k(ranked_relevances, k)
        r = recall_at_k(ranked_relevances, total_relevantes, k)
        n = ndcg_at_k(ranked_relevances, k)
        print(f"{k:>4} | {p:>12.3f} | {r:>10.3f} | {n:>8.3f}")
    print(f"\nMRR: {mrr(ranked_relevances):.3f}")


if __name__ == "__main__":
    main()
