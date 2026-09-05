"""Cliente mínimo de Supabase vía REST (PostgREST).

Deliberadamente sin el paquete `supabase-py`: httpx ya es dependencia del
proyecto y PostgREST expone todo lo que necesita el pipeline (upsert por
`doc_id`). Usa la `service_role_key`, que salta RLS — correcto para un
proceso de backend de confianza, nunca debe usarse desde el cliente/app.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal, Self

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from trackeraid.config import settings

_RETRYABLE = (httpx.TransportError, httpx.HTTPStatusError)


class SupabaseConfigError(RuntimeError):
    """Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el entorno (.env)."""


def sector_encaja(sectores_doc: list[str] | None, cnae_buscado: list[str] | None, nivel1: str | None) -> bool:
    """Mismo criterio que usa `buscar_convocatorias` — factorizado aparte
    para que el script de generación del gold set (`scripts/build_mcp_gold_candidates.py`)
    use exactamente esta lógica y no una copia que pueda desincronizarse."""
    if nivel1 == "ESTATAL":
        return True
    if not cnae_buscado or not sectores_doc:
        return True
    buscado_lower = [c.lower() for c in cnae_buscado]
    return any(kw in sector.lower() for kw in buscado_lower for sector in sectores_doc)


def perfil_encaja(beneficiarios: str | None, perfil: Literal["negocio", "particular"]) -> bool:
    """Mismo criterio que usa `buscar_convocatorias` — ver `sector_encaja`."""
    if not beneficiarios:
        return True  # desconocido -> permisivo, mismo criterio que el resto de filtros
    frases = [f.upper() for f in beneficiarios.split(" | ")]
    if perfil == "particular":
        return any("NO DESARROLLAN ACTIVIDAD ECONÓMICA" in f for f in frases)
    return any("PYME" in f or ("ACTIVIDAD ECONÓMICA" in f and "NO DESARROLLAN" not in f) for f in frases)


# Códigos NUTS3/INE de las tres provincias de la Comunitat Valenciana, tal
# cual aparecen al principio de cada entrada de doc_fields.ambito (p.ej.
# "ES523 - Valencia / València"). Es toda la granularidad geográfica real
# que da BDNS hoy -- no hay municipio.
_CODIGOS_PROVINCIA_CV = {"ES521", "ES522", "ES523"}


def ambito_encaja(ambito_doc: list[str] | None, nivel1: str | None, provincia_buscada: str | None) -> bool:
    """Mismo criterio que usa `buscar_convocatorias` — ver `sector_encaja`.

    Filtra por provincia (código INE: ES521 Alicante, ES522 Castellón,
    ES523 Valencia) SOLO si `provincia_buscada` es uno de esos tres
    códigos. Cualquier otro valor -- vacío, o el texto libre que tenían
    todos los perfiles antes de este filtro ("Comunitat Valenciana") --
    se trata como "sin ámbito real todavía" y es permisivo, para no
    dejar de mostrarle nada a un perfil que aún no se ha vuelto a guardar
    con el desplegable nuevo."""
    if nivel1 == "ESTATAL":
        return True
    if provincia_buscada not in _CODIGOS_PROVINCIA_CV:
        return True
    if not ambito_doc:
        return True  # convocatoria sin ámbito conocido -> permisivo, no se descarta
    return any(provincia_buscada in a for a in ambito_doc)


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

    def select_raw(self, tabla: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Lectura genérica vía PostgREST — para scripts de análisis/gold
        set que necesitan columnas o filtros que los métodos de arriba no
        cubren. `buscar_convocatorias` sigue siendo la fuente de verdad
        para lo que expone la tool MCP; esto es solo para inspección."""
        resp = self._client.get(f"/{tabla}", params=params)
        resp.raise_for_status()
        return resp.json()

    def buscar_convocatorias(
        self,
        cnae: list[str] | None = None,
        ambito: str | None = None,
        perfil: Literal["negocio", "particular"] = "negocio",
        limite: int = 20,
    ) -> list[dict[str, Any]]:
        """Solo lectura. Convocatorias abiertas y con plazo vigente (o sin
        plazo publicado), opcionalmente filtradas por sector.

        `ambito` filtra por provincia — bug real corregido el 2026-09-05:
        hasta entonces este parámetro existía pero nunca se aplicaba
        (`doc_fields.ambito` es texto libre tipo "ES523 - Valencia /
        València" y `profiles.ambito` era texto libre tipo "Comunitat
        Valenciana"; comparar esas dos cadenas nunca coincidía con nada).
        Ahora filtra de verdad, pero SOLO si `ambito` es uno de los tres
        códigos de provincia de la Comunitat Valenciana (ES521 Alicante,
        ES522 Castellón, ES523 Valencia) — es toda la granularidad
        geográfica que da BDNS hoy, no hay municipio. Cualquier otro valor
        (None, o el texto libre heredado) es permisivo a propósito: mejor
        de más que ocultar una ayuda válida a un perfil que aún no se ha
        vuelto a guardar con el código nuevo. ESTATAL siempre aplica sin
        mirar ámbito.

        `cnae` filtra por subcadena, sin distinguir mayúsculas — el campo
        `cnae` de BDNS son descripciones libres, no códigos ("COMERCIO AL
        POR MAYOR Y AL POR MENOR", "Comercio al por menor"...), con
        mayúsculas inconsistentes entre convocatorias. Una igualdad exacta
        (como en la v1 original) nunca hacía match con nada real — bug
        real encontrado probando la tool con un cliente MCP de verdad.

        `perfil` filtra por `beneficiarios` — bug real corregido el
        2026-09-05: hasta entonces esto no se filtraba nunca, así que un
        autónomo/pyme (`perfil="negocio"`, el valor por defecto y el único
        validado) podía ver convocatorias para "personas jurídicas que no
        desarrollan actividad económica" (asociaciones/clubes) que no
        puede solicitar.

        `perfil="particular"` existe pero **no está validado — evaluado
        contra gold set real el 2026-09-05 y sale con 1,3% de precisión**
        (ver docs/f7-mcp-filter-eval.md). `beneficiarios` mide el tipo de
        entidad receptora, no si la ayuda es temáticamente relevante para
        un particular — la mayoría de lo que "encaja" son subvenciones
        municipales nominativas a un club/asociación concreto, ruido para
        cualquier particular real. No usar en producción hasta rediseñar
        con otra señal.
        """
        hoy = datetime.now(UTC).date().isoformat()
        resp = self._client.get(
            "/doc_fields",
            params={
                "select": "doc_id,importe,deadline,ambito,nivel1,cnae,beneficiarios,"
                "documents(title,source_url,published_at)",
                "and": f"(or(abierto.is.null,abierto.eq.true),or(deadline.is.null,deadline.gte.{hoy}))",
            },
        )
        resp.raise_for_status()
        filas = resp.json()

        candidatas = [
            f
            for f in filas
            if sector_encaja(f.get("cnae"), cnae, f.get("nivel1"))
            and perfil_encaja(f.get("beneficiarios"), perfil)
            and ambito_encaja(f.get("ambito"), f.get("nivel1"), ambito)
        ]
        candidatas.sort(key=lambda f: (f["deadline"] is None, f["deadline"] or ""))

        return [
            {
                "doc_id": f["doc_id"],
                "titulo": f["documents"]["title"],
                "url": f["documents"]["source_url"],
                "importe": f["importe"],
                "fecha_limite": f["deadline"],
                "ambito": f["ambito"],
                "nivel1": f["nivel1"],
                "cnae": f["cnae"],
                "beneficiarios": f.get("beneficiarios"),
            }
            for f in candidatas[:limite]
        ]

    def crear_digest(self, user_id: str, n_items: int) -> str:
        """Registra que se generó un digest para este usuario — antes de
        insertar impresiones, porque `impressions.digest_id` es NOT NULL
        (una impresión siempre pertenece a un digest, nunca suelta)."""
        resp = self._client.post(
            "/digests",
            json={"user_id": user_id, "n_items": n_items},
            headers={"Prefer": "return=representation"},
        )
        resp.raise_for_status()
        return resp.json()[0]["digest_id"]

    def registrar_impresiones(self, digest_id: str, user_id: str, filas: list[dict[str, Any]]) -> int:
        """`filas`: cada una con doc_id, position, score, model_version,
        features_json. Se guardan aunque el usuario nunca reaccione — es
        lo que permite luego calcular afinidad incluso a partir de lo que
        NO recibió feedback (base para futuro trabajo, no usado todavía)."""
        if not filas:
            return 0
        payload = [{**f, "digest_id": digest_id, "user_id": user_id} for f in filas]
        resp = self._client.post("/impressions", json=payload, headers={"Prefer": "return=minimal"})
        resp.raise_for_status()
        return len(payload)

    def registrar_feedback(self, impression_id: str, label: Literal["up", "down", "saved", "clicked"]) -> None:
        resp = self._client.post("/feedback", json={"impression_id": impression_id, "label": label})
        resp.raise_for_status()

    def afinidad_sectorial(self, user_id: str) -> dict[str, float]:
        """Puntuación neta de feedback por sector (cnae) para un usuario:
        +1 por 'up'/'saved', -1 por 'down', 'clicked' no puntúa (interés
        débil, no señal de relevancia). Es la pieza que hace que el
        ranking mejore con el uso real, no solo con el filtro estático.

        Dos consultas, no un embed anidado: `impressions` tiene FK a
        `documents`, pero NO a `doc_fields` (aunque comparten `doc_id`),
        así que PostgREST no puede resolver `impressions -> doc_fields`
        en un solo embed — se probó contra la API real y falló con
        PGRST200 ("no matches were found").
        """
        resp = self._client.get(
            "/feedback",
            params={
                "select": "label,impressions!inner(user_id,doc_id)",
                "impressions.user_id": f"eq.{user_id}",
            },
        )
        resp.raise_for_status()
        filas = resp.json()

        peso = {"up": 1.0, "saved": 1.0, "down": -1.0, "clicked": 0.0}
        puntos_por_doc: dict[int, float] = {}
        for f in filas:
            puntos = peso.get(f["label"], 0.0)
            if puntos == 0.0:
                continue
            doc_id = f["impressions"]["doc_id"]
            puntos_por_doc[doc_id] = puntos_por_doc.get(doc_id, 0.0) + puntos
        if not puntos_por_doc:
            return {}

        ids = ",".join(str(d) for d in puntos_por_doc)
        resp = self._client.get("/doc_fields", params={"select": "doc_id,cnae", "doc_id": f"in.({ids})"})
        resp.raise_for_status()
        sectores_por_doc = {f["doc_id"]: f.get("cnae") or [] for f in resp.json()}

        afinidad: dict[str, float] = {}
        for doc_id, puntos in puntos_por_doc.items():
            for sector in sectores_por_doc.get(doc_id, []):
                afinidad[sector] = afinidad.get(sector, 0.0) + puntos
        return afinidad
