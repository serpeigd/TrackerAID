# TrackerAID

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

## Evaluación

El repo trata la calidad de retrieval como algo que se mide, no se asume:

- Gold set etiquetado a mano (`data/gold/`) con criterio de etiquetado documentado.
- Tabla de ablación BM25 / embeddings / híbrido / +reranker sobre recall@20, nDCG@10, precision@5, latencia y coste.
- CI que falla si nDCG@10 cae por debajo de un umbral respecto al baseline.
- Página pública de métricas que se regenera sola cada semana (F7).

Baseline BM25 implementado, testeado y con **[resultados reales sobre gold set etiquetado a mano](docs/f1-eval-results.md)** (443 de 450 pares confirmados, no heurísticos): MRR=1.00, precision@20=0.95, recall@20=0.153 — este último es el número a mejorar con embeddings, siguiente paso.

## Desarrollo

```bash
pip install -e ".[dev]"
pytest                    # tests unitarios (sin red)
pytest -m integration     # smoke test contra la API real de BDNS
ruff check src tests
```

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

## Autor

[Sergio Peigneux d'Egmont](https://github.com/serpeigd) — Data Scientist → ML/AI Agent Engineer.
