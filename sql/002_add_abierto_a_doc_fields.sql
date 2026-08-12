-- F3: falta abierto en doc_fields — es el filtro real que decide si una
-- convocatoria entra en el digest semanal. Ver docs/f1-coverage-report.md:
-- solo ~4.5% de lo publicado sigue abierto, así que este campo es
-- imprescindible para el pipeline, no un "nice to have".
alter table doc_fields add column if not exists abierto boolean;

create index if not exists idx_doc_fields_abierto on doc_fields(abierto) where abierto = true;
