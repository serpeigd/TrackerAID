"""Autenticación mínima de los dos endpoints de escritura de `api.py`.

Dos mecanismos distintos, para dos problemas distintos:

- `POST /pipeline/ingest`: solo n8n debe poder dispararlo. Shared secret
  simple (cabecera `X-Ingest-Token`) comparado contra `INGEST_TOKEN`.
- `GET /feedback`: tiene que poder dispararse con un solo clic sin sesión
  desde un enlace de email (ver `api.py`), así que no hay usuario
  autenticado que verificar. Sin nada más, cualquiera que adivinara o
  interceptara un `impression_id` -- incluido un rastreador de enlaces
  del propio cliente de correo, que sigue redirects para escanear virus
  antes de que el usuario haga clic -- podría registrar feedback falso.
  Se firma el `impression_id` con HMAC-SHA256 al crear el digest
  (`digest.py`) y se verifica aquí: sin la firma correcta no se puede
  fabricar un feedback válido.

Fail-closed en los dos casos: si el secreto correspondiente no está
configurado en el entorno, se rechaza todo en vez de dejar pasar --  lo
contrario (permisivo cuando falta configurar algo) es el bug de
seguridad clásico de la autenticación que se desactiva sola.
"""

from __future__ import annotations

import hashlib
import hmac

from trackeraid.config import settings


def verificar_ingest_token(token: str) -> bool:
    if not settings.ingest_token:
        return False
    return hmac.compare_digest(token, settings.ingest_token)


def firmar_impression_id(impression_id: str) -> str:
    """Llamada al crear el digest (`digest.py`), con el `impression_id`
    ya generado en Python -- antes de que exista ninguna petición HTTP
    que verificar."""
    if not settings.feedback_hmac_secret:
        raise RuntimeError(
            "FEEDBACK_HMAC_SECRET no configurado (.env) -- no se puede firmar feedback sin él."
        )
    return hmac.new(
        settings.feedback_hmac_secret.encode(), impression_id.encode(), hashlib.sha256
    ).hexdigest()


def feedback_valido(impression_id: str, sig: str) -> bool:
    if not settings.feedback_hmac_secret or not sig:
        return False
    return hmac.compare_digest(firmar_impression_id(impression_id), sig)
