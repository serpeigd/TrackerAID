# 0004. Extracción de plazo: regex + LLM local, sin API de pago

## Estado
Aceptado — 2026-08-12

## Contexto
F1 (`docs/f1-coverage-report.md`) midió que el 51% de las convocatorias trae
`fecha_fin_solicitud` ya estructurado por la API; el resto se asumía que
necesitaría descargar y parsear el PDF de bases reguladoras + LLM de pago
(Claude Haiku) para completarse, con un coste estimado de céntimos al mes.

Sergio pidió explícitamente que el proyecto fuera gratis. Antes de decidir
si eso era viable o si tocaba ceder en ese punto, se investigó:

1. **La API de BDNS expone `textInicio`/`textFin`**, un campo de texto libre
   con el plazo en prosa cuando no hay fecha estructurada — no documentado
   en ningún sitio, encontrado por inspección directa de la respuesta real.
2. Se implementó un extractor por reglas (`extraction/deadline.py`) sobre
   ese campo: fechas absolutas en texto, "sin plazo de solicitud", plazos
   relativos con fecha de referencia.
3. Para lo que el regex no resuelve, se probó un LLM local vía Ollama
   (`llama3.1:8b`, ya en uso en otro proyecto del autor) en vez de una API
   de pago.

Medido en vivo sobre 150 convocatorias reales
(`docs/f2-deadline-coverage.md`):

| Nivel | Cobertura |
|---|---|
| Campo estructurado | 53.3% |
| + regex sobre `texto_fin` | +16.0% |
| + LLM local (Ollama) | +22.0% |
| **Total resuelto, coste cero** | **91.3%** |
| Sin resolver (requeriría PDF) | 8.7% |

## Decisión
El pipeline de extracción de plazo (F2) usa **regex primero, LLM local
(Ollama) como fallback**, sin depender de ninguna API de pago. La
`ANTHROPIC_API_KEY` de `.env.example` queda como opcional, documentada mejor
como referencia de "cuánto costaría hacerlo con Claude" que como requisito.

El 8.7% restante (requeriría descargar y parsear el PDF de bases
reguladoras) se deja **explícitamente fuera de alcance del MVP**: no hay
suficiente valor marginal para la complejidad de añadir descarga de PDFs,
extracción de texto y otro nivel de fallback, cuando regex+LLM local ya
cubren el 91.3% sin coste.

## Consecuencias
- El proyecto es genuinamente gratis de ejecutar, cumpliendo el requisito.
- Requiere que la máquina que corre el pipeline semanal (F3) tenga Ollama
  instalado y el modelo descargado — una dependencia operativa a documentar
  en el README de despliegue, no un problema de coste.
- La primera llamada a Ollama sin el modelo "caliente" en memoria puede
  tardar >30s — el pipeline de producción debe precalentar el modelo antes
  del lote semanal (`extraction.llm_ollama.calentar_modelo()`), no en cada
  convocatoria.
- Si en el futuro se quisiera cerrar ese 8.7% restante, la vía más barata
  seguiría siendo regex sobre el texto del PDF (mismo enfoque, un nivel más
  abajo), no saltar directamente a un LLM de pago.
