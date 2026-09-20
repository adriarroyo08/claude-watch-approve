# Preguntar a Claude desde el reloj — diseño

Fecha: 2026-09-20
Estado: aprobado, pendiente de plan de implementación

## Problema

Claude Watch hoy es un megáfono de una sola dirección: Claude Code termina, el hook
avisa al servidor, y el resumen acaba en la muñeca. No hay camino de vuelta. Para
preguntar cualquier cosa —"¿cómo fue la ronda de scrapers de anoche?"— hay que ir al
ordenador.

Este diseño añade el canal de vuelta: dictar o teclear una pregunta en el reloj,
que la conteste un `claude -p` en el servidor, y leer la respuesta en la muñeca.

El camino existente (hook → `/notify` → FCM → móvil → Data Layer → reloj) no se toca.

## Contexto que condiciona el diseño

- El servidor FastAPI corre en **la misma máquina** que el `claude` CLI (2.1.278),
  como systemd en `127.0.0.1:8400` detrás de nginx en `claude-watch.automatito.win`.
  Puede lanzar `claude -p` directamente.
- La app del reloj (`android/wear/`) no tiene hoy ni permiso de Internet ni cliente
  HTTP: solo `play-services-wearable`. Hay que dárselos.
- La app del móvil ya tiene Retrofit, FCM y `SettingsStore` con URL y clave.
- **El APK no se puede compilar en esta máquina**: el `aapt2` que descarga Gradle es
  x86-64 y la máquina es aarch64. El APK sale del CI (`release-on-merge.yml`) al
  mergear a `main`. El servidor sí se prueba en local.

## Decisiones tomadas

| Decisión | Elegido | Por qué |
|---|---|---|
| Permisos de `claude -p` | Dos modos elegibles en el reloj, lectura por defecto | Consultar es el caso normal; actuar debe ser deliberado |
| Transporte | Reloj ↔ servidor directo por HTTPS | Menos saltos; Wear OS enruta por WiFi o por el Bluetooth del móvil |
| Directorio de trabajo | Selector de proyecto en el reloj, lista blanca en el servidor | ~25 repos en `~/`; el cliente nunca manda una ruta |
| Continuidad | Hilo por proyecto vía `--resume` | Desde el reloj repreguntar es la norma, no la excepción |
| Respuesta larga | Corta + "más" + "al móvil" | La pantalla es de 1 pulgada, pero perder detalle no es opción |
| Red en modo escritura | Plan → apruebas → ejecuta | La voz se come palabras; ejecutar a ciegas lo dictado en la calle no |

## Arquitectura

```
                    CLAUDE WATCH — PREGUNTAR DESDE EL RELOJ

   RELOJ (WearOS)                    SERVIDOR (misma máquina que claude)
  ┌──────────────┐                  ┌────────────────────────────┐
  │ 🎤 / ⌨ voz   │  1. POST /ask    │  valida proyecto (lista     │
  │   o teclado  │ ───────────────> │  blanca) y encola 1 job     │
  │              │  <─── job_id ─── │                             │
  │              │     (al instante)│         │                   │
  │  "pensando"  │                  │         v                   │
  │   ●  ●  ●    │  2. GET /ask/id  │   subprocess:               │
  │              │ ───────────────> │   claude -p … --output-     │
  │   cada 2 s   │  <── running ─── │   format json  (cwd=repo)   │
  │              │                  │         │                   │
  │  respuesta   │  3. GET /ask/id  │         v                   │
  │  corta + más │ <── done + texto │   guarda session_id,        │
  └──────────────┘                  │   corto y largo en SQLite   │
         │                          └────────────────────────────┘
         │ 4. "al móvil"                        │
         └──────────────────> FCM ──────────> MÓVIL (texto completo)
```

### Piezas nuevas

Cada una tiene un solo trabajo y se puede entender y probar sin abrir las demás.

| Pieza | Qué hace | De qué depende |
|---|---|---|
| `server/runner.py` | Construye el comando `claude` y lo lanza como subproceso con timeout. Parsea la salida JSON. | `asyncio.subprocess` |
| `server/jobs.py` | Cola de un solo job, máquina de estados, persistencia. No sabe qué es Claude. | `database.py` |
| Endpoints `/ask*` en `server/main.py` | HTTP, autenticación, límite de peticiones. No sabe lanzar procesos. | `jobs.py` |
| `android/wear/.../ask/` | `AskActivity`, sus cuatro pantallas y el cliente HTTP. | Retrofit, RemoteInput |

### Por qué el reloj sondea en vez de esperar

nginx corta a los 60 s y Wear OS apaga la radio en cuanto puede; `claude -p` tarda
entre 10 s y varios minutos. Un `GET /ask/{job_id}` cada 2 s sobrevive a las dos
cosas, permite cancelar a mitad y hace que perder la red sea recuperable.

### Una sola petición a la vez

Un `claude -p` cuesta tokens reales. La cola tiene profundidad 1: si llega otra
petición mientras una corre, el servidor responde **409** y el reloj ofrece cancelar
la que está en marcha. No se encola gasto en segundo plano.

## API

Todos los endpoints nuevos exigen la cabecera `X-Api-Key` con la clave del reloj.

| Método | Ruta | Cuerpo / respuesta |
|---|---|---|
| `GET` | `/projects` | → `{"projects": [{"id": "ahorrapp", "name": "AhorrApp"}, ...]}` |
| `POST` | `/ask` | `{project_id, prompt, mode, thread}` → **202** `{job_id, status}` |
| `GET` | `/ask/{job_id}` | → `{status, short, full, plan, error}` |
| `POST` | `/ask/{job_id}/approve` | Solo si `status == awaiting_approval` → **200**, vuelve a `running` |
| `POST` | `/ask/{job_id}/cancel` | Mata el subproceso → `cancelled` |
| `POST` | `/ask/{job_id}/to-phone` | Manda `full` al móvil por FCM reutilizando `send_info_notification` |

Validación de `POST /ask`:

- `project_id`: debe existir en la lista blanca, si no **404**
- `prompt`: 1–1000 caracteres
- `mode`: `read` | `write`
- `thread`: `continue` | `new`

### Máquina de estados de un job

```
                    ┌─────────> done
                    │
  running ──────────┼─────────> error
     │              │
     │              └─────────> cancelled
     │
     └──> awaiting_approval ──(approve)──> running ──> done
                    │
                    └──(caduca a 5 min / cancel)──> cancelled
```

## Los tres comandos

El `cwd` del subproceso es siempre la ruta del proyecto resuelta desde la lista
blanca, nunca algo que venga del cliente.

**Lectura.** `--permission-prompts none` hace que cualquier herramienta fuera de la
lista se deniegue sola en vez de dejar el proceso esperando un permiso que nadie va
a conceder:

```
claude -p "<prompt>" --output-format json --permission-prompts none \
  --allowedTools Read Grep Glob "Bash(git log:*)" "Bash(git diff:*)" "Bash(git status:*)" \
  --append-system-prompt "<brevedad>" [--resume <session_id>]
```

**Escritura, fase 1 (plan).** Claude mira y piensa, pero no puede tocar nada aunque
quiera:

```
claude -p "<prompt>" --output-format json --permission-mode plan \
  --permission-prompts none --append-system-prompt "<brevedad>" [--resume <session_id>]
```

Termina en `awaiting_approval`, guardando `session_id` y el plan.

**Escritura, fase 2 (al aprobar).** Continúa exactamente la sesión cuyo plan
acabas de leer, así que no hay hueco entre lo aprobado y lo ejecutado:

```
claude -p "Ejecuta el plan que acabas de describir." --resume <session_id> \
  --output-format json --permission-mode acceptEdits --permission-prompts none \
  --disallowedTools "Bash(git push:*)" "Bash(sudo:*)" "Bash(systemctl:*)" \
                    "Bash(docker:*)" "Bash(rm:*)" WebFetch
```

### Corta y larga en una sola llamada

`--append-system-prompt` pide las dos versiones de golpe, en vez de pagar dos
invocaciones:

> Responde con una primera línea de 40 palabras o menos que conteste directamente,
> sin preámbulo. Después una línea en blanco. Después el detalle. Sin markdown ni
> tablas: esto se lee en un reloj.

El servidor parte por el primer `\n\n`: lo de arriba es `short`, el texto entero es
`full`. Si Claude ignora el formato y no hay línea en blanco, `short` son los
primeros 200 caracteres y no se rompe nada.

### Hilo por proyecto

El servidor guarda el `session_id` que devuelve `--output-format json` asociado al
proyecto. Con `thread: "continue"` añade `--resume <session_id>`; con `"new"` lo
ignora y lo sustituye. El hilo caduca a las 6 horas para no arrastrar contexto
viejo de otro día.

## Seguridad

1. **Clave propia para el reloj.** `CLAUDE_WATCH_ASK_KEY`, distinta de
   `CLAUDE_WATCH_API_KEY`. `/notify` solo acepta la del hook; `/ask*` solo la del
   reloj. Perder el reloj se arregla revocando una sola clave, sin romper las
   notificaciones. Comparación con `hmac.compare_digest`, como ya hace el código.
2. **El cliente nunca manda una ruta**, manda un `project_id` de un diccionario en
   config. Un `../../etc` sencillamente no es una clave que exista.
3. **`approve` caduca a los 5 minutos.** Un plan aprobado dos horas después, cuando
   ya no recuerdas qué decía, no se ejecuta.
4. **Lista negra en la fase de ejecución**: `git push`, `sudo`, `systemctl`,
   `docker`, `rm`, `WebFetch`. Esta máquina sostiene el túnel de cloudflared y 19
   contenedores; un "docker" mal entendido por el reconocimiento de voz hace daño
   de verdad.
5. **20 peticiones por hora** y prompt de 1000 caracteres máximo.
6. **Timeouts**: 180 s en lectura, 600 s en escritura.
7. **Modelo configurable** (`CLAUDE_WATCH_ASK_MODEL`). Las preguntas de muñeca son
   cortas y no necesitan el modelo más caro.

Aun con todo esto, el modo escritura es una llave al servidor colgada de la muñeca.
La red del plan lo hace razonable, no inofensivo. Está diseñado para poder
amputarse limpio: quitarlo es borrar dos endpoints y una pantalla.

### Configuración nueva

```
CLAUDE_WATCH_ASK_KEY        # clave del reloj, distinta de la del hook
CLAUDE_WATCH_ASK_MODEL      # modelo para las consultas del reloj
CLAUDE_WATCH_PROJECTS       # id:ruta;id:ruta — la lista blanca
```

## Las apps

### Reloj

La entrada no hay que escribirla: `RemoteInput` abre el selector del sistema de
Wear OS, que ya ofrece voz, teclado, escritura a mano y respuestas guardadas en una
sola pantalla.

```
  WaitingScreen            AskScreen              ThinkingScreen
  (la de hoy)          ┌──────────────┐         ┌──────────────┐
  ┌──────────────┐     │  AhorrApp  ▾ │         │      ●●●     │
  │   Claude     │ ──> │              │  ───>   │   pensando   │
  │   Watch      │     │   🎤  ⌨       │         │   0:14       │
  │              │     │              │         │  [Cancelar]  │
  │ [Preguntar]  │     │ lectura ●──○ │         └──────────────┘
  └──────────────┘     └──────────────┘                 │
                                                        v
   PlanScreen (solo escritura)            AnswerScreen
  ┌──────────────┐                      ┌──────────────┐
  │ Va a tocar   │                      │ La ronda de  │
  │ 3 archivos   │                      │ anoche metió │
  │ de scrapers  │      ──── o ────>    │ 12.400 fichas│
  │[✓ Aprobar]   │                      │ [más][móvil] │
  │[✗ Cancelar]  │                      │ [repreguntar]│
  └──────────────┘                      └──────────────┘
```

`AskActivity` va separada de `MainActivity` a propósito. `MainActivity` son 56
líneas que hacen una cosa bien: recibir resúmenes por Data Layer. Meterle cuatro
pantallas, un sondeo y una máquina de estados la convertiría en el archivo que ya
nadie quiere tocar. El camino de las notificaciones no se modifica.

Cambios necesarios en `android/wear/`: permiso `INTERNET`, Retrofit + Gson (los
mismos que ya usa el móvil), DataStore para guardar la configuración recibida.

### Móvil

Casi nada: `DataLayerSender` gana un `sendConfig()` que empuja URL y clave al reloj
por `/claude-watch/config` al guardar ajustes y al detectar el reloj. La respuesta
larga que pidas "al móvil" llega como notificación FCM por la tubería existente.

## Qué ves cuando algo falla

| Qué pasa | Qué ves en el reloj |
|---|---|
| El reloj pierde la red a mitad | "Sin conexión" y reintentar. El job sigue vivo: guarda el `job_id` y al volver recupera la respuesta. |
| Reinicias el servidor a mitad | Al arrancar, los jobs `running` huérfanos pasan a `error` ("se interrumpió"), en vez de girar para siempre. |
| `claude` sale con código distinto de 0 | "Error" y los primeros 300 caracteres de `stderr`. |
| Se pasa del timeout | "Tardó demasiado", sugiriendo mirarlo en el ordenador. |
| Pides algo con otra consulta en marcha | **409** "hay una consulta en marcha", con opción de cancelarla. |
| `project_id` desconocido | **404**. |
| Claude ignora el formato de respuesta | `short` son los primeros 200 caracteres. |

## Tests

Servidor, con el subproceso simulado: los tests no gastan tokens.

- **runner**: comando correcto en los tres modos; `cwd` es el repo; la lista negra
  viaja en el de ejecución; `--resume` solo cuando `thread == "continue"`
- **parseo**: con línea en blanco, sin ella, respuesta vacía
- **jobs**: transiciones válidas; `approve` rechazado fuera de `awaiting_approval`;
  `approve` caducado a los 5 min; `cancel`
- **endpoints**: 202 con `job_id`; 409 si hay uno corriendo; 404 con proyecto
  desconocido; **403 al usar la clave del hook en `/ask`**; el límite salta en la
  petición 21; prompt de 1001 caracteres rechazado
- **arranque**: job huérfano → `error`

Unos 20 tests nuevos sobre los 20 que ya existen.

En Android no hay tests hoy y este trabajo no los introduce: el reloj se verifica a
mano con el APK que publique el CI. Queda dicho explícitamente para que nadie lea
"tests" y suponga cobertura que no existe.

## Fuera de alcance

Tile y complication para lanzar más rápido, respuesta palabra a palabra, historial
de conversaciones en el reloj, adjuntar imágenes, varias consultas en paralelo.
Todo es añadible después; nada hace falta para que la idea funcione.
