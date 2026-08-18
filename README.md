# TrackerAID

[![CI](https://github.com/serpeigd/TrackerAID/actions/workflows/ci.yml/badge.svg)](https://github.com/serpeigd/TrackerAID/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

> Radar semántico de subvenciones públicas para autónomos y pymes de la Comunitat Valenciana.

**Estado: en construcción (F0, F1 y F2 completadas; F3 en marcha).** Este README se actualiza fase a fase — ver [roadmap](#roadmap) y [ADRs](docs/adr/).

📊 [Cobertura real de campos en BDNS](docs/f1-coverage-report.md) · 📋 [Criterio de etiquetado del gold set](docs/gold-labeling-criteria.md) · 📈 [Resultados de eval (BM25)](docs/f1-eval-results.md) · 🗓️ [Cobertura de extracción de plazo](docs/f2-deadline-coverage.md) · 🔧 [Montar el workflow n8n (F3)](docs/n8n-setup.md)

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

Decisiones documentadas en detalle: [ADR-0001](docs/adr/0001-record-architecture-decisions.md) · [ADR-0002 (fuente única BDNS)](docs/adr/0002-fuente-unica-bdns.md) · [ADR-0003 (lógica en Python)](docs/adr/0003-logica-en-python-no-en-n8n.md) · [ADR-0004 (extracción gratis: regex + LLM local)](docs/adr/0004-extraccion-gratis-regex-llm-local.md).

### Estructura del repo

```
src/trackeraid/
  config.py             Configuración centralizada (lee .env / os.environ)
  api.py                 FastAPI: /health, /pipeline/ingest (202, en background), /pipeline/status
  pipeline.py             Orquesta la ingesta semanal: BDNS -> extracción de plazo -> Supabase
  storage.py               Persistencia en Supabase
  ingestion/bdns.py         Cliente de solo lectura sobre la API pública de BDNS
  retrieval/                 Baseline BM25 (bm25.py) + métricas de IR (metrics.py)
  extraction/                 Plazo: deadline.py (regex, 3 niveles) + llm_ollama.py (LLM local)

scripts/
  explore_coverage.py          F1 — mide cobertura de campos estructurados en BDNS
  build_gold_candidates.py      F1 — genera la hoja de candidatas para el gold set
  run_eval.py                    F1 — baseline BM25 sobre el gold set, reporta métricas
  measure_deadline_coverage.py    F2 — mide qué % del plazo se resuelve sin coste
  start-pipeline-stack.ps1        F3 — levanta Docker + n8n + Ollama + la API
  stop-pipeline-stack.ps1          F3 — los apaga en orden
  run-pipeline-once.ps1            F3 — arranca el stack, lanza la ingesta, espera y apaga, en un comando
  register-scheduled-tasks.ps1      F3 — registra el arranque/apagado semanal en el Programador de
                                        tareas de Windows (preparado, sin activar a propósito)

sql/                    Esquema Postgres/pgvector (001) + migraciones (002)
data/gold/              Gold set curado a mano — SÍ se versiona (ver .gitignore)
data/raw/               Muestras crudas de BDNS — NO se versiona, regenerable
docs/adr/               Decisiones de arquitectura (formato Nygard)
n8n/docker-compose.yml   n8n autoalojado para el cron semanal
tests/                  pytest — unitarios (mockeados con respx) + marcados `integration`
```

## Evaluación

El repo trata la calidad de retrieval como algo que se mide, no se asume:

- Gold set etiquetado a mano (`data/gold/`) con criterio de etiquetado documentado.
- Tabla de ablación BM25 / embeddings / híbrido / +reranker sobre recall@20, nDCG@10, precision@5, latencia y coste.
- CI que falla si nDCG@10 cae por debajo de un umbral respecto al baseline.
- Página pública de métricas que se regenera sola cada semana (F7).

Baseline BM25 implementado, testeado y con **[resultados reales sobre gold set etiquetado a mano](docs/f1-eval-results.md)** (443 de 450 pares confirmados, no heurísticos): MRR=1.00, precision@20=0.95, recall@20=0.153 — este último es el número a mejorar con embeddings, siguiente paso.

## Extracción de plazo (F2)

El campo más importante de una convocatoria — hasta cuándo se puede pedir — viene
estructurado en BDNS solo la mitad de las veces. La cascada de tres niveles de
`src/trackeraid/extraction/` lo resuelve **sin coste**: campo estructurado primero,
luego regex sobre el texto (fecha absoluta, plazo relativo, "sin plazo"), y solo lo
que sobrevive a ambos pasa por un LLM **local** vía Ollama (ver
[ADR-0004](docs/adr/0004-extraccion-gratis-regex-llm-local.md)).

Medido sobre 150 convocatorias reales: **137/150 resueltas (91,3%)**, ninguna con
API de pago — desglose por método en
[`docs/f2-deadline-coverage.md`](docs/f2-deadline-coverage.md), reproducible con
`python scripts/measure_deadline_coverage.py`.

## Desarrollo

```bash
pip install -e ".[dev,eval]"   # dev: pytest/ruff/respx · eval: rank-bm25/numpy/scikit-learn
pytest                         # tests unitarios (sin red — `integration` está excluido por defecto)
pytest -m integration          # smoke test contra la API real de BDNS
ruff check src tests scripts
```

### Scripts de evaluación y medición

Los de F1 se ejecutan en orden, cada uno alimenta al siguiente:

```bash
python scripts/explore_coverage.py [--sample N] [--dias N]
# F1 — qué % de campos clave llegan ya estructurados desde BDNS.
# Escribe data/raw/bdns_cv_sample.jsonl (gitignored) y SOBRESCRIBE docs/f1-coverage-report.md.

python scripts/build_gold_candidates.py [--sample N] [--dias N]
# F1 — descarga una muestra real de convocatorias de la CV y aplica un borrador
# heurístico de relevancia (docs/gold-labeling-criteria.md), dejando `relevance`
# vacía a propósito, a la espera de revisión humana.

python scripts/run_eval.py [--k 5,10,20]
# F1 — baseline BM25 sobre data/gold/candidates.csv: precision@k / recall@k / nDCG@k / MRR.

python scripts/measure_deadline_coverage.py
# F2 — mide la cascada de extracción de plazo y regenera docs/f2-deadline-coverage.md.
```

Todos hacen `time.sleep(0.15)` entre llamadas a la API de BDNS (pública, sin key)
para no abusar de un servicio gratuito de terceros.

### El stack de F3 en local

```powershell
.\scripts\start-pipeline-stack.ps1   # Docker + n8n + Ollama + la API, en orden
.\scripts\stop-pipeline-stack.ps1    # los apaga
# o los tres pasos (arrancar, ingerir, apagar) en un solo comando:
.\scripts\run-pipeline-once.ps1
```

Guía completa para montar el workflow de n8n (los 5 nodos, el aviso por
Gmail, cómo probarlo sin esperar al lunes): [`docs/n8n-setup.md`](docs/n8n-setup.md).

Con el stack levantado, la API expone:

| Endpoint | Qué hace |
|---|---|
| `GET /health` | Comprobación de vida |
| `POST /pipeline/ingest` | Lanza la ingesta y devuelve `202` de inmediato — corre en background, porque la llamada síncrona cortaba la conexión de n8n |
| `GET /pipeline/status` | Estado de la última ingesta |

n8n (`http://localhost:5678`) solo dispara el cron y llama a `/pipeline/ingest`:
nunca contiene lógica de negocio (ver [ADR-0003](docs/adr/0003-logica-en-python-no-en-n8n.md)).

## Configuración

Variables de entorno (ver [`.env.example`](.env.example) — cópialo a `.env`, que está gitignored):

| Variable | Usada por | Notas |
|---|---|---|
| `BDNS_BASE_URL`, `BDNS_VPD` | `ingestion/bdns.py` | API pública, no requiere key (verificado 2026-08-11) |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | `storage.py` | Persistencia de la ingesta |
| `SUPABASE_ANON_KEY`, `DATABASE_URL` | — | Reservadas para la app de F4, aún sin uso en el código |
| `OLLAMA_URL`, `OLLAMA_MODEL` | — | Documentan el valor por defecto del módulo (`localhost:11434`, `llama3.1:8b`) — `extraction/llm_ollama.py` usa constantes propias y no lee estas variables todavía, así que cambiarlas en `.env` no tiene efecto (ver Limitaciones) |
| `LLM_PROVIDER`, `LLM_MODEL`, `LLM_MONTHLY_BUDGET_EUR`, `ANTHROPIC_API_KEY` | opcional | Solo para comparar calidad/coste contra un LLM de pago; déjalas vacías |
| `EMAIL_PROVIDER`, `RESEND_API_KEY`, `EMAIL_FROM` | digest semanal (F4/F5) | Aún no implementado |
| `N8N_WEBHOOK_URL` | orquestación (F3) | Aún no implementado |

Solo `BDNS_BASE_URL`/`BDNS_VPD` (con sus valores por defecto) hacen falta para
correr los tests y los scripts de evaluación. `config.py` es el único sitio que
lee entorno; las variables marcadas "aún no implementado" documentan lo que hará
falta más adelante, pero todavía no las lee ningún módulo.

## Roadmap

| Fase | Contenido | Estado |
|---|---|---|
| F0 | Fuentes verificadas (BDNS en vivo, ver ADR-0002) | ✅ |
| F1 | Cobertura de campos medida, gold set completo (443/450), baseline BM25 evaluado | ✅ |
| F2 | Extracción de plazo (regex + LLM local, sin coste, 91,3% resuelto) | ✅ |
| F3 | Pipeline de ingesta a Supabase, API FastAPI y scaffold de n8n ✅ · email verificado (SPF/DKIM/DMARC) pendiente | 🚧 |
| F4 | App pública en Lovable + consentimiento RGPD | ⬜ |
| F5 | Lanzamiento con usuarios reales | ⬜ |
| F6 | Reranker entrenado con feedback real, A/B | ⬜ |
| F7 | Página de métricas pública + vídeo demo | ⬜ |

## Privacidad

`TrackerAID` es un producto con usuarios reales desde su diseño: doble opt-in,
texto de consentimiento versionado (`consents.texto_version`), baja en un
clic y borrado de datos bajo petición. Detalle en `sql/001_init_schema.sql`.

## Limitaciones actuales

- El contrato de la API de BDNS no está documentado oficialmente por el proveedor;
  el cliente (`src/trackeraid/ingestion/bdns.py`) está confirmado por prueba
  directa, no por spec. Si BDNS cambia el contrato, el primer síntoma será que
  `pytest -m integration` empiece a fallar.
- **`recall@20 = 0,153`** es el número flojo del baseline BM25: encuentra bien
  (precision@20 = 0,95, MRR = 1,00) pero se deja fuera la mayoría de lo relevante.
  Mejorarlo con embeddings es el siguiente paso real, no un detalle.
- El 8,7% de convocatorias cuyo plazo no se resuelve queda **explícitamente sin
  resolver**, no adivinado — la fecha vive en el PDF de las bases, que este
  pipeline no abre.
- La extracción por LLM depende de un **Ollama local levantado**: sin él, ese
  tercer nivel de la cascada se cae y solo quedan campo estructurado + regex.
- Solo BDNS como fuente (decisión explícita, ver ADR-0002) — sin PLACSP ni datos
  abiertos de la GVA en el MVP.
- Los scripts del stack de F3 son **PowerShell** (`.ps1`), atados al entorno de
  desarrollo actual; en Linux/macOS hay que levantar los servicios a mano.
- `POST /pipeline/ingest` no tiene **ninguna autenticación** todavía —
  aceptable mientras solo corre en local, pero hay que añadir una API key
  simple antes de exponerlo fuera de la máquina (detalle en
  [`docs/n8n-setup.md`](docs/n8n-setup.md)).
- `OLLAMA_URL`/`OLLAMA_MODEL` no tienen efecto hoy: `extraction/llm_ollama.py`
  usa constantes propias en vez de leer `config.settings` — gap de código real,
  no solo de docs (ver Configuración arriba).
- La ingesta (`pipeline.py`, F3) todavía no filtra por `abierto`: guarda el
  campo pero no descarta convocatorias ya cerradas, aunque
  [`docs/gold-labeling-criteria.md`](docs/gold-labeling-criteria.md) documenta
  ese filtro como el paso que debe aplicarse antes de mandar el digest.

## Licencia y aviso legal

Copyright © 2026 Sergio Peigneux d'Egmont ([@serpeigd](https://github.com/serpeigd)).

El código de este repositorio se publica bajo [licencia MIT](LICENSE): se puede
reutilizar, modificar y redistribuir, incluso comercialmente, siempre que se
conserven el aviso de copyright y el texto de la licencia. Se ofrece **tal cual,
sin garantía de ningún tipo**; el descargo completo está en el archivo LICENSE.

Esa licencia cubre el código y la documentación propios, y **no** se extiende a:

- **Los datos de la BDNS.** Las convocatorias proceden de la
  [Base de Datos Nacional de Subvenciones](https://www.infosubvenciones.es/),
  un registro público del Estado, y se consultan a través de su API pública en
  modo solo lectura. Se rigen por sus propias condiciones de reutilización de
  información del sector público, no por la licencia de este repositorio.
- **Modelos y servicios de terceros**: Ollama y los pesos que sirve, Supabase,
  n8n y Docker mantienen cada uno sus propias licencias y términos de uso.
- **Contenido de una convocatoria concreta** (textos, importes, bases
  reguladoras), que pertenece al organismo que la publica.

**Nada de lo que produce TrackerAID es asesoramiento legal, fiscal ni
administrativo**: es un sistema de descubrimiento y ordenación por relevancia.
La única fuente válida para decidir si se puede optar a una ayuda, y hasta
cuándo, son las bases reguladoras oficiales de esa convocatoria — el plazo que
extrae este pipeline es una estimación automática, y un 8,7% de los casos ni
siquiera se resuelve (ver [Limitaciones](#limitaciones-actuales)).

Sobre datos personales: el proyecto está pensado para tener usuarios reales
(ver [Privacidad](#privacidad)), lo que implica responsabilidades propias de
RGPD para quien lo despliegue. Este aviso no es una opinión jurídica.

## Autor

[Sergio Peigneux d'Egmont](https://github.com/serpeigd) — Data Scientist → ML/AI Agent Engineer.
