# TrackerAID

[![CI](https://github.com/serpeigd/TrackerAID/actions/workflows/ci.yml/badge.svg)](https://github.com/serpeigd/TrackerAID/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

> Radar semántico de subvenciones públicas para autónomos y pymes de la Comunitat Valenciana.

**Estado: en construcción (F0 completada, F1 en marcha).** Este README se actualiza fase a fase — ver [roadmap](#roadmap) y [ADRs](docs/adr/).

📊 [Cobertura real de campos en BDNS](docs/f1-coverage-report.md) · 📋 [Criterio de etiquetado del gold set](docs/gold-labeling-criteria.md)

## Qué hace

Cada semana, `TrackerAID` ingiere las convocatorias de subvenciones publicadas en
[BDNS](https://www.infosubvenciones.es/) (el registro legal centralizado de
ayudas públicas de España), extrae sus campos clave (importe, plazo, ámbito,
CNAE) y las ordena por relevancia para el perfil de negocio de cada usuario.
El usuario recibe un email semanal con las mejores; cada 👍/👎 que da se
convierte en una etiqueta que reentrena el ranking.

## Por qué existe

Es un proyecto de portfolio con un objetivo doble: aprender cuatro
herramientas nuevas (Lovable, motionsites.ai, Make, n8n) construyendo algo
real, y producir una pieza de ingeniería de datos/ML que se sostenga en una
entrevista técnica — no una demo, sino un sistema con datos reales, un gold
set etiquetado a mano y un loop de feedback medido.

**Principio de diseño (ver [ADR-0003](docs/adr/0003-logica-en-python-no-en-n8n.md)):**
toda la lógica de retrieval, extracción y ranking vive en Python, testeada y
versionada. n8n y Make solo orquestan y notifican — nunca contienen lógica de
negocio.

## Arquitectura

```
BDNS API ──▶ ingestion (Python) ──▶ Postgres/pgvector (Supabase)
                                          │
                                    retrieval + extracción (Python)
                                          │
                                    ranking / reranker (Python)
                                          │
                    n8n (cron semanal) ──▶ email (Resend) ──▶ usuario
                                          │
                              feedback (👍/👎) ──▶ Supabase ──▶ reentrenamiento
```

- **Núcleo**: Python (FastAPI + retrieval/extraction), tests + CI.
- **Datos**: Postgres con pgvector en Supabase, RLS por usuario.
- **Orquestación**: n8n autoalojado en Docker (cron semanal, llama a la API).
- **Producto**: app en Lovable (alta, perfil, feedback) + landing con secciones generadas con prompts de motionsites.ai. Repo: [trackeraid-onboarding-pro](https://github.com/serpeigd/trackeraid-onboarding-pro) (privado por ahora — se abre en F5).
- **Embeddings**: locales (multilingual-e5 / bge-m3), en batch. LLM solo para extracción estructurada del top-N, con caché por hash y presupuesto mensual duro.

Decisiones documentadas en detalle: [ADR-0001](docs/adr/0001-record-architecture-decisions.md) · [ADR-0002 (fuente única BDNS)](docs/adr/0002-fuente-unica-bdns.md) · [ADR-0003 (lógica en Python)](docs/adr/0003-logica-en-python-no-en-n8n.md).

### Estructura del repo

```
src/trackeraid/
  config.py          Configuración centralizada (lee .env / os.environ)
  ingestion/bdns.py   Cliente de solo lectura sobre la API pública de BDNS
  retrieval/          Baseline BM25 (bm25.py) + métricas de IR (metrics.py)
  extraction/          Extracción estructurada de campos — placeholder, se implementa en F2

scripts/
  explore_coverage.py     F1 — mide cobertura de campos estructurados en BDNS
  build_gold_candidates.py  F1 — genera la hoja de candidatas para el gold set
  run_eval.py              F1 — corre el baseline BM25 sobre el gold set y reporta métricas

sql/001_init_schema.sql   Esquema Postgres/pgvector (se aplica vía Supabase en F4)
data/gold/                Gold set curado a mano — SÍ se versiona (ver .gitignore)
data/raw/                 Muestras crudas de BDNS — NO se versiona, regenerable
docs/adr/                 Decisiones de arquitectura (formato Nygard)
tests/                    pytest — unitarios (mockeados con respx) + marcados `integration`
```

## Evaluación

El repo trata la calidad de retrieval como algo que se mide, no se asume:

- Gold set etiquetado a mano (`data/gold/`) con criterio de etiquetado documentado.
- Tabla de ablación BM25 / embeddings / híbrido / +reranker sobre recall@20, nDCG@10, precision@5, latencia y coste.
- CI que falla si nDCG@10 cae por debajo de un umbral respecto al baseline.
- Página pública de métricas que se regenera sola cada semana (F7).

Baseline BM25 implementado y testeado (`src/trackeraid/retrieval/`, `python scripts/run_eval.py`). Embeddings e híbrido, pendientes. La tabla de ablación real se publica en cuanto `data/gold/candidates.csv` tenga la columna `relevance` revisada a mano — hasta entonces el script avisa explícitamente que corre sobre etiquetas heurísticas provisionales (estado actual: 450 candidatas con `heuristic_relevance` generada, 0 revisadas a mano en `relevance`).

## Desarrollo

```bash
pip install -e ".[dev,eval]"   # dev: pytest/ruff · eval: rank-bm25/numpy/scikit-learn (necesarios para tests y scripts de F1)
pytest                         # tests unitarios (sin red)
pytest -m integration          # smoke test contra la API real de BDNS
ruff check src tests scripts
```

### Scripts de F1 (pipeline de evaluación de retrieval)

Se ejecutan en este orden — cada uno alimenta al siguiente:

```bash
python scripts/explore_coverage.py [--sample N] [--dias N]
# Mide qué % de campos clave ya vienen estructurados desde la API de BDNS.
# Escribe data/raw/bdns_cv_sample.jsonl (gitignored) y SOBRESCRIBE docs/f1-coverage-report.md.

python scripts/build_gold_candidates.py [--sample N] [--dias N]
# Descarga una muestra real de convocatorias de la Comunitat Valenciana y aplica
# un borrador heurístico de relevancia (docs/gold-labeling-criteria.md).
# Escribe data/gold/candidates.csv con `relevance` vacía a propósito, a la
# espera de revisión humana.

python scripts/run_eval.py [--k 5,10,20]
# Corre el baseline BM25 sobre data/gold/candidates.csv y reporta
# precision@k / recall@k / nDCG@k / MRR. Usa `relevance` si ya está
# revisada a mano; si no, cae a `heuristic_relevance` y lo avisa en la salida.
```

Todos los scripts hacen `time.sleep(0.15)` entre llamadas a la API de BDNS
(pública, sin key) para no abusar de un servicio gratuito de terceros.

## Configuración

Variables de entorno (ver [`.env.example`](.env.example) — cópialo a `.env`, que está gitignored):

| Variable | Usada por | Notas |
|---|---|---|
| `BDNS_BASE_URL` | `ingestion/bdns.py` | API pública, no requiere key (verificado 2026-08-11) |
| `BDNS_VPD` | `ingestion/bdns.py` | Identificador de vpd, por defecto `GE` |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY`, `DATABASE_URL` | — | Se rellenan en F1/F4, aún no usadas por el código actual |
| `LLM_PROVIDER`, `LLM_MODEL`, `LLM_MONTHLY_BUDGET_EUR`, `ANTHROPIC_API_KEY` | extracción estructurada (F2) | Presupuesto mensual duro en EUR para cortar llamadas; extracción aún no implementada |
| `EMAIL_PROVIDER`, `RESEND_API_KEY`, `EMAIL_FROM` | digest semanal (F4/F5) | Aún no implementado |
| `N8N_WEBHOOK_URL` | orquestación (F3) | Aún no implementado |

Solo `BDNS_BASE_URL`/`BDNS_VPD` (con sus valores por defecto) son necesarias
para correr el código Python actual (`src/trackeraid/ingestion`,
`src/trackeraid/retrieval`, los tests, y los scripts de F1). El resto son
placeholders para fases futuras — `config.py` solo lee de `.env` las que ya
usa el código (`bdns_base_url`, `bdns_vpd`, `database_url`,
`llm_monthly_budget_eur`); las demás variables del `.env.example` documentan
lo que hará falta más adelante, pero todavía no las lee ningún módulo.

## Roadmap

| Fase | Contenido | Estado |
|---|---|---|
| F0 | Fuentes verificadas (BDNS en vivo, ver ADR-0002) | ✅ |
| F1 | Cobertura de campos medida, criterio de etiquetado escrito, gold set y harness de eval en marcha | 🔜 |
| F2 | Extracción estructurada + caché | ⬜ |
| F3 | n8n + FastAPI en producción, email verificado (SPF/DKIM/DMARC) | ⬜ |
| F4 | App pública en Lovable + consentimiento RGPD | ⬜ |
| F5 | Lanzamiento con usuarios reales | ⬜ |
| F6 | Reranker entrenado con feedback real, A/B | ⬜ |
| F7 | Página de métricas pública + vídeo demo | ⬜ |

## Privacidad

`TrackerAID` es un producto con usuarios reales desde su diseño: doble opt-in,
texto de consentimiento versionado (`consents.texto_version`), baja en un
clic y borrado de datos bajo petición. Detalle en `sql/001_init_schema.sql`.

## Limitaciones actuales

- El contrato de la API de BDNS no está documentado oficialmente por el
  proveedor; el cliente (`src/trackeraid/ingestion/bdns.py`) está confirmado
  por prueba directa, no por spec. Si BDNS cambia el contrato, el primer
  síntoma será que `pytest -m integration` empiece a fallar.
- El gold set (`data/gold/candidates.csv`) tiene 450 candidatas con relevancia
  heurística provisional; la columna `relevance` (revisión humana) sigue
  vacía, así que no hay todavía una tabla de ablación real — solo la
  confirmación de que el mecanismo de eval funciona de punta a punta.
- `src/trackeraid/extraction/` es un placeholder: la extracción estructurada
  con LLM (F2) no está implementada.
- Solo BDNS como fuente (decisión explícita, ver ADR-0002) — sin PLACSP ni
  datos abiertos de la GVA en el MVP.

## Licencia

[MIT](LICENSE) — Copyright (c) 2026 Sergio Peigneux d'Egmont.

## Autor

[Sergio Peigneux d'Egmont](https://github.com/serpeigd) — Data Scientist → ML/AI Agent Engineer.
