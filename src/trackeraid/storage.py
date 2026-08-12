"""Cliente mínimo de Supabase vía REST (PostgREST).

Deliberadamente sin el paquete `supabase-py`: httpx ya es dependencia del
proyecto y PostgREST expone todo lo que necesita el pipeline (upsert por
`doc_id`). Usa la `service_role_key`, que salta RLS — correcto para un
proceso de backend de confianza, nunca debe usarse desde el cliente/app.
"""

from __future__ import annotations

from typing import Any, Self

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from trackeraid.config import settings

_RETRYABLE = (httpx.TransportError, httpx.HTTPStatusError)


class SupabaseConfigError(RuntimeError):
    """Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el entorno (.env)."""


class SupabaseStorage:
    def __init__(self, url: str | None = None, service_role_key: str | None = None, timeout: float = 20.0):
        self.url = (url or settings.supabase_url).rstrip("/")
        self.service_role_key = service_role_key or settings.supabase_service_role_key
        if not self.url or not self.service_role_key:
            raise SupabaseConfigError(
                "SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY son obligatorios "
                "(revisa tu .env — nunca se commitea, solo .env.example)."
            )
        self._client = httpx.Client(
            base_url=f"{self.url}/rest/v1",
            timeout=timeout,
            headers={
                "apikey": self.service_role_key,
                "Authorization": f"Bearer {self.service_role_key}",
                "Content-Type": "application/json",
            },
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self._client.close()

    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
    )
    def upsert(self, tabla: str, filas: list[dict[str, Any]], on_conflict: str) -> int:
        """Upsert genérico vía PostgREST (`Prefer: resolution=merge-duplicates`).

        Devuelve el número de filas enviadas (PostgREST no confirma cuántas
        se insertaron vs. actualizaron con `return=minimal`, que se usa aquí
        a propósito para no pagar el coste de traer de vuelta cada fila).
        """
        if not filas:
            return 0
        resp = self._client.post(
            f"/{tabla}",
            params={"on_conflict": on_conflict},
            json=filas,
            headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
        )
        resp.raise_for_status()
        return len(filas)

    def upsert_documents(self, filas: list[dict[str, Any]]) -> int:
        return self.upsert("documents", filas, on_conflict="doc_id")

    def upsert_doc_fields(self, filas: list[dict[str, Any]]) -> int:
        return self.upsert("doc_fields", filas, on_conflict="doc_id")

    def contar(self, tabla: str) -> int:
        """Nº de filas de una tabla, vía el header Content-Range de PostgREST."""
        resp = self._client.head(f"/{tabla}", headers={"Prefer": "count=exact"})
        resp.raise_for_status()
        content_range = resp.headers.get("content-range", "*/0")
        return int(content_range.split("/")[-1])
