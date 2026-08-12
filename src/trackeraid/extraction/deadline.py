"""Resolución del plazo de solicitud (fecha_fin_solicitud).

Tres niveles, de más barato a más caro — nunca hace falta una API de pago:

1. **Campo estructurado** (`fecha_fin_solicitud`) — gratis, ya lo da la API.
2. **Regex sobre `texto_fin`** (`textFin` de BDNS) — gratis, cubre el caso
   más común: fecha absoluta en texto ("HASTA EL 31 DE OCTUBRE DE 2026") o
   "sin plazo de solicitud". Hallazgo de F2: la mayoría de lo que
   `fecha_fin_solicitud` deja vacío, `texto_fin` sí lo rellena en texto
   libre — no hace falta PDF ni LLM para resolverlo.
3. **LLM local (Ollama)** — gratis (corre en el PC), solo para el resto:
   frases relativas o ambiguas que el regex no cubre. Ver
   `trackeraid.extraction.llm_ollama`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from trackeraid.ingestion.bdns import ConvocatoriaDetalle

MESES: dict[str, int] = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

_PATRON_FECHA_TEXTUAL = re.compile(
    r"(\d{1,2})\s+de\s+(" + "|".join(MESES) + r")\s+de\s+(\d{4})", re.IGNORECASE
)
_PATRON_FECHA_SLASH = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_PATRON_SIN_PLAZO = re.compile(r"sin\s+plazo", re.IGNORECASE)
_PATRON_DIAS_RELATIVO = re.compile(r"(\d+)\s+d[ií]as?\s+(h[áa]biles|naturales)?", re.IGNORECASE)

# Métodos posibles, de más a menos fiable — se guarda en doc_fields.extractor_version.
METODOS = (
    "estructurado",
    "regex_sin_plazo",
    "regex_fecha_absoluta",
    "regex_relativo",
    "llm_ollama",
    "no_resuelto",
)


@dataclass
class ResultadoPlazo:
    fecha_fin: date | None
    sin_plazo: bool  # True = ayuda sin plazo de solicitud (línea abierta permanente)
    metodo: str
    texto_fuente: str | None = None


def _parse_fecha_absoluta(texto: str) -> date | None:
    m = _PATRON_FECHA_TEXTUAL.search(texto)
    if m:
        dia, mes_txt, anio = m.groups()
        try:
            return date(int(anio), MESES[mes_txt.lower()], int(dia))
        except ValueError:
            return None
    m = _PATRON_FECHA_SLASH.search(texto)
    if m:
        dia, mes, anio = m.groups()
        try:
            return date(int(anio), int(mes), int(dia))
        except ValueError:
            return None
    return None


def resolver_por_regex(texto_fin: str, fecha_referencia: date | None = None) -> ResultadoPlazo:
    """Intenta resolver el plazo a partir de `texto_fin` sin llamar a ningún LLM."""
    if _PATRON_SIN_PLAZO.search(texto_fin):
        return ResultadoPlazo(fecha_fin=None, sin_plazo=True, metodo="regex_sin_plazo", texto_fuente=texto_fin)

    fecha_absoluta = _parse_fecha_absoluta(texto_fin)
    if fecha_absoluta:
        return ResultadoPlazo(
            fecha_fin=fecha_absoluta, sin_plazo=False, metodo="regex_fecha_absoluta", texto_fuente=texto_fin
        )

    if fecha_referencia:
        m = _PATRON_DIAS_RELATIVO.search(texto_fin)
        if m:
            # Aproximación deliberada: no se distingue calendario laboral de
            # natural con precisión (festivos, fines de semana) — el objetivo
            # es una fecha orientativa, no exacta al día. Documentado aquí,
            # no oculto en el dato.
            dias = int(m.group(1))
            fecha_fin = fecha_referencia + timedelta(days=dias)
            return ResultadoPlazo(
                fecha_fin=fecha_fin, sin_plazo=False, metodo="regex_relativo", texto_fuente=texto_fin
            )

    return ResultadoPlazo(fecha_fin=None, sin_plazo=False, metodo="no_resuelto", texto_fuente=texto_fin)


def resolver_plazo(detalle: ConvocatoriaDetalle) -> ResultadoPlazo:
    """Punto de entrada: estructurado -> regex sobre texto_fin -> sin resolver.

    No llama a Ollama — eso lo decide el llamador (ver `extraction/pipeline.py`
    o el script de medición) para poder medir por separado cuánto aporta cada
    nivel antes de gastar tiempo de LLM en lo que el regex ya resuelve gratis.
    """
    if detalle.fecha_fin_solicitud:
        return ResultadoPlazo(fecha_fin=detalle.fecha_fin_solicitud, sin_plazo=False, metodo="estructurado")
    if detalle.texto_fin:
        return resolver_por_regex(detalle.texto_fin, detalle.fecha_recepcion)
    return ResultadoPlazo(fecha_fin=None, sin_plazo=False, metodo="no_resuelto")
