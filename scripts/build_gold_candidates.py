"""F1 — genera la hoja de candidatas para el gold set (data/gold/candidates.csv).

Descarga una muestra diversa de convocatorias reales de la Comunitat
Valenciana y les aplica un BORRADOR heurístico de relevancia según el
criterio escrito en docs/gold-labeling-criteria.md — solo para los casos
inequívocos que el propio criterio ya resuelve sin ambigüedad (asociaciones/
ayuntamientos/premios = 0, beneficiario empresarial claro = 2 candidato).
Todo lo demás se deja en blanco a propósito.

`abierto` NO decide la relevancia (ver corrección en el criterio: exigirlo
dejaba el gold set casi sin positivos — 4 de 450 candidatas empresariales
reales seguían abiertas en el momento de la prueba). Se etiqueta relevancia
temática; `abierto` queda como columna informativa para el filtro de
producto de F3, aparte de la etiqueta.

IMPORTANTE: `heuristic_relevance` NO es el gold label. Es un borrador para
acelerar la revisión humana, no un sustituto de ella. La columna `relevance`
(la que de verdad cuenta para el gold set) se deja vacía hasta que un
anotador humano la confirme o corrija — así lo dice el propio criterio de
etiquetado: los casos dudosos se etiquetan como 1, no se adivinan.

Uso:
    python scripts/build_gold_candidates.py [--sample N] [--dias N]
"""

from __future__ import annotations

import argparse
import csv
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from trackeraid.ingestion.bdns import REGIONES_COMUNITAT_VALENCIANA, BDNSClient, ConvocatoriaDetalle

OUT = Path("data/gold/candidates.csv")

# Vocabulario tomado de docs/gold-labeling-criteria.md — solo cubre los
# casos que el criterio ya resuelve sin ambigüedad.
KEYWORDS_NO_EMPRESARIAL = [
    "ASOCIACION", "ASSOCIACIÓ", "AYUNTAMIENTO", "AJUNTAMENT", "PARROQU",
    "CLUB", "FAMILIA", "NO DESARROLLAN ACTIVIDAD ECONÓMICA",
    "CENTRO EDUCATIVO", "CENTRE EDUCATIU", "ENTIDAD LOCAL", "FUNDACIÓN SIN",
    "DEPORTIV", "ESPORTIV",
]
KEYWORDS_EMPRESARIAL = [
    "EMPRESA", "AUTÓNOMO", "AUTONOMO", "PYME", "ACTIVIDAD ECONÓMICA",
    "EMPRESARIAL", "PERSONAS FÍSICAS O JURÍDICAS QUE DESARROLLAN",
]
# Encontrado en la primera pasada: premios/certámenes locales listan "PYME"
# como categoría de participante posible, pero no son ayuda económica a la
# actividad empresarial — son un concurso con premio, no una subvención.
KEYWORDS_CONCURSO = ["PREMIO", "CERTAMEN", "CONCURSO"]


def clasificar(det: ConvocatoriaDetalle) -> tuple[str, str]:
    """Devuelve (heuristic_relevance, motivo). Cadena vacía si no está claro."""
    texto_beneficiarios = " | ".join(det.tipos_beneficiarios).upper()
    tipo = (det.tipo_convocatoria or "").upper()
    descripcion = det.descripcion.upper()

    if "NOMINATIV" in tipo:
        return "0", "convenio nominativo, no hay proceso de solicitud abierto a terceros"
    if any(kw in descripcion for kw in KEYWORDS_CONCURSO):
        return "0", "premio/certamen/concurso, no es ayuda económica a la actividad empresarial"
    if any(kw in texto_beneficiarios for kw in KEYWORDS_NO_EMPRESARIAL):
        return "0", "beneficiario no empresarial (asociación/ayuntamiento/parroquia/club/...)"
    if any(kw in texto_beneficiarios for kw in KEYWORDS_EMPRESARIAL):
        # La relevancia es temática, no de disponibilidad: `abierto` no entra
        # aquí (ver docs/gold-labeling-criteria.md). Se anota igualmente en el
        # CSV como columna aparte para el filtro de producto de F3.
        return "2", "beneficiario empresarial claro"
    return "", "sin señal clara en tipos_beneficiarios — revisar a mano"


# Muestreo por pura recencia sale dominado por convenios/premios locales
# (visto en la primera pasada: 282/300 -> 0, 0/300 -> 2). Se combina con
# búsquedas dirigidas a los términos que un autónomo/pyme real usaría, para
# que el gold set tenga positivos de verdad, no solo negativos.
TERMINOS_EMPRESARIALES = [
    "pymes", "autónomos", "empresas digitalización", "emprendedores",
    "comercio local", "agricultura profesional", "hostelería", "innovación empresarial",
    "kit digital", "IVACE", "inversión empresarial", "internacionalización",
    "eficiencia energética empresas", "industria", "startup", "economía circular",
]


def recolectar_resumenes(client: BDNSClient, dias: int, objetivo: int) -> list:
    fecha_desde = datetime.now(UTC).date() - timedelta(days=dias)
    region_ids = list(REGIONES_COMUNITAT_VALENCIANA.values())
    vistos: dict[int, object] = {}

    # Mitad por recencia (diversidad de negativos reales) ...
    page = 0
    while len(vistos) < objetivo // 2:
        lote = client.buscar(regiones=region_ids, fecha_desde=fecha_desde, page=page, page_size=50)
        if not lote:
            break
        for r in lote:
            vistos[r.id] = r
        page += 1

    # ... mitad dirigida a términos de negocio real (para tener positivos).
    # Sin ventana de fecha aquí a propósito: interesa encontrar líneas
    # abiertas ahora mismo, estén publicadas cuando estén.
    for termino in TERMINOS_EMPRESARIALES:
        lote = client.buscar(descripcion=termino, regiones=region_ids, page_size=40)
        for r in lote:
            vistos[r.id] = r

    return list(vistos.values())[:objetivo]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=300)
    parser.add_argument("--dias", type=int, default=180)
    args = parser.parse_args()

    OUT.parent.mkdir(parents=True, exist_ok=True)

    filas = []
    contador = {"0": 0, "1": 0, "2": 0, "": 0}
    with BDNSClient() as client:
        resumenes = recolectar_resumenes(client, args.dias, args.sample)
        print(f"Resúmenes recogidos (CV, últimos {args.dias} días): {len(resumenes)}")

        for i, r in enumerate(resumenes, 1):
            if not r.numero_convocatoria:
                continue
            try:
                det = client.detalle(r.numero_convocatoria)
            except (httpx.HTTPStatusError, httpx.TransportError) as e:
                print(f"  [{i}/{len(resumenes)}] fallo en {r.numero_convocatoria}: {e}")
                continue
            heur, motivo = clasificar(det)
            contador[heur] += 1
            filas.append(
                {
                    "doc_id": det.id,
                    "numero_convocatoria": det.numero_convocatoria,
                    "nivel1": r.nivel1,
                    "nivel2": r.nivel2,
                    "descripcion": det.descripcion,
                    "tipos_beneficiarios": " | ".join(det.tipos_beneficiarios),
                    "sectores": " | ".join(det.sectores),
                    "tipo_convocatoria": det.tipo_convocatoria,
                    "importe": det.importe,
                    "abierto": det.abierto,
                    "fecha_fin_solicitud": det.fecha_fin_solicitud,
                    "heuristic_relevance": heur,
                    "heuristic_reason": motivo,
                    "relevance": "",  # a rellenar por un humano
                    "annotator": "",
                    "notes": "",
                }
            )
            if i % 25 == 0:
                print(f"  [{i}/{len(resumenes)}] procesadas")
            time.sleep(0.15)

    # utf-8-sig (BOM): sin él, Excel en Windows abre el CSV interpretando
    # los acentos mal (mojibake) aunque el archivo sea UTF-8 válido.
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        writer.writeheader()
        writer.writerows(filas)

    print(f"\n{len(filas)} candidatas escritas en {OUT}")
    print(f"Borrador heurístico: {contador['2']} candidatas a 2, {contador['1']} a 1, "
          f"{contador['0']} a 0, {contador['']} sin señal clara (revisión manual obligatoria).")
    print("Recuerda: 'relevance' está vacía a propósito. 'heuristic_relevance' es solo un borrador.")


if __name__ == "__main__":
    main()
