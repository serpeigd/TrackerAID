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

**Importante — historial real:** la primera versión de este workflow hacía
un único `POST /pipeline/ingest` síncrono y esperaba varios minutos a la
respuesta. En la práctica, la conexión entre el contenedor de n8n y la API
del host se cortaba antes de que llegara la respuesta (aunque el pipeline
sí terminaba bien del lado del servidor — confirmado por los datos en
Supabase). Por eso `/pipeline/ingest` ahora responde al instante (202) y
lanza el trabajo en segundo plano; hay que consultar `/pipeline/status`
después para saber cómo fue. El workflow tiene 5 nodos, no 3:

1. **Schedule Trigger**: Cron, `0 6 * * 1` (lunes 06:00, o el horario que
   prefieras). Zona horaria ya fijada a `Europe/Madrid` en el
   `docker-compose.yml`.
2. **HTTP Request** ("Lanzar ingesta"):
   - Method: `POST`
   - URL: `http://host.docker.internal:8000/pipeline/ingest`
     (`host.docker.internal` es como un contenedor Docker Desktop en
     Windows/Mac alcanza el host — no uses `localhost`)
   - Body (JSON): `{"dias": 7, "con_llm": true, "max_convocatorias": 300}`
   - Responde en menos de un segundo (`{"iniciado": true}`) — no hace
     falta tocar el timeout por defecto aquí.
3. **Wait**: 10 minutos. Deja tiempo de sobra para que el pipeline
   termine en segundo plano antes de preguntar por el resultado (300
   convocatorias con LLM de fallback puede tardar varios minutos).
4. **HTTP Request** ("Consultar estado"):
   - Method: `GET`
   - URL: `http://host.docker.internal:8000/pipeline/status`
   - Devuelve `{"estado": "completado"|"error"|"en_curso", "resumen": {...con "errores": [...]}, ...}`
5. **If**: condición sobre `{{ $json.resumen.errores }}` (o `{{ $json.error }}`
   si `estado` es `"error"`) — **tipo de dato Array, no Object** — "is not
   empty". La salida **`true`** (sí hay errores) es la que va al nodo de
   aviso, no la `false`.
6. Nodo de aviso (Gmail u otro) colgado de la salida `true` del If — ver
   configuración abajo.
7. Activa el workflow (toggle arriba a la derecha).

### Configurar el aviso por Gmail (self-hosted, sin botón "Sign in with Google")

En n8n autoalojado no hay un cliente de Google preconfigurado como en n8n
Cloud — hay que crear el tuyo en Google Cloud Console:

1. [console.cloud.google.com](https://console.cloud.google.com) → crea o
   elige un proyecto.
2. **APIs & Services → Library** → busca "Gmail API" → **Enable**.
3. **APIs & Services → OAuth consent screen** → tipo *External* → rellena
   nombre de la app y tu email → en *Test users* añade tu propio email
   (mientras la app esté en modo "Testing", solo esos usuarios pueden
   autenticarse).
4. **APIs & Services → Credentials → Create Credentials → OAuth client ID**
   → tipo *Web application* → en **Authorized redirect URIs** pega
   exactamente la URL que te muestra n8n en el credential
   (`http://localhost:5678/rest/oauth2-credential/callback`).
5. Copia el **Client ID** y **Client Secret** generados y pégalos en los
   campos del credential de n8n. Guarda — ahora sí debería aparecer el
   botón para conectar la cuenta.
6. En el nodo **Send a message**: To = tu email, Subject y Message como
   en el ejemplo de más abajo.

### Plantilla del email de aviso

```
Subject: ⚠️ Error en el pipeline TrackerAID — {{ $now.format('dd/MM/yyyy HH:mm') }}

Message:
El pipeline de ingesta ha fallado en {{ $json.resumen.errores.length }} convocatoria(s):

{{ $json.resumen.errores.join('\n') }}

Resumen de la corrida:
- Procesadas: {{ $json.resumen.procesadas }}
- Guardadas: {{ $json.resumen.guardadas }}
- Con plazo resuelto: {{ $json.resumen.con_plazo_resuelto }}
- Resueltas vía LLM: {{ $json.resumen.metodo_llm_usado }}

---
Copia este email entero y pégaselo a Claude: "lee este error y corrígelo".
```

## 4. Probar sin esperar al lunes

Botón **Execute workflow** en n8n, o a mano en dos pasos:

```bash
curl -X POST http://localhost:8000/pipeline/ingest \
  -H "Content-Type: application/json" \
  -d '{"dias": 7, "con_llm": true, "max_convocatorias": 20}'
# -> {"iniciado": true, "mensaje": "..."} al instante

# espera unos segundos/minutos según el tamaño del lote, luego:
curl http://localhost:8000/pipeline/status
# -> {"estado": "completado", "resumen": {...}, ...}
```

## 5. Encender y apagar el stack solo cuando toca

Docker Desktop en reposo consume ~1-2 GB de RAM (la VM de WSL2 de debajo)
aunque no haya nada corriendo — no compensa dejarlo abierto toda la
semana para un cron que solo dispara una vez. `scripts/start-pipeline-stack.ps1`
y `scripts/stop-pipeline-stack.ps1` arrancan/paran Docker Desktop + n8n +
Ollama + la API de TrackerAID de un tirón.

**No puede hacerse desde dentro del propio workflow de n8n** — n8n corre
*dentro* de Docker, así que no puede arrancar Docker antes de que exista.
La forma robusta es que el Programador de tareas de Windows controle el
ciclo completo, por fuera:

1. **Tarea "arrancar"**: la que ya tienes programada (domingo 23:00) — solo
   tienes que apuntar su Acción a
   `powershell.exe -File "<ruta-del-repo>\scripts\start-pipeline-stack.ps1"`.
2. **Tarea "apagar"** (nueva, hay que crearla): mismo patrón, lunes a una
   hora con margen tras el cron de las 6:00 (por ejemplo 07:00 — el
   workflow tarda como mucho la espera de 10 min + lo que dure el lote),
   apuntando a `stop-pipeline-stack.ps1`.

Para que la tarea del domingo despierte el PC si está en suspensión (no
apagado — Task Scheduler no puede encender un PC apagado del todo), marca
la casilla **"Wake the computer to run this task"** en la pestaña
*Conditions* de la tarea.

Prueba cada script a mano primero (`powershell -File scripts\start-pipeline-stack.ps1`)
antes de fiarte de que el Programador de tareas los dispare solo.

## Pendiente (no bloquea el MVP)

- **Máquina siempre encendida**: aunque el arranque/apagado ya esté
  automatizado (ver arriba), el pipeline sigue dependiendo de que tu PC
  esté encendido o en suspensión ese domingo por la noche — si está
  apagado del todo, no hay cron que valga. Para producción real (F5) hará
  falta un host siempre activo (Railway/Fly.io free tier, o sustituir el
  Schedule Trigger de n8n por un cron de GitHub Actions) — pospuesto a
  propósito, no es necesario para probar el pipeline de punta a punta
  ahora.
- **Autenticación del endpoint**: `/pipeline/ingest` no tiene ninguna
  protección todavía (cualquiera que alcance el puerto 8000 puede
  dispararlo). Aceptable mientras corre solo en local; añadir una API key
  simple antes de exponerlo fuera de tu máquina.
