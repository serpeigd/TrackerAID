# F3 — Montar el workflow semanal en n8n

n8n solo dispara el cron y llama a la API — toda la lógica vive en Python
(`trackeraid.pipeline`, expuesto por `trackeraid.api`). Ver
[ADR-0003](adr/0003-logica-en-python-no-en-n8n.md).

## 1. Arrancar n8n

```bash
cd n8n
docker compose up -d
```

Abre `http://localhost:5678` y crea tu usuario local (queda en el volumen
Docker `n8n_data`, no en el repo).

## 2. Arrancar la API de TrackerAID

En otra terminal, desde la raíz del repo:

```bash
uvicorn trackeraid.api:app --host 0.0.0.0 --port 8000
```

`--host 0.0.0.0` es importante: n8n corre dentro de un contenedor Docker y
necesita alcanzar la API que corre en tu máquina (el host), no solo
`localhost` dentro del propio contenedor.

## 3. Crear el workflow en n8n

1. **New workflow** → nodo **Schedule Trigger**: Cron, `0 6 * * 1` (lunes
   06:00, o el horario que prefieras). Zona horaria ya viene fijada a
   `Europe/Madrid` en el `docker-compose.yml`.
2. Nodo **HTTP Request**:
   - Method: `POST`
   - URL: `http://host.docker.internal:8000/pipeline/ingest`
     (`host.docker.internal` es como un contenedor Docker Desktop en
     Windows/Mac alcanza el host — no uses `localhost`, apunta al
     contenedor mismo, no a tu máquina)
   - Body (JSON): `{"dias": 7, "con_llm": true, "max_convocatorias": 300}`
   - **Timeout: súbelo a al menos 300000 ms (5 min)** — el pipeline
     puede tardar varios minutos en lotes grandes (rate-limit deliberado
     contra BDNS + posible LLM local por convocatoria sin resolver).
3. (Opcional, recomendado) Nodo **IF** tras el HTTP Request: si
   `errores` no está vacío en la respuesta, ramifica a una notificación
   (Telegram/email) — así te enteras si BDNS o Ollama fallaron sin tener
   que mirar logs.
4. Activa el workflow (toggle arriba a la derecha).

## 4. Probar sin esperar al lunes

Botón **Execute workflow** en n8n, o directamente:

```bash
curl -X POST http://localhost:8000/pipeline/ingest \
  -H "Content-Type: application/json" \
  -d '{"dias": 7, "con_llm": true, "max_convocatorias": 20}'
```

## Pendiente (no bloquea el MVP)

- **Máquina siempre encendida**: mientras el cron dependa de tu PC con
  Docker + Ollama corriendo, el pipeline solo se ejecuta si tu equipo está
  encendido a esa hora. Para producción real (F5) hará falta un host
  siempre activo — pospuesto a propósito, no es necesario para probar el
  pipeline de punta a punta ahora.
- **Autenticación del endpoint**: `/pipeline/ingest` no tiene ninguna
  protección todavía (cualquiera que alcance el puerto 8000 puede
  dispararlo). Aceptable mientras corre solo en local; añadir una API key
  simple antes de exponerlo fuera de tu máquina.
