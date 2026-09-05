# F7 — evaluación real del filtro de `buscar_convocatorias`

Gold set: 275 candidatas (`data/gold/mcp_candidates_labeled.csv`), etiquetadas
a mano por Sergio con la escala 0/1/2 de
[gold-labeling-criteria.md](gold-labeling-criteria.md) (relevante = etiqueta
≥ 1, mismo criterio que F1). Generadas desde lo ya ingerido en Supabase
con `scripts/build_mcp_gold_candidates.py`, medidas con
`scripts/eval_mcp_filter.py`.

## Resultado

| Grupo | n | relevantes | precisión | recall | accuracy |
|---|---|---|---|---|---|
| negocio/comercio | 26 | 14 | 0,824 | 1,000 | 0,885 |
| negocio/hostelería | 12 | 11 | 1,000 | 1,000 | 1,000 |
| particular/sanitario_social | 73 | 3 | 0,014 | 0,333 | 0,027 |
| particular/artístico_deportivo | 164 | 5 | 0,013 | 0,400 | 0,018 |
| **TOTAL negocio** | 38 | 25 | **0,893** | **1,000** | 0,921 |
| **TOTAL particular** | 237 | 8 | **0,013** | 0,375 | 0,021 |

## Interpretación

**Negocio funciona**: precisión 89%, recall 100% — el filtro (sector por
subcadena + `beneficiarios` exige PYME/actividad económica) no deja fuera
ninguna convocatoria relevante, y casi todo lo que muestra lo es de
verdad.

**Particular no funciona — hallazgo real, no ruido de muestra pequeña**:
precisión 1,3%. La hipótesis de partida (2026-09-04: "~94% de
sanitario/social son `beneficiarios` = personas jurídicas sin actividad
económica, luego encajan con 'particular'") era incorrecta. Esas
convocatorias son subvenciones municipales nominativas a una asociación o
club **concreto** (ej. una banda de música o un club deportivo local de
un ayuntamiento pequeño), no ayudas genéricas que interesen a un
particular cualquiera. `beneficiarios` mide el tipo de entidad receptora,
no si la ayuda es temáticamente relevante para un particular — eran dos
cosas distintas que se trataron como una.

## Consecuencia

El selector "particular/asociación" en el onboarding de Lovable (F4,
2026-09-04) queda con un filtro que no aporta valor — pendiente de
decidir si se rediseña (con qué señal, si `beneficiarios` no sirve) o se
retira del producto. No afecta a usuarios reales: `is_published=false`.

`buscar_convocatorias(perfil="negocio")` (el uso por defecto, y el único
validado) no necesita cambios.
