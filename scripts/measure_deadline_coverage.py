"""F2 — mide cuánto resuelve cada nivel del pipeline de plazo (estructurado
-> regex -> LLM local) sobre una muestra real de BDNS, antes de dar el
pipeline por bueno. Nada de esto usa una API de pago: Ollama corre en local.

Uso:
    python scripts/measure_deadline_coverage.py [--sample N] [--dias N] [--sin-llm]

Nota: este script SOBRESCRIBE docs/f2-deadline-coverage.md por completo. Si
se ha añadido análisis manual al informe, cópialo aparte antes de volver a
ejecutar.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from trackeraid.extraction.deadline import resolver_plazo
from trackeraid.extraction.llm_ollama import (
    OllamaNoDisponibleError,
    calentar_modelo,
    extraer_plazo_llm,
)
from trackeraid.ingestion.bdns import REGIONES_COMUNITAT_VALENCIANA, BDNSClient

# La consola de Windows (cp1252) no sabe imprimir ⚠️/em-dash y tumba el
# script justo al final, después de haber medido todo — forzamos UTF-8 en
# stdout para que el resumen se vea también en pantalla, no solo en el .md.
sys.stdout.reconfigure(encoding="utf-8")

REPORT_OUT = Path("docs/f2-deadline-coverage.md")


def recolectar_resumenes(client: BDNSClient, dias: int, objetivo: int) -> list:
    fecha_desde = datetime.now(UTC).date() - timedelta(days=dias)
    region_ids = list(REGIONES_COMUNITAT_VALENCIANA.values())
    resumenes, page = [], 0
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
    parser.add_argument("--sin-llm", action="store_true", help="no probar el fallback de Ollama")
    args = parser.parse_args()

    contador_metodo: Counter[str] = Counter()
    llm_intentos = 0
    llm_resueltos = 0
    ollama_caido = False

    if not args.sin_llm:
        print("Precalentando Ollama (puede tardar hasta ~1 min la primera vez)...")
        try:
            calentar_modelo()
            print("Ollama listo.")
        except OllamaNoDisponibleError as e:
            print(f"Ollama no disponible, se sigue sin LLM: {e}")
            ollama_caido = True

    with BDNSClient() as client:
        resumenes = recolectar_resumenes(client, args.dias, args.sample)
        print(f"Muestra (CV, últimos {args.dias} días): {len(resumenes)} convocatorias")

        for i, r in enumerate(resumenes, 1):
            if not r.numero_convocatoria:
                continue
            try:
                det = client.detalle(r.numero_convocatoria)
            except (httpx.HTTPStatusError, httpx.TransportError):
                continue

            resultado = resolver_plazo(det)
            metodo_final = resultado.metodo

            if resultado.metodo == "no_resuelto" and det.texto_fin and not args.sin_llm and not ollama_caido:
                llm_intentos += 1
                try:
                    llm = extraer_plazo_llm(det.texto_fin, fecha_referencia=det.fecha_recepcion)
                    if llm.fecha_fin or llm.sin_plazo:
                        metodo_final = "llm_ollama"
                        llm_resueltos += 1
                except OllamaNoDisponibleError as e:
                    print(f"  Ollama no disponible, se sigue sin LLM: {e}")
                    ollama_caido = True

            contador_metodo[metodo_final] += 1
            if i % 25 == 0:
                print(f"  [{i}/{len(resumenes)}] procesadas")
            time.sleep(0.15)

    total = sum(contador_metodo.values())

    def pct(x: int) -> str:
        return f"{100 * x / total:.1f}%" if total else "n/a"

    resuelto = total - contador_metodo.get("no_resuelto", 0)
    resumen = (
        f"Medido el {datetime.now(UTC).date().isoformat()} sobre {total} convocatorias reales "
        f"(CV, últimos {args.dias} días). Reproducible con `python scripts/measure_deadline_coverage.py`."
    )
    lineas = [
        "# Cobertura de plazo (fecha_fin_solicitud) — pipeline de tres niveles",
        "",
        resumen,
        "",
        "| Método | Convocatorias | % |",
        "|---|---|---|",
    ]
    orden = ["estructurado", "regex_fecha_absoluta", "regex_sin_plazo", "regex_relativo", "llm_ollama", "no_resuelto"]
    for metodo in orden:
        n = contador_metodo.get(metodo, 0)
        if n:
            lineas.append(f"| `{metodo}` | {n} | {pct(n)} |")
    lineas += [
        "",
        f"**Resuelto en total (sin PDF, sin coste): {resuelto}/{total} ({pct(resuelto)})**",
        "",
        f"Intentos de LLM: {llm_intentos} | resueltos por LLM: {llm_resueltos}"
        + (" | ⚠️ Ollama no estaba disponible durante parte de la corrida" if ollama_caido else ""),
    ]
    report = "\n".join(lineas) + "\n"
    REPORT_OUT.write_text(report, encoding="utf-8")
    print("\n" + report)


if __name__ == "__main__":
    main()
