"""Servidor MCP de TrackerAID.

Expone la búsqueda de convocatorias como herramienta que cualquier agente
compatible con MCP (Claude Desktop, Claude Code, ChatGPT con conectores)
puede descubrir y llamar. Reutiliza `SupabaseStorage`, la misma clase que
ya usa `pipeline.py` — cero lógica nueva, solo una forma nueva de
exponerla.

v1 deliberadamente limitada, por diseño de mínimo privilegio:
- Solo lectura. Sin ninguna tool que escriba o dispare el pipeline.
- Sin datos de perfil de usuario (`profiles`/`consents`) — solo
  convocatorias públicas de BDNS, evitando así tener que resolver
  autenticación por usuario en esta primera versión.

Uso local (stdio, sin exponer nada a internet):
    claude mcp add trackeraid -- <ruta-al-venv>/python -m trackeraid.mcp_server

Ver docs/mcp-server.md para cómo probarlo y qué falta para exponerlo por
HTTP a un agente externo.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from trackeraid.storage import SupabaseStorage

mcp = FastMCP("trackeraid")


@mcp.tool()
def buscar_convocatorias(
    cnae: list[str] | None = None,
    ambito: str | None = None,
    limite: int = 20,
) -> list[dict[str, Any]]:
    """Busca convocatorias de subvenciones públicas abiertas y con plazo
    vigente en la Comunitat Valenciana (o sin fecha límite publicada),
    dirigidas a autónomos y pymes.

    Args:
        cnae: sectores de actividad a priorizar (ej. ["comercio", "turismo"]).
            Filtra por coincidencia parcial, sin distinguir mayúsculas. Sin
            filtro si se omite.
        ambito: código de provincia de la Comunitat Valenciana a priorizar
            — "ES521" (Alicante), "ES522" (Castellón) o "ES523" (Valencia).
            Es la única granularidad geográfica que da BDNS hoy, no hay
            municipio. Cualquier otro valor (u omitirlo) no filtra por
            ámbito.
        limite: máximo de resultados a devolver (por defecto 20).

    Devuelve una lista de convocatorias con título, URL oficial, importe,
    fecha límite, ámbito, sector y a quién van dirigidas.
    """
    # `SupabaseStorage.buscar_convocatorias` también acepta perfil="particular",
    # pero no está validado (precisión 1,3% en el gold set real, ver
    # docs/f7-mcp-filter-eval.md) — no se expone aquí a propósito para que
    # ningún agente externo lo use hasta rediseñarlo.
    with SupabaseStorage() as storage:
        return storage.buscar_convocatorias(cnae=cnae, ambito=ambito, perfil="negocio", limite=limite)


if __name__ == "__main__":
    mcp.run()
