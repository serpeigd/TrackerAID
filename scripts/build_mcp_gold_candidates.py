"""Gold set para evaluar `buscar_convocatorias` (servidor MCP) — genera
data/gold/mcp_candidates.csv.

A diferencia de `build_gold_candidates.py` (F1, BM25 contra una query
genérica), esto no vuelve a llamar a BDNS: usa lo ya ingerido en Supabase,
porque lo que hay que evaluar aquí es el FILTRO estructurado
(cnae + beneficiarios), no un ranking de texto libre.

Cubre los 4 grupos de sector/perfil decididos con datos reales el
2026-09-05 (ver conversación): comercio y hostelería para el perfil
'negocio'; sanitario/social y artístico/deportivo para 'particular'.

La columna `prediccion_tool` es lo que `buscar_convocatorias` decidiría
HOY (reutiliza `sector_encaja`/`perfil_encaja`, la misma lógica exacta,
no una copia) — no es el gold label. `relevante` se deja vacía a
propósito: la tiene que rellenar un humano (mismo principio que
docs/gold-labeling-criteria.md — "ninguna cifra sin denominador").

Uso:
    python scripts/build_mcp_gold_candidates.py
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from trackeraid.storage import SupabaseStorage, perfil_encaja, sector_encaja

OUT = Path("data/gold/mcp_candidates.csv")

# (perfil_objetivo, sector_grupo, palabras clave del filtro cnae)
GRUPOS: list[tuple[str, str, list[str]]] = [
    ("negocio", "comercio", ["comercio"]),
    ("negocio", "hosteleria", ["hosteler"]),
    ("particular", "sanitario_social", ["sanitari", "servicios sociales"]),
    ("particular", "artistico_deportivo", ["artístic", "deportiv", "entretenimiento"]),
]


def _coincide_grupo(sectores_doc: list[str] | None, claves: list[str]) -> bool:
    if not sectores_doc:
        return False
    return any(clave.lower() in sector.lower() for clave in claves for sector in sectores_doc)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)

    with SupabaseStorage() as storage:
        filas_raw = storage.select_raw(
            "doc_fields",
            {
                "select": "doc_id,importe,deadline,ambito,nivel1,cnae,beneficiarios,abierto,"
                "documents(title,source_url)"
            },
        )

    candidatas: list[dict[str, Any]] = []
    for perfil, grupo, claves in GRUPOS:
        for f in filas_raw:
            if not _coincide_grupo(f.get("cnae"), claves):
                continue
            prediccion = sector_encaja(f.get("cnae"), claves, f.get("nivel1")) and perfil_encaja(
                f.get("beneficiarios"), perfil
            )
            candidatas.append(
                {
                    "doc_id": f["doc_id"],
                    "perfil_objetivo": perfil,
                    "sector_grupo": grupo,
                    "titulo": f["documents"]["title"],
                    "url": f["documents"]["source_url"],
                    "cnae": " | ".join(f.get("cnae") or []),
                    "beneficiarios": f.get("beneficiarios") or "",
                    "nivel1": f.get("nivel1") or "",
                    "ambito": " | ".join(f.get("ambito") or []),
                    "importe": f.get("importe"),
                    "deadline": f.get("deadline") or "",
                    "abierto": f.get("abierto"),
                    "prediccion_tool": "sí" if prediccion else "no",
                    "relevante": "",  # a rellenar por Sergio: sí / no
                    "notas": "",
                }
            )

    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(candidatas[0].keys()))
        writer.writeheader()
        writer.writerows(candidatas)

    print(f"{len(candidatas)} candidatas escritas en {OUT}")
    for perfil, grupo, _ in GRUPOS:
        n = sum(1 for c in candidatas if c["perfil_objetivo"] == perfil and c["sector_grupo"] == grupo)
        n_si = sum(
            1
            for c in candidatas
            if c["perfil_objetivo"] == perfil and c["sector_grupo"] == grupo and c["prediccion_tool"] == "sí"
        )
        print(f"  {perfil}/{grupo}: {n} candidatas, la tool hoy diría sí a {n_si}")
    print("\n'relevante' está vacía a propósito — rellénala con sí/no. "
          "'prediccion_tool' es lo que la tool ya decide, no el gold label.")


if __name__ == "__main__":
    main()
