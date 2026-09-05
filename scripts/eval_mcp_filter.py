"""F7 — evalúa el filtro de `buscar_convocatorias` contra el gold set
etiquetado a mano (data/gold/mcp_candidates_labeled.csv).

`relevante` usa la misma escala 0/1/2 que docs/gold-labeling-criteria.md
(2=relevante, 1=parcialmente, 0=no). Igual que en run_eval.py, "relevante"
para el cálculo de precision/recall es relevante >= 1 — los casos dudosos
cuentan, no se descartan (mismo criterio ya establecido en F1).

Uso:
    python scripts/eval_mcp_filter.py
"""

from __future__ import annotations

import csv
from pathlib import Path

LABELED = Path("data/gold/mcp_candidates_labeled.csv")


def metricas(filas: list[dict]) -> dict[str, float | int]:
    tp = sum(1 for r in filas if r["_pred"] and r["_rel"])
    fp = sum(1 for r in filas if r["_pred"] and not r["_rel"])
    fn = sum(1 for r in filas if not r["_pred"] and r["_rel"])
    tn = sum(1 for r in filas if not r["_pred"] and not r["_rel"])
    total_relevantes = tp + fn
    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / total_relevantes if total_relevantes else float("nan")
    accuracy = (tp + tn) / len(filas) if filas else float("nan")
    return {
        "n": len(filas), "relevantes": total_relevantes,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": precision, "recall": recall, "accuracy": accuracy,
    }


def main() -> None:
    if not LABELED.exists():
        print(f"No existe {LABELED} todavía.")
        return

    with LABELED.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    sin_etiquetar = [r for r in rows if not r["relevante"].strip()]
    if sin_etiquetar:
        print(f"AVISO: {len(sin_etiquetar)} filas sin etiquetar todavía, se excluyen del cálculo.")

    filas = []
    for r in rows:
        if not r["relevante"].strip():
            continue
        filas.append(
            {
                **r,
                "_pred": r["prediccion_tool"].strip().lower() == "sí",
                "_rel": int(r["relevante"].strip()) >= 1,
            }
        )

    print(f"\n{'grupo':<32} | {'n':>4} | {'relev.':>6} | {'precision':>9} | {'recall':>7} | {'accuracy':>8}")
    print("-" * 80)
    grupos = sorted({(r["perfil_objetivo"], r["sector_grupo"]) for r in filas})
    for perfil, grupo in grupos:
        sub = [r for r in filas if r["perfil_objetivo"] == perfil and r["sector_grupo"] == grupo]
        m = metricas(sub)
        print(
            f"{perfil + '/' + grupo:<32} | {m['n']:>4} | {m['relevantes']:>6} | "
            f"{m['precision']:>9.3f} | {m['recall']:>7.3f} | {m['accuracy']:>8.3f}"
        )

    print("-" * 80)
    for perfil in ["negocio", "particular"]:
        sub = [r for r in filas if r["perfil_objetivo"] == perfil]
        m = metricas(sub)
        print(
            f"{'TOTAL ' + perfil:<32} | {m['n']:>4} | {m['relevantes']:>6} | "
            f"{m['precision']:>9.3f} | {m['recall']:>7.3f} | {m['accuracy']:>8.3f}"
        )

    m = metricas(filas)
    print(f"\n{'TOTAL':<32} | {m['n']:>4} | {m['relevantes']:>6} | "
          f"{m['precision']:>9.3f} | {m['recall']:>7.3f} | {m['accuracy']:>8.3f}")
    print(f"TP={m['tp']} FP={m['fp']} FN={m['fn']} TN={m['tn']}")


if __name__ == "__main__":
    main()
