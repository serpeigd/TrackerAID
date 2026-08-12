"""Pipeline de ingesta semanal: BDNS -> extracción de plazo -> Supabase.

Punto de entrada único (`ingerir()`) que dispara n8n cada semana a través
del endpoint de FastAPI (ver `api.py`). Reutiliza los módulos ya
construidos y testeados por separado — este archivo solo orquesta.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import httpx

from trackeraid.extraction.deadline import ResultadoPlazo, resolver_plazo
from trackeraid.extraction.llm_ollama import (
    OllamaNoDisponibleError,
    calentar_modelo,
    extraer_plazo_llm,
)
from trackeraid.ingestion.bdns import REGIONES_COMUNITAT_VALENCIANA, BDNSClient, ConvocatoriaDetalle
from trackeraid.storage import SupabaseStorage


@dataclass
class ResumenIngesta:
    procesadas: int = 0
    guardadas: int = 0
    con_plazo_resuelto: int = 0
    metodo_llm_usado: int = 0
    errores: list[str] = field(default_factory=list)


def _hash_contenido(det: ConvocatoriaDetalle) -> str:
    """Hash del contenido relevante — permite detectar si una convocatoria
    ya vista cambió (BDNS avisa explícitamente de que los datos son
    dinámicos y pueden corregirse tras la extracción)."""
    base = "|".join(
        str(v) for v in (det.descripcion, det.importe, det.fecha_fin_solicitud, det.texto_fin, det.abierto)
    )
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _fila_documento(det: ConvocatoriaDetalle) -> dict:
    return {
        "doc_id": det.id,
        "source": "bdns",
        "source_url": det.sede_electronica,
        "published_at": det.fecha_recepcion.isoformat() if det.fecha_recepcion else None,
        "raw_hash": _hash_contenido(det),
        "title": det.descripcion,
    }


def _fila_doc_fields(det: ConvocatoriaDetalle, resultado: ResultadoPlazo) -> dict:
    return {
        "doc_id": det.id,
        "importe": det.importe,
        "deadline": resultado.fecha_fin.isoformat() if resultado.fecha_fin else None,
        "ambito": ", ".join(det.regiones) or None,
        "cnae": det.sectores or None,
        "beneficiarios": " | ".join(det.tipos_beneficiarios) or None,
        "extractor_version": resultado.metodo,
        "abierto": det.abierto,
    }


def ingerir(
    dias: int = 14,
    region_ids: list[int] | None = None,
    con_llm: bool = True,
    max_convocatorias: int = 500,
) -> ResumenIngesta:
    """Ingiere convocatorias recientes, resuelve su plazo y las guarda.

    `con_llm=False` desactiva el fallback de Ollama (útil para pruebas
    rápidas o si Ollama no está disponible en la máquina que corre esto).
    """
    region_ids = region_ids or list(REGIONES_COMUNITAT_VALENCIANA.values())
    resumen = ResumenIngesta()

    llm_disponible = con_llm
    if con_llm:
        try:
            calentar_modelo()
        except OllamaNoDisponibleError as e:
            resumen.errores.append(f"Ollama no disponible, se sigue sin LLM: {e}")
            llm_disponible = False

    documentos_filas: list[dict] = []
    doc_fields_filas: list[dict] = []

    with BDNSClient() as bdns:
        fecha_desde = datetime.now(UTC).date() - timedelta(days=dias)
        resumenes, page = [], 0
        while len(resumenes) < max_convocatorias:
            lote = bdns.buscar(regiones=region_ids, fecha_desde=fecha_desde, page=page, page_size=50)
            if not lote:
                break
            resumenes.extend(lote)
            page += 1
        resumenes = resumenes[:max_convocatorias]

        for r in resumenes:
            if not r.numero_convocatoria:
                continue
            try:
                det = bdns.detalle(r.numero_convocatoria)
            except (httpx.HTTPStatusError, httpx.TransportError) as e:
                resumen.errores.append(f"{r.numero_convocatoria}: {e}")
                continue

            resultado = resolver_plazo(det)
            if resultado.metodo == "no_resuelto" and det.texto_fin and llm_disponible:
                try:
                    llm = extraer_plazo_llm(det.texto_fin, fecha_referencia=det.fecha_recepcion)
                    if llm.fecha_fin or llm.sin_plazo:
                        resultado = ResultadoPlazo(
                            fecha_fin=llm.fecha_fin, sin_plazo=llm.sin_plazo, metodo="llm_ollama"
                        )
                        resumen.metodo_llm_usado += 1
                except OllamaNoDisponibleError:
                    llm_disponible = False

            documentos_filas.append(_fila_documento(det))
            doc_fields_filas.append(_fila_doc_fields(det, resultado))
            resumen.procesadas += 1
            if resultado.fecha_fin or resultado.sin_plazo:
                resumen.con_plazo_resuelto += 1
            time.sleep(0.15)  # buen ciudadano con la API pública de BDNS

    with SupabaseStorage() as storage:
        resumen.guardadas = storage.upsert_documents(documentos_filas)
        storage.upsert_doc_fields(doc_fields_filas)

    return resumen
