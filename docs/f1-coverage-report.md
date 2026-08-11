# Cobertura de campos estructurados — BDNS, Comunitat Valenciana

Medido el 2026-08-11 sobre una muestra de **200 convocatorias**
de los últimos 90 días (regiones Alicante/Castellón/Valencia).
Reproducible con `python scripts/explore_coverage.py`.

| Campo | Cobertura estructurada | Decisión F2 |
|---|---|---|
| `importe` (presupuestoTotal) | 200/200 (100.0%) | reglas suficientes |
| `fecha_fin_solicitud` (plazo) | 102/200 (51.0%) | LLM/regex sobre el PDF para el resto |
| `sectores` (~CNAE) | 200/200 (100.0%) | reglas suficientes |
| `abierto` (convocatoria vigente) | 9/200 (4.5%) siguen abiertas | — |

Muestra cruda (gitignored, no se versiona): `data/raw/bdns_cv_sample.jsonl`.

## Hallazgo de producto: filtrar por fecha de publicación no basta

Solo el 4.5% de las convocatorias publicadas en los últimos 90 días siguen
`abierto=true` hoy — la mayoría del volumen es histórico ya cerrado (actas,
convenios nominativos, resoluciones de concesión que también entran por el
mismo endpoint). **Consecuencia para el pipeline (F1/F3): el filtro
correcto para el radar es `abierto=true` explícito, no solo una ventana de
fechaDesde.** Filtrar solo por fecha habría llenado el digest semanal de
convocatorias ya cerradas — hay que aplicar ambos filtros a la vez.

`busqueda` no acepta `abierto`/`estado` como filtro server-side (probado:
con y sin el parámetro devuelve exactamente los mismos resultados, en el
mismo orden — se ignora en silencio). El filtro por `abierto` solo puede
hacerse en cliente, tras pedir el detalle de cada candidata. No cambia el
diseño (F2 ya necesita el detalle para extraer `importe`/`fecha_fin_solicitud`),
pero descarta la idea de pedir solo las abiertas a la API para ahorrar
llamadas.

## Bug de la API encontrado y corregido

`fechaDesde`/`fechaHasta` exigen formato `dd/mm/yyyy`, no ISO 8601 como el
resto de la API — con formato ISO la API devuelve `400 ERR_VALIDACION`. No
está documentado en ningún sitio público; se encontró por prueba y error
contra la API real. Corregido en `BDNSClient.buscar()`
([src/trackeraid/ingestion/bdns.py](../src/trackeraid/ingestion/bdns.py)).
