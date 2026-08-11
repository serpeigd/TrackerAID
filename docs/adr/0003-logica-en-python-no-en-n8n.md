# 0003. La lógica de negocio vive en Python; n8n solo orquesta

## Estado
Aceptado — 2026-08-11

## Contexto
El proyecto usa n8n (y puntualmente Make) como parte de los objetivos de
aprendizaje declarados. El riesgo es que, por comodidad, la lógica de
retrieval, extracción y scoring acabe escrita dentro de nodos de n8n
(Function nodes, prompts sueltos), lo que la hace imposible de testear,
versionar con significado o mostrar como código propio en el portfolio.

## Decisión
- Todo el retrieval, extracción, ranking y evaluación vive en el paquete
  `src/trackeraid/`, con tests y CI.
- n8n solo dispara el pipeline (cron semanal), llama a endpoints de una
  API FastAPI, y mueve el resultado (envío de email, notificación a
  Telegram vía Make). Ningún nodo de n8n contiene lógica de negocio.
- Make se usa para un único escenario secundario de aprendizaje (ver
  README), no como pieza del backbone.

## Consecuencias
- Migrar de n8n a otra herramienta de orquestación en el futuro no toca
  la lógica del producto.
- El repo sigue siendo evaluable como proyecto de ingeniería de datos/ML,
  no como una demo de no-code.
- Coste: hay que exponer la lógica como API (FastAPI) en vez de dejarla
  suelta, lo cual añade una capa pero es trabajo que de todos modos hace
  falta para el hosting de F3.
