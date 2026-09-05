# F8 — filtro real de ámbito (provincia)

`buscar_convocatorias` (Python) y el dashboard de Lovable tenían un
parámetro `ambito`/`profiles.ambito` que nunca filtraba nada: comparaban
texto libre del perfil (p.ej. `"Comunitat Valenciana"`) contra texto
libre de BDNS (`doc_fields.ambito`, tipo `"ES523 - Valencia / València"`)
— esas dos cadenas nunca coincidían, así que el filtro era, de hecho, un
permisivo total disfrazado de filtro.

## Qué da realmente BDNS

`doc_fields.ambito` es un array con un único código de provincia (NUTS3/
INE) por convocatoria, con el nombre pegado detrás. Comprobado contra las
422 filas reales de la base: solo aparecen tres, sin excepción —
`ES521` (Alicante), `ES522` (Castellón), `ES523` (Valencia). No hay
municipio ni nada más fino. Eso fija el límite real de precisión de este
filtro: provincia, no ciudad.

## Solución

Sin migración de esquema — `profiles.ambito` sigue siendo `text`, solo
cambia su significado: pasa a guardar uno de los tres códigos, o `""`/
cualquier otro valor no reconocido = sin filtrar (permisivo, mismo
comportamiento que tenían todos los perfiles hasta ahora).

- **`storage.py`**: `ambito_encaja(ambito_doc, nivel1, provincia_buscada)`
  — mismo patrón que `sector_encaja`/`perfil_encaja`. ESTATAL siempre
  encaja; si `provincia_buscada` no es uno de los tres códigos, permisivo;
  si la convocatoria no tiene ámbito conocido, permisivo. Conectado al
  parámetro `ambito` ya existente en `buscar_convocatorias` (antes
  ignorado) y en `digest.py` (`generar_digest_usuario` ya lo pasa desde
  `perfil["ambito"]`).
- **`mcp_server.py`**: docstring de la tool actualizada — antes decía
  "de momento informativo, no filtra de forma estricta", ahora documenta
  los tres códigos válidos.
- **Lovable (`onboarding.tsx`)**: el `Input` de texto libre se sustituye
  por un `Select` con las 3 provincias + "toda la Comunitat Valenciana".
  Un perfil con el valor heredado (texto libre) se trata como "toda la
  CV" al cargar el formulario, no como un valor roto.
- **Lovable (`dashboard.tsx`)**: `matchesAmbito`, espejo exacto de
  `ambito_encaja` en TypeScript, sustituye al `scopeOk` que antes
  aceptaba cualquier `nivel1` sin mirar nada.

## Validado contra datos reales, no solo mocks

Con las 422 filas reales de `doc_fields` (vía `SupabaseStorage`, no el
MCP de Supabase — ver nota más abajo):

```
ES523 (Valencia)  -> 232 de 422 encajan
ES521 (Alicante)  -> 119 de 422 encajan
ES522 (Castellón) ->  71 de 422 encajan
valor heredado ("Comunitat Valenciana") -> 422 de 422 (permisivo, sin regresión)
```

232 + 119 + 71 = 422: cada convocatoria tiene exactamente una provincia,
así que el filtro particiona los datos correctamente, sin solapes ni
pérdidas. El perfil real existente hoy sigue viendo todo hasta que se
vuelva a guardar con el desplegable nuevo — sin regresión para el único
usuario actual.

## Nota: el MCP de Supabase de esta sesión no apuntaba a este proyecto

Al empezar esta tarea, `list_projects` del MCP de Supabase solo devolvía
un proyecto llamado "WayWin" (tablas de viajes/apuestas, nada que ver
con TrackerAID) — no el proyecto real (`ohcripltqainujxxyakd`, según
`.env`). No se tocó nada por esa vía; toda la validación de este
documento se hizo con `SupabaseStorage` (el mismo cliente que usa la app
en producción) contra el proyecto real. Pendiente: revisar por qué el
MCP de Supabase de esta sesión no lista el proyecto correcto.
