"""Genera y guarda el digest semanal de un usuario: candidatas -> ranking
-> impresiones en Supabase. Orquesta `storage.py` y `ranking.py` sin
lógica propia — mismo patrón que `pipeline.py`.

El envío del digest por email (el paso que faltaría para que esto sea el
correo semanal real que describe el CLAUDE.md del proyecto) NO vive
aquí todavía — esto genera y guarda el digest, la entrega es un paso
aparte (podría reutilizar el nodo Gmail de n8n ya construido para los
avisos de error).
"""

from __future__ import annotations

import uuid
from typing import Any

from trackeraid.auth import firmar_impression_id
from trackeraid.ranking import rankear
from trackeraid.storage import SupabaseStorage

MODEL_VERSION = "heuristico-v1"


def generar_digest_usuario(storage: SupabaseStorage, perfil: dict[str, Any], top_n: int = 10) -> dict[str, Any]:
    """`perfil`: fila de `profiles` (necesita al menos `user_id`, y
    opcionalmente `cnae` y `ambito` -- este último solo filtra de verdad
    si es un código de provincia de la CV, ver docstring de
    `SupabaseStorage.buscar_convocatorias`). Genera, puntúa y GUARDA el
    digest (crea `digests` + `impressions`) — no envía ningún email.

    Cada `impression_id` se genera aquí, en Python (no lo asigna
    Supabase) -- así se puede firmar con HMAC (`auth.firmar_impression_id`)
    ANTES de insertarlo, para componer el enlace de feedback de un clic
    (`GET /feedback?impression_id=...&sig=...`) sin tener que volver a
    leer la fila recién creada.

    Devuelve {digest_id, n_items, convocatorias} para quien quiera
    componer el email o mostrarlo en el dashboard -- cada convocatoria
    lleva ya su `impression_id` y `feedback_sig`.
    """
    user_id = perfil["user_id"]
    cnae_perfil = perfil.get("cnae") or None

    candidatas = storage.buscar_convocatorias(cnae=cnae_perfil, ambito=perfil.get("ambito"), limite=100)
    afinidad = storage.afinidad_sectorial(user_id)
    rankeadas = rankear(candidatas, cnae_perfil, afinidad, top_n=top_n)

    digest_id = storage.crear_digest(user_id, n_items=len(rankeadas))

    filas = []
    convocatorias = []
    for i, c in enumerate(rankeadas):
        impression_id = str(uuid.uuid4())
        filas.append(
            {
                "impression_id": impression_id,
                "doc_id": c["doc_id"],
                "position": i,
                "score": round(c["score"], 4),
                "model_version": MODEL_VERSION,
                "features_json": {"cnae": c.get("cnae"), "fecha_limite": c.get("fecha_limite")},
            }
        )
        convocatorias.append(
            {**c, "impression_id": impression_id, "feedback_sig": firmar_impression_id(impression_id)}
        )

    storage.registrar_impresiones(digest_id, user_id, filas)
    return {"digest_id": digest_id, "n_items": len(rankeadas), "convocatorias": convocatorias}
