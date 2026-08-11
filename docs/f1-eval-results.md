# Resultados del harness de eval — primera pasada con gold set real

Primera corrida de `scripts/run_eval.py` sobre etiquetas humanas confirmadas
(columna `relevance` de `data/gold/candidates.csv`, no `heuristic_relevance`).
Anotador: Sergio. 169 de 450 candidatas etiquetadas (93 con relevancia 0,
5 con 1, 71 con 2) — dentro del objetivo de 150-300 pares del
[criterio de etiquetado](gold-labeling-criteria.md), aunque quedan 281 filas
sin revisar si se quiere ampliar el gold set más adelante.

## BM25 sobre la query genérica de perfil CV

| k | precision@k | recall@k | nDCG@k |
|---|---|---|---|
| 5 | 1.000 | 0.066 | 1.000 |
| 10 | 0.900 | 0.118 | 0.887 |
| 20 | 0.950 | 0.250 | 0.905 |

MRR: 1.000

## Cómo leer esto (y su límite honesto)

Estos números son buenos en parte porque el subconjunto etiquetado (169 de
450) tiene una proporción de relevantes mucho más alta (76/169 ≈ 45%) que la
que tendría un flujo real de convocatorias entrando cada semana — donde,
según [f1-coverage-report.md](f1-coverage-report.md), solo ~4.5% está abierto
en un momento dado y la proporción temáticamente relevante también es baja.
BM25 lo tiene "fácil" aquí porque la query genérica comparte vocabulario casi
literal con las descripciones marcadas como relevantes (empresas, pymes,
digitalización...).

Esto no invalida el resultado — confirma que el mecanismo de retrieval
funciona correctamente sobre el vocabulario esperado — pero significa que
**recall@20 = 0.25 es el número que de verdad importa vigilar**: de los
documentos relevantes que existen en la muestra, BM25 solo trae 1 de cada 4
en el top 20. Ahí es donde embeddings (para capturar sinónimos y paráfrasis
que BM25 no ve por coincidencia léxica) debería aportar la mejora real —
siguiente paso de la tabla de ablación.

## Siguiente paso

- Añadir el baseline de embeddings y la fila híbrida a esta tabla.
- Opcional: ampliar el gold set más allá de 169 si el recall@20 no mejora
  lo suficiente con embeddings — podría ser señal de que faltan ejemplos
  relevantes diversos, no solo mejor retrieval.
