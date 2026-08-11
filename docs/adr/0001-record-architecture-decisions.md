# 0001. Registrar decisiones de arquitectura con ADRs

## Estado
Aceptado — 2026-08-11

## Contexto
El proyecto combina herramientas no-code (Lovable, n8n, Make) con un
núcleo Python. Sin registro explícito de decisiones, es fácil que la
lógica se disperse entre nodos de n8n y prompts sueltos, y que el
razonamiento detrás de cada elección se pierda.

## Decisión
Cada decisión de arquitectura con impacto real (elección de fuente de
datos, dónde vive la lógica, modelo de embeddings, hosting, esquema de
datos) se documenta en `docs/adr/` como un ADR corto: contexto, decisión,
consecuencias. Formato inspirado en Michael Nygard.

## Consecuencias
Coste marginal por decisión (~10 minutos). A cambio, el README puede
enlazar a los ADRs en vez de re-explicar el razonamiento, y sirve como
evidencia de criterio técnico para quien revise el repo.
