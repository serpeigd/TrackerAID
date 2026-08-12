"""API mínima que n8n llama para disparar el pipeline semanal.

Toda la lógica vive en `pipeline.py` — este archivo solo la expone por
HTTP. Un único endpoint de negocio (`POST /pipeline/ingest`) más un
`/health` para que n8n (o cualquier monitor) compruebe que está viva antes
de disparar el cron.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from trackeraid.pipeline import ResumenIngesta, ingerir

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("trackeraid.api")

app = FastAPI(title="TrackerAID API", version="0.1.0")


class IngestaRequest(BaseModel):
    dias: int = Field(default=14, ge=1, le=90, description="Ventana de días hacia atrás a revisar en BDNS.")
    con_llm: bool = Field(default=True, description="Usar Ollama como fallback cuando el regex no basta.")
    max_convocatorias: int = Field(default=200, ge=1, le=1000)


class IngestaResponse(BaseModel):
    procesadas: int
    guardadas: int
    con_plazo_resuelto: int
    metodo_llm_usado: int
    errores: list[str]

    @classmethod
    def from_resumen(cls, resumen: ResumenIngesta) -> IngestaResponse:
        return cls(
            procesadas=resumen.procesadas,
            guardadas=resumen.guardadas,
            con_plazo_resuelto=resumen.con_plazo_resuelto,
            metodo_llm_usado=resumen.metodo_llm_usado,
            errores=resumen.errores,
        )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/pipeline/ingest", response_model=IngestaResponse)
def pipeline_ingest(body: IngestaRequest) -> IngestaResponse:
    """Dispara la ingesta. Llamada síncrona: para lotes grandes puede tardar
    varios minutos (rate-limit deliberado contra BDNS + posible LLM local
    en cada convocatoria no resuelta por regex) — el nodo HTTP Request de
    n8n necesita un timeout generoso, no el que trae por defecto."""
    logger.info("Ingesta solicitada: dias=%s con_llm=%s max=%s", body.dias, body.con_llm, body.max_convocatorias)
    try:
        resumen = ingerir(dias=body.dias, con_llm=body.con_llm, max_convocatorias=body.max_convocatorias)
    except Exception as e:
        # Captura amplia deliberada: cualquier fallo del pipeline se traduce
        # a un 500 explícito con detalle, en vez de tumbar el proceso o
        # dejar que n8n reciba una conexión cortada sin explicación.
        logger.exception("Fallo en la ingesta")
        raise HTTPException(status_code=500, detail=str(e)) from e
    logger.info("Ingesta completa: %s", resumen)
    return IngestaResponse.from_resumen(resumen)
