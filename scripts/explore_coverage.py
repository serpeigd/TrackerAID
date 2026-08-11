"""F1 — mide qué % de convocatorias de la Comunitat Valenciana traen ya
estructurados los campos clave (importe, plazo, sector) frente a los que
solo están en el PDF/texto libre.

Esta cifra decide cuánto trabajo de extracción con LLM hace falta en F2:
si la mayoría de campos ya vienen en la API, las reglas bastan y el LLM
es innecesario para esos campos (más barato, más rápido, sin alucinación
posible). Resultado -> docs/f1-coverage-report.md.

Uso:
    python scripts/explore_coverage.py [--sample N] [--dias N]

Nota: este script SOBRESCRIBE docs/f1-coverage-report.md por completo. Si
se ha añadido análisis manual al informe (hallazgos de producto, bugs de
la API encontrados a mano), cópialo aparte antes de volver a ejecutar.
"""

from __future__ import annotations

import argparse
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from trackeraid.ingestion.bdns import REGIONES_COMUNITAT_VALENCIANA, BDNSClient

RAW_OUT = Path("data/raw/bdns_cv_sample.jsonl")
REPORT_OUT = Path("docs/f1-coverage-report.md")


def recolectar_resumenes(client: BDNSClient, dias: int, objetivo: int) -> list:
    fecha_desde = datetime.now(UTC).date() - timedelta(days=dias)
    resumenes, page = [], 0
    region_ids = list(REGIONES_COMUNITAT_VALENCIANA.values())
    while len(resumenes) < objetivo:
        lote = client.buscar(regiones=region_ids, fecha_desde=fecha_desde, page=page, page_size=50)
        if not lote:
            break
        resumenes.extend(lote)
        page += 1
    return resumenes[:objetivo]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=200)
    parser.add_argument("--dias", type=int, default=90)
    args = parser.parse_args()

    RAW_OUT.parent.mkdir(parents=True, exist_ok=True)

    with BDNSClient() as client:
        resumenes = recolectar_resumenes(client, args.dias, args.sample)
        print(f"Resúmenes recogidos (CV, últimos {args.dias} días): {len(resumenes)}")

        detalles = []
        for i, r in enumerate(resumenes, 1):
            if not r.numero_convocatoria:
                continue
            try:
                det = client.detalle(r.numero_convocatoria)
                detalles.append(det)
            except (httpx.HTTPStatusError, httpx.TransportError) as e:
                # se descarta la ficha suelta y se sigue con el resto de la muestra
                print(f"  [{i}/{len(resumenes)}] fallo en {r.numero_convocatoria}: {e}")
            if i % 25 == 0:
                print(f"  [{i}/{len(resumenes)}] procesadas")
            time.sleep(0.15)  # ser buen ciudadano con una API pública gratuita

    n = len(detalles)
    con_importe = sum(1 for d in detalles if d.importe is not None)
    con_plazo = sum(1 for d in detalles if d.fecha_fin_solicitud is not None)
    con_sector = sum(1 for d in detalles if d.sectores)
    abiertas = sum(1 for d in detalles if d.abierto)

    with RAW_OUT.open("w", encoding="utf-8") as f:
        for d in detalles:
            f.write(d.model_dump_json() + "\n")

    def pct(x: int) -> str:
        return f"{100 * x / n:.1f}%" if n else "n/a"

    report = f"""# Cobertura de campos estructurados — BDNS, Comunitat Valenciana

Medido el {datetime.now(UTC).date().isoformat()} sobre una muestra de **{n} convocatorias**
de los últimos {args.dias} días (regiones Alicante/Castellón/Valencia).
Reproducible con `python scripts/explore_coverage.py`.

| Campo | Cobertura estructurada | Decisión F2 |
|---|---|---|
| `importe` (presupuestoTotal) | {con_importe}/{n} ({pct(con_importe)}) | {"reglas suficientes" if con_importe / n > 0.7 else "LLM/regex sobre el PDF para el resto"} |
| `fecha_fin_solicitud` (plazo) | {con_plazo}/{n} ({pct(con_plazo)}) | {"reglas suficientes" if con_plazo / n > 0.7 else "LLM/regex sobre el PDF para el resto"} |
| `sectores` (~CNAE) | {con_sector}/{n} ({pct(con_sector)}) | {"reglas suficientes" if con_sector / n > 0.7 else "LLM sobre descripción/PDF para el resto"} |
| `abierto` (convocatoria vigente) | {abiertas}/{n} ({pct(abiertas)}) siguen abiertas | — |

Muestra cruda (gitignored, no se versiona): `data/raw/bdns_cv_sample.jsonl`.
"""
    REPORT_OUT.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
