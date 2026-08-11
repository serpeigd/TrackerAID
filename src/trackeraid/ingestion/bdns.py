"""Cliente para la API pública de BDNS/SNPSAP (infosubvenciones.es).

Verificado en vivo el 2026-08-11: la API no requiere API key y responde
JSON. No hay Swagger público estable, así que los endpoints y parámetros
de este módulo están confirmados por llamada directa, no por documentación
oficial — si BDNS cambia el contrato, los tests de integración (marcados
`integration`) son los que lo detectan primero.

Códigos de región (catálogo `/regiones`, rama ES52 - Comunitat Valenciana):
    55 = Alicante / Alacant
    56 = Castellón / Castelló
    57 = Valencia / València
"""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from trackeraid.config import settings

# IDs de la Comunitat Valenciana en el catálogo de regiones de BDNS.
REGIONES_COMUNITAT_VALENCIANA: dict[str, int] = {
    "Alicante/Alacant": 55,
    "Castellón/Castelló": 56,
    "Valencia/València": 57,
}

_RETRYABLE = (httpx.TransportError, httpx.HTTPStatusError)


class Convocatoria(BaseModel):
    """Resumen de una convocatoria tal como lo devuelve /convocatorias/busqueda."""

    id: int
    numero_convocatoria: str | None = None
    descripcion: str
    descripcion_leng: str | None = None
    fecha_recepcion: date | None = None
    nivel1: str | None = None  # ESTATAL / AUTONOMICA / LOCAL
    nivel2: str | None = None  # comunidad / provincia / municipio
    nivel3: str | None = None  # órgano concedente
    codigo_invente: str | None = None

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> Convocatoria:
        return cls(
            id=raw["id"],
            numero_convocatoria=raw.get("numeroConvocatoria"),
            descripcion=raw.get("descripcion") or "",
            descripcion_leng=raw.get("descripcionLeng"),
            fecha_recepcion=raw.get("fechaRecepcion"),
            nivel1=raw.get("nivel1"),
            nivel2=raw.get("nivel2"),
            nivel3=raw.get("nivel3"),
            codigo_invente=raw.get("codigoInvente"),
        )


class BDNSClient:
    """Cliente mínimo de solo lectura sobre la API pública de BDNS."""

    def __init__(self, base_url: str | None = None, vpd: str | None = None, timeout: float = 15.0):
        self.base_url = (base_url or settings.bdns_base_url).rstrip("/")
        self.vpd = vpd or settings.bdns_vpd
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout)

    def __enter__(self) -> BDNSClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self._client.close()

    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
    )
    def _get(self, path: str, params: dict[str, Any]) -> Any:
        params = {"vpd": self.vpd, **{k: v for k, v in params.items() if v is not None}}
        resp = self._client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _items(data: Any) -> list[dict[str, Any]]:
        """BDNS a veces envuelve resultados en {"content": [...]} y a veces
        devuelve la lista directamente (p.ej. /convocatorias/ultimas)."""
        if isinstance(data, dict):
            return data.get("content", [])
        return data if isinstance(data, list) else []

    def ultimas(self, page_size: int = 50) -> list[Convocatoria]:
        """Últimas convocatorias publicadas, sin filtrar. Útil para smoke-test."""
        data = self._get("/convocatorias/ultimas", {"pageSize": page_size})
        return [Convocatoria.from_api(item) for item in self._items(data)]

    def buscar(
        self,
        descripcion: str | None = None,
        regiones: list[int] | None = None,
        fecha_desde: date | None = None,
        fecha_hasta: date | None = None,
        page: int = 0,
        page_size: int = 50,
    ) -> list[Convocatoria]:
        """Búsqueda paginada de convocatorias con filtros opcionales.

        `regiones` son los IDs numéricos del catálogo `/regiones`
        (ver REGIONES_COMUNITAT_VALENCIANA para los de la CV).
        """
        params: dict[str, Any] = {
            "descripcion": descripcion,
            "page": page,
            "pageSize": page_size,
        }
        if fecha_desde:
            params["fechaDesde"] = fecha_desde.isoformat()
        if fecha_hasta:
            params["fechaHasta"] = fecha_hasta.isoformat()
        if regiones:
            params["regiones"] = ",".join(str(r) for r in regiones)
        data = self._get("/convocatorias/busqueda", params)
        return [Convocatoria.from_api(item) for item in self._items(data)]

    def regiones_catalogo(self) -> list[dict[str, Any]]:
        """Árbol completo de regiones (NUTS) tal como lo expone BDNS."""
        data = self._get("/regiones", {})
        return data if isinstance(data, list) else data.get("content", [])
