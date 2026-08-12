# Cobertura de plazo (fecha_fin_solicitud) — pipeline de tres niveles

Medido el 2026-08-12 sobre 150 convocatorias reales (CV, últimos 90 días). Reproducible con `python scripts/measure_deadline_coverage.py`.

| Método | Convocatorias | % |
|---|---|---|
| `estructurado` | 80 | 53.3% |
| `regex_fecha_absoluta` | 17 | 11.3% |
| `regex_sin_plazo` | 1 | 0.7% |
| `regex_relativo` | 6 | 4.0% |
| `llm_ollama` | 33 | 22.0% |
| `no_resuelto` | 13 | 8.7% |

**Resuelto en total (sin PDF, sin coste): 137/150 (91.3%)**

Intentos de LLM: 41 | resueltos por LLM: 33

## Lectura

Punto de partida (F1, `docs/f1-coverage-report.md`): 51% de las convocatorias
traían `fecha_fin_solicitud` ya estructurado. El resto se asumía que
necesitaría descargar y parsear el PDF de bases — el hallazgo real de F2 es
que la mayor parte no hacía falta: la propia API expone `textFin`, un campo
de texto libre (no documentado en ningún sitio, encontrado por inspección
directa) que ya trae el plazo casi siempre que falta el campo estructurado.

- **Regex sobre `texto_fin` añade 16 puntos gratis** (fecha en texto tipo
  "HASTA EL 31 DE OCTUBRE DE 2026", "Sin plazo de solicitud", o "N días
  hábiles desde...").
- **El LLM local (Ollama, `llama3.1:8b`) resuelve 33 de 41 intentos** sobre
  lo que el regex no pudo — frases narrativas o ambiguas ("último día
  laborable de noviembre", "mientras existan fondos disponibles"). Sin
  coste: corre en el propio PC, sin `ANTHROPIC_API_KEY`.
- **Precalentar el modelo antes del lote es obligatorio en la práctica**:
  la primera llamada a Ollama sin el modelo cargado en memoria tardó >30s
  y disparó un timeout en la primera corrida de este script — con
  precalentamiento (`calentar_modelo()`), el resto del lote fue rápido.
- Queda un **8.7% genuinamente sin resolver** (ni campo estructurado, ni
  `texto_fin`, ni nada que el LLM pueda leer) — ahí sí haría falta bajar al
  PDF de bases reguladoras, y solo para ese resto. No implementado todavía:
  no compensa el coste de ingeniería para un 8.7% cuando regex+LLM local ya
  cubren el 91.3% gratis.
