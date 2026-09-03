-- F4: corrige el matching de ámbito geográfico del dashboard y añade el
-- número de trabajadores al perfil.
--
-- Bug real encontrado: doc_fields.ambito se guardaba como texto unido con
-- ", " (p.ej. "ES523 - Valencia / València"), y el dashboard comparaba por
-- IGUALDAD EXACTA contra profiles.ambito (p.ej. "Comunitat Valenciana").
-- Esas dos cadenas casi nunca coinciden -> la mayoría de coincidencias
-- reales no se mostraban. Se cambia ambito a array (mismo patrón que
-- cnae) para poder comparar por solape (&&).
--
-- También se añade nivel1 (ESTATAL/AUTONOMICA/LOCAL): sin esto no hay
-- forma de distinguir "aplica a toda España" (debería mostrarse siempre,
-- ambito puede venir vacío) de "no se pudo determinar la región".

ALTER TABLE doc_fields ADD COLUMN IF NOT EXISTS nivel1 text;

ALTER TABLE doc_fields ALTER COLUMN ambito TYPE text[] USING
  CASE WHEN ambito IS NULL OR ambito = '' THEN NULL ELSE string_to_array(ambito, ', ') END;

ALTER TABLE profiles ADD COLUMN IF NOT EXISTS num_empleados integer;
