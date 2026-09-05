"""Tests del servidor MCP — la capa que un agente externo llama de verdad,
separada de la lógica interna ya cubierta en test_storage.py."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

from trackeraid.mcp_server import buscar_convocatorias, mcp


def test_tool_registrada_con_el_nombre_esperado():
    tools = asyncio.run(mcp.list_tools())
    nombres = [t.name for t in tools]
    assert "buscar_convocatorias" in nombres


def test_tool_no_expone_perfil_particular_sin_validar():
    # perfil="particular" existe en SupabaseStorage (para scripts de
    # evaluación) pero no debe ofrecerse a un agente externo -- ver
    # docs/f7-mcp-filter-eval.md (precisión 1,3%).
    tools = asyncio.run(mcp.list_tools())
    tool = next(t for t in tools if t.name == "buscar_convocatorias")
    assert "perfil" not in tool.inputSchema["properties"]


def test_buscar_convocatorias_fuerza_perfil_negocio():
    with patch("trackeraid.mcp_server.SupabaseStorage") as mock_storage_cls:
        mock_storage = mock_storage_cls.return_value.__enter__.return_value
        mock_storage.buscar_convocatorias.return_value = []

        buscar_convocatorias(cnae=["comercio"], limite=5)

        mock_storage.buscar_convocatorias.assert_called_once_with(
            cnae=["comercio"], ambito=None, perfil="negocio", limite=5
        )
