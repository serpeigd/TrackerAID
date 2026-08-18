# Criterio de etiquetado del gold set

Se escribe **antes** de etiquetar nada, sobre datos reales ya observados
(ver [f1-coverage-report.md](f1-coverage-report.md)). El perfil objetivo
por defecto: *autónomo o pyme con sede en la Comunitat Valenciana*, sin
sector fijado (el gold set cubrirá varios sectores para no sesgar el
retrieval a uno solo).

## Escala

**Importante — corregido tras la primera pasada de muestreo real:** el
gold set etiqueta **relevancia temática** (¿es del tipo de ayuda que le
interesa a este perfil, sin importar si hoy está abierta?), no
disponibilidad en tiempo real. Se probó exigir `abierto=true` para
relevancia 2 y, sobre 450 candidatas encontradas con búsqueda dirigida a
términos empresariales (pymes, autónomos, digitalización, IVACE...), solo
**4 seguían abiertas en el momento de la prueba** frente a 90 que sí eran
temáticamente relevantes. Exigir apertura habría dejado el gold set casi
vacío de positivos y habría medido "¿tengo suerte con el timing?" en vez
de "¿el retrieval encuentra lo relevante?". `abierto` se queda como
columna informativa (`data/gold/candidates.csv`) y es el filtro pensado
para aplicarse antes de mandar el digest — pero es un filtro posterior al
retrieval, no parte de la etiqueta de relevancia. **La ingesta actual
(`pipeline.py`, F3) todavía no lo aplica**: guarda `abierto` en
`doc_fields` pero no descarta convocatorias cerradas, así que hoy se
ingiere también lo ya cerrado.

**2 — Relevante.** La convocatoria concede ayuda económica directa a
autónomos o pymes (inversión, digitalización, contratación, I+D+i,
internacionalización, eficiencia energética, comercio, hostelería,
agricultura profesional...), el perfil encaja en el tipo de beneficiario
exigido, y el ámbito geográfico incluye la Comunitat Valenciana.

**1 — Parcialmente relevante.** Cumple el criterio de "2" salvo uno de
estos matices:
- Beneficiario definido de forma amplia ("cualquier autónomo o pyme",
  sin restringir sector) — relevante pero menos específico.
- Ámbito nacional/estatal que incluye la CV pero no está pensado para
  ella en particular.

**0 — No relevante.** Cualquiera de estos casos, todos observados ya en
la muestra real:
- Beneficiario es una asociación, ayuntamiento, club deportivo, parroquia,
  particular/familia o centro educativo — no una empresa/autónomo.
- Es un convenio nominativo entre administraciones (`tipoConvocatoria`
  distinto de concurrencia competitiva) sin proceso de solicitud abierto
  a terceros.
- Ámbito fuera de la Comunitat Valenciana.
- Beca o ayuda a estudiantes/investigadores individuales sin vínculo con
  actividad empresarial.
- Premio, certamen o concurso (aunque liste "pyme" como categoría de
  participante posible en el catálogo de beneficiarios) — no es ayuda
  económica a la actividad empresarial, es un reconocimiento con premio.
  Encontrado en la primera pasada de muestreo: varios "Certamen
  Gastronómico"/"Premios Ciudad de..." etiquetan PYME como beneficiario
  sin serlo en la práctica.

## Proceso

1. Muestreo estratificado desde `data/raw/bdns_cv_sample.jsonl` (y
   ampliaciones posteriores): cubrir varios `nivel1` (ESTATAL/AUTONOMICA/
   LOCAL) y varios `sectores`, no solo los más frecuentes.
2. Un único anotador (Sergio) por ahora — se anota en `annotator` para
   poder auditar consistencia si se suman más etiquetadores.
3. Casos dudosos: se etiquetan como 1, no se descartan. El gold set debe
   reflejar la dificultad real del problema, no solo los casos fáciles.
4. Meta: 150–300 pares (profile_id, doc_id, relevance) antes de construir
   el harness de eval (`src/trackeraid/retrieval/`).

## Ejemplos reales ya vistos (sin etiquetar aún, ilustrativos)

| Descripción real | Relevancia esperada | Por qué |
|---|---|---|
| "RESOLUCIÓN... CONVOCATORIA DE AYUDAS A EMPRESAS Y CENTROS DE INVESTIGACIÓN DE TRANSFERENCIA DE CONOCIMIENTO Y TECNOLOGÍA..." | 2 (si ámbito CV) | Ayuda directa a empresas, concurrencia competitiva |
| "Subvención nominativa 2026 Cáritas Parroquial..." | 0 | Beneficiario no empresarial, convenio nominativo |
| "Convenio Asociación Moros y Cristianos con el Ayuntamiento de Quart de Poblet" | 0 | Asociación, no empresa |
| "SARC_Festivales, muestras y certámenes 2026" (Diputación) | 1 | Puede incluir empresas culturales/eventos, verificar bases |
