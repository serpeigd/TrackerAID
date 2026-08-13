"""API mínima que n8n llama para disparar el pipeline semanal.

Toda la lógica vive en `pipeline.py` — este archivo solo la expone por
HTTP. `POST /pipeline/ingest` NO espera a que termine: lanza el trabajo en
segundo plano y responde al instante. Se hizo así tras un fallo real en
producción — con una llamada síncrona de varios minutos, la conexión entre
n8n (en Docker) y la API (en el host) se cortaba antes de recibir la
respuesta, aunque el pipeline sí terminaba bien del lado del servidor
(confirmado: los datos llegaban a Supabase pese al error de conexión en
n8n). `GET /pipeline/status` consulta el resultado de la última corrida.
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from typing import Literal

from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel, Field

from trackeraid.pipeline import ResumenIngesta, ingerir

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("trackeraid.api")

app = FastAPI(title="TrackerAID API", version="0.1.0")

Estado = Literal["inactivo", "en_curso", "completado", "error"]


class _EstadoPipeline:
    """Estado en memoria de la última corrida. Vale para una única instancia
    del proceso (el caso real de este proyecto) — si algún día hay más de
    un worker, esto tendría que vivir en Supabase, no en memoria."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.estado: Estado = "inactivo"
        self.iniciado_en: str | None = None
        self.terminado_en: str | None = None
        self.resumen: ResumenIngesta | None = None
        self.error: str | None = None

    def marcar_inicio(self) -> None:
        with self._lock:
            self.estado = "en_curso"
            self.iniciado_en = datetime.now(UTC).isoformat()
            self.terminado_en = None
            self.resumen = None
            self.error = None

    def marcar_completado(self, resumen: ResumenIngesta) -> None:
        with self._lock:
            self.estado = "completado"
            self.terminado_en = datetime.now(UTC).isoformat()
            self.resumen = resumen

    def marcar_error(self, error: str) -> None:
        with self._lock:
            self.estado = "error"
            self.terminado_en = datetime.now(UTC).isoformat()
            self.error = error


_estado_pipeline = _EstadoPipeline()


class IngestaRequest(BaseModel):
    dias: int = Field(default=14, ge=1, le=90, description="Ventana de días hacia atrás a revisar en BDNS.")
    con_llm: bool = Field(default=True, description="Usar Ollama como fallback cuando el regex no basta.")
    max_convocatorias: int = Field(default=200, ge=1, le=1000)


class IngestaIniciadaResponse(BaseModel):
    iniciado: bool
    mensaje: str


class ResumenResponse(BaseModel):
    procesadas: int
    guardadas: int
    con_plazo_resuelto: int
    metodo_llm_usado: int
    errores: list[str]

    @classmethod
    def from_resumen(cls, resumen: ResumenIngesta) -> ResumenResponse:
        return cls(
            procesadas=resumen.procesadas,
            guardadas=resumen.guardadas,
            con_plazo_resuelto=resumen.con_plazo_resuelto,
            metodo_llm_usado=resumen.metodo_llm_usado,
            errores=resumen.errores,
        )


class EstadoResponse(BaseModel):
    estado: Estado
    iniciado_en: str | None
    terminado_en: str | None
    resumen: ResumenResponse | None
    error: str | None


def _ejecutar_ingesta(dias: int, con_llm: bool, max_convocatorias: int) -> None:
    """Corre en segundo plano — nadie está esperando esta llamada por HTTP."""
    try:
        resumen = ingerir(dias=dias, con_llm=con_llm, max_convocatorias=max_convocatorias)
        logger.info("Ingesta completa: %s", resumen)
        _estado_pipeline.marcar_completado(resumen)
    except Exception as e:
        # Captura amplia deliberada: un fallo aquí no debe tumbar el
        # proceso (nadie más lo vería) — se registra en el estado para que
        # /pipeline/status lo reporte y n8n pueda avisar por email.
        logger.exception("Fallo en la ingesta en segundo plano")
        _estado_pipeline.marcar_error(str(e))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/pipeline/ingest", response_model=IngestaIniciadaResponse, status_code=202)
def pipeline_ingest(body: IngestaRequest, background_tasks: BackgroundTasks) -> IngestaIniciadaResponse:
    """Lanza la ingesta en segundo plano y responde al instante (202).
    Consulta el resultado con GET /pipeline/status más adelante."""
    logger.info("Ingesta solicitada: dias=%s con_llm=%s max=%s", body.dias, body.con_llm, body.max_convocatorias)
    _estado_pipeline.marcar_inicio()
    background_tasks.add_task(_ejecutar_ingesta, body.dias, body.con_llm, body.max_convocatorias)
    return IngestaIniciadaResponse(iniciado=True, mensaje="Ingesta lanzada en segundo plano.")


@app.get("/pipeline/status", response_model=EstadoResponse)
def pipeline_status() -> EstadoResponse:
    return EstadoResponse(
        estado=_estado_pipeline.estado,
        iniciado_en=_estado_pipeline.iniciado_en,
        terminado_en=_estado_pipeline.terminado_en,
        resumen=ResumenResponse.from_resumen(_estado_pipeline.resumen) if _estado_pipeline.resumen else None,
        error=_estado_pipeline.error,
    )
