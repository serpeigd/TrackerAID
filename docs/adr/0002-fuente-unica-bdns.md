# 0002. Usar BDNS como única fuente de datos para el MVP

## Estado
Aceptado — 2026-08-11

## Contexto
El diseño inicial contemplaba 4 fuentes: BDNS/SNPSAP, BOE datos abiertos,
Plataforma de Contratación del Sector Público (PLACSP) y el portal de
datos abiertos de la GVA. Se verificó cada una antes de escribir código
de ingesta (ver `tests/test_bdns.py::test_ultimas_contra_la_api_real`
para la prueba en vivo contra BDNS).

Hallazgos:
- **BDNS/SNPSAP** (`infosubvenciones.es/bdnstrans/api`): API REST pública,
  sin API key, JSON, confirmada en vivo el 2026-08-11. Por Real Decreto
  130/2019 es el registro legal centralizado de subvenciones de todas las
  administraciones (estatal desde 2014, resto desde 2016). Incluye catálogo
  de regiones NUTS con los 3 códigos de la Comunitat Valenciana.
- **BOE datos abiertos**: API oficial gratuita, pero cubre legislación y
  sumarios generales, no convocatorias estructuradas — ese caso de uso ya
  lo resuelve mejor BDNS.
- **PLACSP**: cubre *licitaciones* (contratos que se licitan y compiten),
  un dominio distinto de *subvenciones* (ayudas que se conceden). No es
  redundante, pero tampoco es necesario para el caso de uso "ayudas para
  mi negocio".
- **GVA dadesobertes**: expone subvenciones ya *concedidas* (histórico),
  útil para enriquecer perfiles o validar cobertura, pero no para el radar
  de convocatorias *abiertas*, que es el producto.

## Decisión
El MVP (F0–F6) usa BDNS como única fuente de ingesta. PLACSP y GVA quedan
como extensión de alcance explícitamente fuera del MVP, no como deuda
técnica.

## Consecuencias
- Menos superficie de mantenimiento (un solo cliente, un solo formato).
- Cobertura completa de convocatorias de subvenciones en España por
  mandato legal, no una muestra parcial.
- Si en el futuro se añade PLACSP, el proyecto pasaría de "radar de
  subvenciones" a "radar de oportunidades públicas", lo cual es una
  decisión de producto a tomar aparte, no un fallback improvisado.
