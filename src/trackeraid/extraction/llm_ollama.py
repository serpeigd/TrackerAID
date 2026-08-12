"""Fallback de extracción de plazo con LLM local (Ollama) — coste cero.

Se usa solo cuando `deadline.resolver_por_regex` no llega a una respuesta
(`metodo == "no_resuelto"`): frases relativas o redactadas de forma poco
habitual. No requiere ANTHROPIC_API_KEY ni ningún servicio de pago — corre
contra un Ollama local en `localhost:11434`.
"""

from __future__ import annotations

import json
from datetime import date

import httpx
from pydantic import BaseModel, ValidationError

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3.1:8b"

_PROMPT = """Eres un extractor de datos preciso. Te doy el texto de plazo de \
solicitud de una subvención pública española y, si existe, la fecha de \
publicación de la convocatoria como referencia. Devuelve SOLO un objeto \
JSON con esta forma exacta, sin explicación ni texto adicional:

{{"fecha_fin": "YYYY-MM-DD" o null, "sin_plazo": true o false}}

- "sin_plazo": true solo si el texto dice explícitamente que no hay plazo \
o que la convocatoria está abierta de forma permanente.
- Si no puedes determinar una fecha con confianza, usa fecha_fin: null y \
sin_plazo: false — no inventes una fecha.

Fecha de publicación (referencia): {fecha_referencia}
Texto del plazo: "{texto}"

JSON:"""


class RespuestaLLM(BaseModel):
    fecha_fin: date | None = None
    sin_plazo: bool = False


class OllamaNoDisponibleError(RuntimeError):
    """Ollama no responde en localhost:11434, o el modelo no está descargado."""


def extraer_plazo_llm(
    texto: str,
    fecha_referencia: date | None = None,
    model: str = DEFAULT_MODEL,
    timeout: float = 30.0,
) -> RespuestaLLM:
    prompt = _PROMPT.format(
        fecha_referencia=fecha_referencia.isoformat() if fecha_referencia else "desconocida",
        texto=texto,
    )
    try:
        resp = httpx.post(
            OLLAMA_URL,
            json={"model": model, "prompt": prompt, "stream": False, "format": "json"},
            timeout=timeout,
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise OllamaNoDisponibleError(
            f"Ollama no responde en {OLLAMA_URL} (¿está corriendo? ¿modelo '{model}' descargado?): {e}"
        ) from e

    raw_text = resp.json().get("response", "")
    try:
        data = json.loads(raw_text)
        return RespuestaLLM.model_validate(data)
    except (json.JSONDecodeError, ValidationError):
        # El modelo no devolvió JSON válido: se trata como "no resuelto" en
        # vez de fallar el pipeline entero por una respuesta rara del LLM.
        return RespuestaLLM(fecha_fin=None, sin_plazo=False)
