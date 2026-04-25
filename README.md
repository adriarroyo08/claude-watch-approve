# Claude Watch Approve

Sistema de aprobacion remota para Claude Code desde tu smartwatch WearOS. Cuando Claude Code intenta ejecutar una accion potencialmente peligrosa (Bash, Edit, Write...), recibiras una notificacion en tu reloj para aprobar o denegar la ejecucion.

## Arquitectura

```
Claude Code CLI
       |
  Hook (pre_tool_use)
       |
  POST /approval-request
       |
  Backend Server (FastAPI)
       |
  Firebase Cloud Messaging
       |
  Mobile App (Android)
       |
  Wearable Data Layer
       |
  WearOS App (Smartwatch)
       |
  Usuario: Approve / Deny
       |
  (camino inverso hasta el Hook)
```

## Componentes

### 1. Hook - Interceptor de Claude Code

**`hook/claude_watch_hook.py`**

Intercepta las ejecuciones de herramientas antes de que se ejecuten.

**Herramientas que requieren aprobacion:**
- `Bash`, `Edit`, `Write`, `NotebookEdit`
- Acciones MCP excepto las que empiezan por: get, list, search, read, fetch, find, check, validate

**Herramientas seguras (sin aprobacion):**
- `Read`, `Glob`, `Grep`, `Agent`, `WebSearch`, `WebFetch`, `Skill`, `TaskList`, `TaskGet`

**Variables de entorno:**
| Variable | Default | Descripcion |
|----------|---------|-------------|
| `CLAUDE_WATCH_URL` | `https://claude-watch.automatito.win` | URL del servidor |
| `CLAUDE_WATCH_API_KEY` | - | Clave de autenticacion |
| `CLAUDE_WATCH_POLL_INTERVAL` | `2` | Intervalo de polling (segundos) |
| `CLAUDE_WATCH_TIMEOUT` | `300` | Timeout maximo (segundos) |

**Comportamiento fail-open:** si el servidor no responde, la ejecucion se permite automaticamente.

### 2. Servidor Backend

**`server/`** — FastAPI + SQLite + Firebase Admin SDK

Escucha en `http://127.0.0.1:8400`, proxy via Nginx en `claude-watch.automatito.win`.

#### Endpoints

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| POST | `/approval-request` | Crea solicitud de aprobacion y envia FCM |
| GET | `/approval-status/{id}` | Consulta estado (pending/approved/denied) |
| POST | `/approval-response/{id}` | Envia decision desde mobile/watch |
| POST | `/register-device` | Registra token FCM del dispositivo |

Todos los endpoints requieren header `X-Api-Key`.

#### Base de datos (SQLite)

**Tabla `approvals`:** id, tool_name, tool_input_summary, context, status, created_at, resolved_at

**Tabla `devices`:** id, fcm_token, updated_at

### 3. Mobile App (Android)

**`android/mobile/`** — Kotlin + Jetpack Compose

App companion que actua como puente entre FCM y el reloj.

| Clase | Funcion |
|-------|---------|
| `MainActivity` | Pantalla de configuracion (URL servidor + API key) |
| `SettingsStore` | Persistencia con DataStore Preferences |
| `ApprovalFcmService` | Recibe notificaciones FCM y las reenvia al reloj |
| `DataLayerSender` | Envia solicitudes al watch via Wearable Data Layer |
| `DataLayerReceiver` | Recibe respuestas del watch y las envia al servidor |
| `ApiClient` | Cliente HTTP Retrofit para comunicar con el backend |
| `SettingsScreen` | UI de configuracion con Material 3 |

**Requisitos:** Android 9.0+ (API 28)

### 4. WearOS App (Smartwatch)

**`android/wear/`** — Kotlin + Wear Compose + Tiles API

| Clase | Funcion |
|-------|---------|
| `MainActivity` | Pantalla principal con botones Approve/Deny |
| `DataLayerListenerService` | Escucha solicitudes en background |
| `ApprovalNotificationManager` | Notificaciones con vibracion, sonido y acciones |
| `ApprovalActionReceiver` | Procesa respuestas desde las acciones de notificacion |
| `ApprovalTileService` | Tile para acceso rapido desde la esfera del reloj |
| `ApprovalScreen` | UI Compose con botones circulares Deny (rojo) / Approve (verde) |

**Requisitos:** WearOS 3.0+ (API 31)

**Notificaciones:** Vibracion personalizada, sonido custom (`approval_sound.ogg`), iconos segun tipo de herramienta.

## Flujo completo

1. Claude Code ejecuta una herramienta (ej: `Bash: rm -rf /tmp/cache`)
2. El hook intercepta y envia POST `/approval-request` al servidor
3. El servidor crea registro en DB y envia notificacion FCM
4. El mobile recibe FCM y reenvia al watch via Wearable Data Layer
5. El watch muestra notificacion con Approve/Deny
6. El usuario pulsa en el reloj
7. El watch envia respuesta al mobile via Data Layer
8. El mobile envia POST `/approval-response/{id}` al servidor
9. El hook (polling cada 2s) recibe la decision
10. Si aprobado: la herramienta se ejecuta. Si denegado: se bloquea.

## Build

### Requisitos
- Java 17
- Android SDK 35

### Compilar

```bash
cd android
./gradlew :wear:assembleDebug      # WearOS
./gradlew :mobile:assembleDebug    # Mobile
./gradlew assembleRelease          # Ambos (release)
```

### Instalar via ADB

```bash
adb install wear/build/outputs/apk/debug/wear-debug.apk
adb install mobile/build/outputs/apk/debug/mobile-debug.apk
```

### CI/CD

El workflow de GitHub Actions compila y publica APKs automaticamente al mergear un PR a `main`. Los `google-services.json` se inyectan desde GitHub Secrets en base64:

- `GOOGLE_SERVICES_WEAR` — base64 del google-services.json del modulo wear
- `GOOGLE_SERVICES_MOBILE` — base64 del google-services.json del modulo mobile

## Servidor - Despliegue

### Variables de entorno

```bash
export CLAUDE_WATCH_API_KEY="tu-clave-secreta"
export CLAUDE_WATCH_DB_PATH="/path/to/approvals.db"
export CLAUDE_WATCH_FCM_CREDENTIALS="/path/to/firebase-credentials.json"
export CLAUDE_WATCH_TIMEOUT="300"
```

### Ejecutar

```bash
cd server
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8400
```

### Nginx (proxy)

Dominio: `claude-watch.automatito.win` → `http://127.0.0.1:8400`

## Tests

```bash
# Server tests
cd server && pytest

# Hook tests
cd hook && pytest
```

33+ tests cubriendo endpoints, base de datos, FCM y logica del hook.

## Configuracion del Mobile

1. Abre la app ClaudeWatch en tu telefono
2. Introduce la URL del servidor y tu API key
3. Pulsa "Save Settings"
4. Pulsa "Register Device" para registrar el token FCM

## Stack Tecnologico

| Componente | Tecnologia |
|------------|------------|
| Hook | Python 3 |
| Backend | FastAPI + SQLite + Firebase Admin |
| Mobile | Kotlin, Jetpack Compose, Retrofit, DataStore, FCM |
| WearOS | Kotlin, Wear Compose, Tiles API, Wearable Data Layer |
| CI/CD | GitHub Actions |
| Proxy | Nginx |
