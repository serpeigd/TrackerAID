"""Ranking heurístico de convocatorias — v1, deliberadamente simple.

Puntúa cada candidata combinando: solape con los sectores del perfil,
proximidad del plazo, y afinidad histórica de feedback del propio usuario
por sector (`SupabaseStorage.afinidad_sectorial`). No es un modelo de ML
— es una heurística transparente y fácil de depurar. Si algún día hace
falta algo más sofisticado (embeddings, un modelo aprendido), esto es la
base con la que comparar si de verdad mejora algo — ninguna cifra sin
denominador, tampoco aquí.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

_DIAS_URGENCIA = 30  # a partir de aquí, el plazo ya no suma más puntos
_BONUS_SECTOR_MAX = 0.6
_BONUS_URGENCIA_MAX = 0.4


def _bonus_sector(cnae_doc: list[str] | None, cnae_perfil: list[str] | None) -> float:
    """Más sectores del documento que coinciden con los del perfil ->
    más señal de que es justo lo que busca, no un pase permisivo."""
    if not cnae_doc or not cnae_perfil:
        return 0.0
    perfil_lower = [c.lower() for c in cnae_perfil]
    coincidencias = sum(1 for sector in cnae_doc if any(kw in sector.lower() for kw in perfil_lower))
    return min(coincidencias * 0.3, _BONUS_SECTOR_MAX)


def _bonus_urgencia(fecha_limite: str | None) -> float:
    """Cuanto más cerca el plazo, más arriba — hasta _DIAS_URGENCIA; pasado
    ese umbral no suma más (no queremos que todo lo urgente gane siempre a
    todo lo relevante). Plazos ya vencidos no reciben bonus (no deberían
    llegar aquí de todos modos, buscar_convocatorias ya los excluye)."""
    if not fecha_limite:
        return 0.0
    dias = (date.fromisoformat(fecha_limite) - datetime.now(UTC).date()).days
    if dias < 0:
        return 0.0
    return max(0.0, (_DIAS_URGENCIA - min(dias, _DIAS_URGENCIA)) / _DIAS_URGENCIA) * _BONUS_URGENCIA_MAX


def _bonus_afinidad(cnae_doc: list[str] | None, afinidad: dict[str, float]) -> float:
    """Suma directa: si el usuario ya dio 👍 a convocatorias de este sector
    antes, sube; si dio 👎, baja. Sin normalizar a propósito en v1 — con
    poco historial un solo 👍/👎 ya debe notarse, no diluirse."""
    if not cnae_doc or not afinidad:
        return 0.0
    return sum(afinidad.get(sector, 0.0) for sector in cnae_doc)


def puntuar(candidata: dict[str, Any], cnae_perfil: list[str] | None, afinidad: dict[str, float]) -> float:
    """Puntuación de una convocatoria ya filtrada por
    `SupabaseStorage.buscar_convocatorias` — esto no decide si entra o no,
    solo en qué orden se muestra."""
    return (
        1.0
        + _bonus_sector(candidata.get("cnae"), cnae_perfil)
        + _bonus_urgencia(candidata.get("fecha_limite"))
        + _bonus_afinidad(candidata.get("cnae"), afinidad)
    )


def rankear(
    candidatas: list[dict[str, Any]],
    cnae_perfil: list[str] | None,
    afinidad: dict[str, float],
    top_n: int = 10,
) -> list[dict[str, Any]]:
    """Ordena por puntuación descendente; añade `score` a cada fila para
    poder guardarlo luego en `impressions.score`."""
    puntuadas = [{**c, "score": puntuar(c, cnae_perfil, afinidad)} for c in candidatas]
    puntuadas.sort(key=lambda c: c["score"], reverse=True)
    return puntuadas[:top_n]
