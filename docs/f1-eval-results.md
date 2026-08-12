# Resultados del harness de eval — gold set completo

`scripts/run_eval.py` sobre etiquetas humanas confirmadas (columna
`relevance` de `data/gold/candidates.csv`, no `heuristic_relevance`).
Anotador: Sergio. **443 de 450 candidatas etiquetadas** (319 con relevancia
0, 31 con 1, 93 con 2) — quedan 7 filas sin etiqueta (se perdieron al fusionar
un export intermedio, no afectan al resultado de forma relevante).

*(Primera pasada parcial, con 169 etiquetas, en el historial de git —
sustituida por esta al completar el gold set.)*

## BM25 sobre la query genérica de perfil CV

| k | precision@k | recall@k | nDCG@k |
|---|---|---|---|
| 5 | 0.800 | 0.032 | 0.462 |
| 10 | 0.900 | 0.073 | 0.651 |
| 20 | 0.950 | 0.153 | 0.730 |

MRR: 1.000 · 124 documentos relevantes de 443 evaluados (28%)

## Cómo leer esto

Con el gold set casi completo, la proporción de relevantes (28%) ya se
parece más a un escenario real que en la pasada parcial anterior (45%), así
que estos números son los que cuentan como línea base del proyecto.

- **MRR=1.000**: el primer resultado casi siempre es relevante — la query
  genérica funciona bien para encontrar *algo* bueno rápido.
- **precision@20=0.95**: de las 20 primeras, 19 son relevantes — muy poco
  ruido en el top.
- **recall@20=0.153, el número que de verdad importa vigilar**: de los 124
  documentos relevantes que hay en la colección, BM25 solo trae 1 de cada
  6-7 en el top 20. Con una sola query genérica compitiendo contra 443
  documentos (en vez de contra el volumen real semanal, mucho menor), es
  esperable que el recall absoluto sea bajo — la pregunta relevante no es
  "¿es bajo?" sino "¿sube con embeddings?", que es la comparación real que
  importa para decidir si compensa el coste de calcularlos.

## Siguiente paso

- Añadir el baseline de embeddings y la fila híbrida a esta tabla — ahí se
  ve si recall@20 mejora de verdad frente a BM25 solo.
- Las 7 filas sin etiquetar pueden completarse cuando se quiera, no bloquean
  nada — ya se superó de sobra el objetivo de 150-300 pares.
