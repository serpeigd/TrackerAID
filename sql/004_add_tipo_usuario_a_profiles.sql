-- F4: segundo perfil de usuario (particulares/asociaciones), y base para
-- filtrar por a quién van dirigidas las convocatorias.
--
-- Hasta ahora ni el dashboard de Lovable ni buscar_convocatorias (Python)
-- filtraban por doc_fields.beneficiarios -- un autónomo real podía ver
-- convocatorias para "personas jurídicas que no desarrollan actividad
-- económica" (asociaciones/clubes) que no puede solicitar. Con datos
-- reales: de las convocatorias de sanitario/social, solo el 6% son para
-- negocio; el resto son para particulares/asociaciones.
--
-- 'negocio' es el valor por defecto -- es el público objetivo actual del
-- proyecto, y mantiene el comportamiento de todos los perfiles ya
-- existentes sin que nadie tenga que volver a rellenar el onboarding.

ALTER TABLE profiles ADD COLUMN IF NOT EXISTS tipo_usuario text NOT NULL DEFAULT 'negocio'
  CHECK (tipo_usuario IN ('negocio', 'particular'));
