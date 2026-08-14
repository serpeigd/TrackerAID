# CLAUDE.md — TrackerAID

Memoria del proyecto para Claude Code.

Radar semántico de subvenciones públicas (BDNS) para autónomos y pymes de la
Comunitat Valenciana: ingesta semanal → extracción de campos → ranking por
perfil de negocio → email semanal con feedback 👍/👎 que reentrena el ranking.

## Convenciones

- **El contenido del repo (README, docs, ADRs, mensajes de commit) va en español**,
  como el producto. La conversación con Sergio también.
- Toda la lógica de retrieval, extracción y ranking vive en Python, testeada y
  versionada. n8n y Make solo orquestan y notifican — **nunca** contienen lógica
  de negocio (ADR-0003). No mover lógica a un nodo de n8n "porque es más rápido".
- Las decisiones de arquitectura se documentan como ADR en `docs/adr/`, formato
  Nygard, cada una con la alternativa que se descartó.
- **Gratis por diseño.** El plazo se resuelve con campo estructurado → regex →
  LLM local (Ollama). `ANTHROPIC_API_KEY` existe en `.env.example` solo para
  comparar calidad/coste; el pipeline no la necesita. Antes de meter cualquier
  servicio de pago, pregunta.
- **Sé breve (2026-08-13, petición explícita en chat).** Demasiado texto y demasiadas
  explicaciones. Empieza por la respuesta o por el cambio; el razonamiento solo si
  cambia una decisión. No resumas trabajo que ya se ve en el diff, no repitas la
  pregunta antes de contestarla, y no cierres con una frase-conclusión. Aplica al
  chat, a los mensajes de commit y a los cuerpos de PR. Los documentos de referencia
  (README, este archivo) pueden ser largos, pero solo donde la extensión se gane.

## Ninguna cifra sin denominador

Es el principio que ordena este repo, no un detalle de estilo: la calidad de
retrieval se mide, no se asume. `scripts/run_eval.py` avisa explícitamente
cuando corre sobre etiquetas heurísticas provisionales en vez del gold set
revisado a mano. Al reportar resultados, ese contexto va siempre — incluido el
número que queda mal. Hoy el que queda mal es `recall@20 = 0,153`, junto a
`MRR = 1,00` y `precision@20 = 0,95`.

Lo mismo con el plazo: el 8,7% que no se resuelve se marca como no resuelto,
no se adivina. La fecha vive en el PDF de las bases, que este pipeline no abre.

## Estado (2026-08-13)

F0, F1 y F2 completadas; F3 en marcha.

- **F1**: cobertura de campos medida, gold set completo (443/450 pares
  confirmados a mano), baseline BM25 evaluado. Resultados en
  `docs/f1-eval-results.md`.
- **F2**: cascada de extracción de plazo en tres niveles, 137/150 resueltas
  (91,3%) sin coste. Detalle en `docs/f2-deadline-coverage.md`, reproducible con
  `scripts/measure_deadline_coverage.py`.
- **F3**: ya están el pipeline de ingesta a Supabase (`pipeline.py`), la API
  FastAPI (`api.py`) y el scaffold de n8n. Falta el email verificado
  (SPF/DKIM/DMARC), así que la fase **no** está cerrada.

Los scripts del stack (`scripts/start-pipeline-stack.ps1` y su pareja) son
PowerShell, atados al entorno de desarrollo actual.

## Sobre la tarea programada de sincronización de docs

- **Autorización permanente para mergear PRs solo-documentación de esa tarea
  (2026-08-14, decisión explícita en chat), en cuanto el CI esté verde.** Mismo
  listón que cualquier merge, solo que sin paso de confirmación, y solo para
  este caso concreto: cambios en README/`docs/`, nunca en código de producto.
  Si algún check falla, no mergees — avisa con el motivo.
- Esa ejecución corre en una rama nueva con nombre aleatorio cada vez, así que
  una PR de un run anterior nunca se reutiliza sola. Antes de abrir otra,
  comprueba si ya hay una PR de docs abierta: si la hay, incorpora lo que siga
  siendo válido y avisa, en vez de dejar dos abiertas.
- Precedente real: la PR #1 (11 ago) se quedó abierta hasta el 13 y para
  entonces la mitad de lo que afirmaba era falso — decía que `extraction/` era
  un placeholder y que el gold set no tenía ninguna etiqueta humana. **Una PR de
  documentación caduca rápido en un repo que avanza por fases.** Al recuperar
  contenido de una PR vieja, contrástalo contra el código antes de copiarlo.

## Archivos clave

| Área | Archivo |
|---|---|
| Cliente de la API pública de BDNS | `src/trackeraid/ingestion/bdns.py` |
| Extracción de plazo (regex + LLM local) | `src/trackeraid/extraction/deadline.py`, `llm_ollama.py` |
| Baseline BM25 y métricas de IR | `src/trackeraid/retrieval/bm25.py`, `metrics.py` |
| Orquestación de la ingesta semanal | `src/trackeraid/pipeline.py` |
| API que dispara n8n | `src/trackeraid/api.py` |
| Configuración centralizada (único sitio que lee entorno) | `src/trackeraid/config.py` |
| Decisiones de arquitectura | `docs/adr/` |
| Criterio de etiquetado del gold set | `docs/gold-labeling-criteria.md` |
