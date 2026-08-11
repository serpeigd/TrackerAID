# Criterio de etiquetado del gold set

Se escribe **antes** de etiquetar nada, sobre datos reales ya observados
(ver [f1-coverage-report.md](f1-coverage-report.md)). El perfil objetivo
por defecto: *autónomo o pyme con sede en la Comunitat Valenciana*, sin
sector fijado (el gold set cubrirá varios sectores para no sesgar el
retrieval a uno solo).

## Escala

**2 — Relevante.** La convocatoria concede ayuda económica directa a
autónomos o pymes (inversión, digitalización, contratación, I+D+i,
internacionalización, eficiencia energética, comercio, hostelería,
agricultura profesional...), el perfil encaja en el tipo de beneficiario
exigido, el ámbito geográfico incluye la Comunitat Valenciana, y sigue
`abierto=true` en el momento de etiquetar.

**1 — Parcialmente relevante.** Cumple el criterio de "2" salvo uno de
estos matices:
- Beneficiario definido de forma amplia ("cualquier autónomo o pyme",
  sin restringir sector) — relevante pero menos específico.
- Ámbito nacional/estatal que incluye la CV pero no está pensado para
  ella en particular.
- Ya cerrada (`abierto=false`) pero de un organismo/línea que convoca
  todos los años — útil como señal de "vigila esta línea", no como
  oportunidad inmediata.

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
