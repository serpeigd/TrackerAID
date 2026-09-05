# F6 — bucle de feedback (👍/👎 → reentrena el ranking)

Primer uso real de las tablas `digests`/`impressions`/`feedback`, vacías
desde que se creó el esquema. Cierra el hueco más grande que quedaba del
roadmap original del `CLAUDE.md` del proyecto.

## Piezas

- **`src/trackeraid/ranking.py`**: heurística transparente, no ML.
  Puntúa cada candidata (ya filtrada por `buscar_convocatorias`) sumando
  tres señales: solape de sector con el perfil, proximidad del plazo, y
  afinidad histórica de feedback del propio usuario por sector.
- **`src/trackeraid/digest.py`**: orquesta — pide candidatas, calcula
  afinidad, rankea, y GUARDA el digest (`digests` + `impressions`). No
  envía ningún email todavía.
- **`SupabaseStorage`**: `crear_digest`, `registrar_impresiones`,
  `registrar_feedback`, `afinidad_sectorial`.
- **`GET /feedback?impression_id=...&label=up|down|saved|clicked`**: GET
  a propósito (no POST) — tiene que poder dispararse desde un enlace de
  email de un solo clic, sin formulario ni JavaScript.

## Bug real encontrado probando contra Supabase de verdad, no solo mocks

`afinidad_sectorial` intentó primero un embed anidado de PostgREST
(`feedback -> impressions -> doc_fields`) que parecía razonable pero
falló con `PGRST200`: `impressions` tiene FK a `documents`, pero **no**
a `doc_fields` (aunque comparten `doc_id`) — PostgREST no puede resolver
ese camino en un solo embed. Arreglado con dos consultas (feedback+
impressions primero, luego doc_fields por los doc_id resultantes) en vez
de una sola anidada.

## Validado en vivo, con un resultado honesto

Al probar `generar_digest_usuario` contra el perfil real de prueba, dio
0 resultados — no por un bug, sino porque **las 21 convocatorias
abiertas ahora mismo son el 100% para particular, 0% para negocio**
(mismo patrón que ya documentó `f7-mcp-filter-eval.md`). El mecanismo
(consulta, ranking, guardado en Supabase) funciona correctamente; lo que
falta es que el pipeline traiga más convocatorias abiertas de negocio,
no un fallo de este código.

## Qué falta para que esto sea el "email semanal" real

1. **Envío del email** — no construido en esta pasada. Podría reutilizar
   el nodo Gmail de n8n ya montado para los avisos de error, apuntado a
   una nueva plantilla con los `top_n` de `generar_digest_usuario` y
   enlaces `GET /feedback?...` para cada 👍/👎.
2. **Programar la generación semanal** — un script/tarea que recorra
   `profiles` y llame a `generar_digest_usuario` por cada uno (el propio
   `pipeline.py` de ingesta ya corre semanalmente vía n8n; esto sería un
   paso más en el mismo cron, o uno aparte).
3. **Botones 👍/👎 en el dashboard de Lovable** — hoy el dashboard hace su
   propia consulta en vivo, no lee de `impressions`. Conectarlo al digest
   guardado (en vez de una query en vivo) es un cambio de arquitectura
   del dashboard que merece su propia ronda, no se ha tocado aquí.
