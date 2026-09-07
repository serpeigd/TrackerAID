# Servidor MCP de TrackerAID

Expone `buscar_convocatorias` como herramienta que cualquier agente
compatible con MCP (Claude Desktop, Claude Code, ChatGPT con conectores)
puede llamar. Código en `src/trackeraid/mcp_server.py`, reutiliza
`SupabaseStorage` — la misma clase que ya usa `pipeline.py`.

## Por qué es así de pequeño a propósito

v1 deliberadamente limitada, por diseño de mínimo privilegio:

- **Solo lectura.** Ninguna tool escribe ni dispara el pipeline — eso
  requeriría autenticación por API key como mínimo, y confirmación humana
  antes de ejecutar nada (ver `docs/adr/` para el criterio ya aplicado en
  n8n: nunca acciones automáticas sin supervisión).
- **Sin datos de perfil de usuario.** Solo consulta `documents`/
  `doc_fields` (información pública de BDNS). Si se quisiera personalizar
  por el perfil de un usuario concreto, haría falta OAuth por usuario —
  mucho más trabajo, pospuesto a propósito.

## Cómo lo pruebas tú (esto no lo puedo hacer yo por ti)

El servidor habla por `stdio` (proceso local) — no necesita hosting ni
internet para esta prueba. Regístralo en tu propio Claude Code:

```bash
claude mcp add trackeraid -- "<ruta-a-tu-venv>\Scripts\python.exe" -m trackeraid.mcp_server
```

Reinicia Claude Code (o abre una sesión nueva) y pregunta algo como:

> "Usa la herramienta buscar_convocatorias para encontrarme ayudas de
> comercio en la Comunitat Valenciana"

Deberías ver que el agente **decide llamar a la tool** (no que responde de
memoria), y que el resultado son datos reales de tu Supabase. Eso es lo
que hay que observar para entender de verdad el patrón LLM → decide tool
→ ejecuta → responde con el resultado — es la Fase 6 del plan (tool
calling) ocurriendo delante de ti, no una explicación teórica.

También puedes probarlo suelto, sin ningún agente, para depurar:

```bash
.venv\Scripts\python.exe -c "from trackeraid.mcp_server import buscar_convocatorias; print(buscar_convocatorias(limite=3))"
```

## Qué falta para que un agente externo (ChatGPT, Claude.ai) lo use

Por `stdio` solo lo alcanza software que corre en tu propia máquina. Para
que un agente en la nube lo llame, hace falta:

1. Transporte HTTP en vez de stdio (`mcp.run(transport="streamable-http")`).
2. Un host público — mismo requisito que ya teníamos pendiente para F5
   (Railway/Fly.io free tier).
3. Autenticación propia — el servidor MCP habla con `SupabaseStorage`
   directamente, sin pasar por `api.py`, así que el `X-Ingest-Token` que
   ya protege `POST /pipeline/ingest` (ver `docs/n8n-setup.md` y
   `src/trackeraid/auth.py`) no le sirve; necesitaría su propio mecanismo
   si se expone fuera de la máquina.

No es trabajo nuevo: es la misma pieza de infraestructura que llevamos
aplazando, ahora con una razón más concreta para resolverla.
