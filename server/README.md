# Servidor — El centro de comunicaciones

> Este componente conecta tu ordenador con tu reloj para enviar los resumenes.

---

## Que hace?

El servidor es el **puente** entre Claude Code (en tu ordenador) y las apps de tu movil y reloj. Se encarga de:

1. **Recibir resumenes** — Cuando Claude termina, el servidor recibe el resumen de la sesion
2. **Notificar a tus dispositivos** — Envia el resumen a tu movil, que lo reenvia al reloj
3. **Gestionar dispositivos** — Sabe a que moviles enviar las notificaciones

```
  ┌──────────────┐                              ┌──────────────┐
  │              │    POST /notify               │              │
  │  Tu          │    "Claude ha terminado.      │  Tu movil    │
  │  ordenador   │     Resumen: Refactorizado    │  + reloj     │
  │              │     modulo de auth..."         │              │
  │  (Hook)      │                               │              │
  └──────┬───────┘                               └──────▲───────┘
         │                                              │
         │         ┌──────────────────────┐             │
         │         │                      │             │
         └────────>│     SERVIDOR         │─────────────┘
                   │                      │  Notificacion
                   │  1. Recibe resumen   │  push (FCM)
                   │  2. Busca devices    │
                   │  3. Envia FCM push   │
                   │                      │
                   └──────────────────────┘
```

---

## Que informacion gestiona?

### Dispositivos registrados

El servidor sabe a que dispositivos enviar los resumenes. Cuando configuras la app del movil y pulsas "Register Device", tu movil se registra aqui.

---

## Seguridad

- **Autenticacion** — Toda comunicacion requiere una clave secreta
- **Datos minimos** — Solo se envian resumenes cortos, nunca archivos completos ni codigo fuente

---

## Preguntar al reloj (ask)

Ademas de recibir resumenes, el servidor deja que el **reloj** dicte una pregunta y la mande de vuelta. El reloj elige un proyecto de una lista blanca configurada en el servidor, dicta el texto, y el servidor lanza el CLI `claude` dentro de esa carpeta para conseguir una respuesta. Hay dos modos: `read` (el CLI solo puede leer archivos y ejecutar `git log`/`git diff`/`git status`, nunca escribe nada) y `write` (primero planifica, y solo si el reloj aprueba el plan se ejecuta con permiso para editar archivos). Esto es codigo nuevo que corre procesos externos en la maquina que sostiene el tunel de cloudflared y 19 contenedores, asi que la lista de proyectos y el modo lectura son deliberadamente restrictivos.

### Variables de entorno nuevas

| Variable | Por defecto | Que hace |
|---|---|---|
| `CLAUDE_WATCH_ASK_KEY` | `change-me-in-production` | Clave que debe mandar el reloj en `X-Api-Key` para usar `/projects` y `/ask*`. Es una clave distinta de `CLAUDE_WATCH_API_KEY` (la del hook) a proposito: revocar el reloj no debe tocar las notificaciones. Si se queda en el valor por defecto, estos endpoints devuelven 503 en vez de abrirse. |
| `CLAUDE_WATCH_ASK_MODEL` | `sonnet` | Modelo que usa el CLI `claude` al responder. |
| `CLAUDE_WATCH_CLAUDE_BIN` | `claude` | Ruta al binario del CLI. En produccion hace falta la ruta absoluta (ver comentario en la unit file). |
| `CLAUDE_WATCH_PROJECTS` | `` (vacio) | Lista blanca de proyectos donde el reloj puede preguntar. Formato abajo. Vacio significa que `/projects` devuelve una lista vacia y ningun `id` es valido. |
| `CLAUDE_WATCH_MAX_ASKS_PER_HOUR` | `20` | Limite de preguntas por hora, para no disparar el gasto en tokens si algo manda peticiones en bucle. |
| `CLAUDE_WATCH_READ_TIMEOUT` | `180` | Segundos maximos para una consulta en modo lectura antes de matar el proceso. |
| `CLAUDE_WATCH_WRITE_TIMEOUT` | `600` | Segundos maximos para la fase de ejecucion de un plan aprobado (modo escritura). |
| `CLAUDE_WATCH_THREAD_TTL_HOURS` | `6` | Horas que se puede seguir una conversacion con `--resume` antes de que el hilo caduque y haya que empezar uno nuevo. |
| `CLAUDE_WATCH_APPROVAL_TTL` | `300` | Segundos que un plan generado en modo escritura espera la aprobacion del reloj antes de caducar. |

### Formato de `CLAUDE_WATCH_PROJECTS`

```
id:/ruta/absoluta;id:/ruta/absoluta
```

Cada entrada es un `id` corto (lo que el reloj manda) seguido de `:` y la ruta absoluta al proyecto. Varias entradas se separan con `;`. Las rutas relativas se ignoran en silencio (no rompen el arranque del servidor, simplemente esa entrada no existe). El nombre que ve la persona en el reloj es el ultimo segmento de la ruta, asi que no hace falta repetirlo en la configuracion. La lista del ejemplo trae una sola entrada a modo de ejemplo; cada quien anade las suyas.

### Endpoints nuevos

| Metodo y ruta | Cuerpo | Que devuelve |
|---|---|---|
| `GET /projects` | — | `{"projects": [{"id", "name"}, ...]}` — solo id y nombre, la ruta nunca sale del servidor |
| `POST /ask` | `{"project_id", "prompt", "mode": "read"\|"write", "thread": "new"\|"continue"}` | `202` con `{"job_id", "status": "running"}`; `409` si ya hay una consulta en marcha, `429` si se supero el limite por hora |
| `GET /ask/{job_id}` | — | `{"status", "short", "full", "plan", "error"}` con el estado y la respuesta del job |
| `POST /ask/{job_id}/approve` | — | Ejecuta el plan generado en modo escritura tras la aprobacion del reloj; `{"status": "running"}`. Es el unico endpoint que puede modificar archivos |
| `POST /ask/{job_id}/cancel` | — | Cancela el job si sigue en marcha; devuelve el estado real, no un exito falso |
| `POST /ask/{job_id}/to-phone` | — | Reenvia la respuesta completa al movil como notificacion push; `409` si todavia no hay respuesta |

Todos requieren la cabecera `X-Api-Key` con `CLAUDE_WATCH_ASK_KEY`.

### Por que --restricted no es opcional

Medido contra el CLI real, no asumido: `--allowedTools` no restringe que herramientas existen, solo dice cuales no piden confirmacion. Y `claude` carga `~/.claude/settings.json`, que en esta maquina concede `Write`, `Edit` y `Bash` de forma global — asi que el modo "solo lectura" creaba un archivo en disco cuando se le pedia, con los 125 tests en verde, porque todos los tests usan un `claude` falso que nunca ve esa configuracion. Lo que de verdad lo arreglo fue combinar `--restricted` (ignora los settings de usuario/proyecto/local y confina las herramientas de archivos al directorio de trabajo) con `--tools` (que define que herramientas existen, no solo cuales estan pre-aprobadas). `--permission-mode manual` y `dontAsk` se probaron antes y los dos seguian escribiendo el archivo.

### Coste

Cada pregunta gasta tokens reales. Medido: unos 0,07 USD para una consulta trivial, hasta unos 0,52 USD para una que lee archivos y ejecuta `git`. Por eso existe el limite por hora — y por eso, si hace falta mas margen, se sube `CLAUDE_WATCH_MAX_ASKS_PER_HOUR` en vez de quitarlo.

### Como desplegar (sin ejecutar todavia)

Estos pasos son para cuando esta rama se fusione a `main`. **No se han ejecutado en esta tarea.**

```bash
# 1. Generar la clave del reloj
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# 2. Ponerla en server/claude-watch.service, sustituyendo
#    PON_AQUI_LA_CLAVE_DEL_RELOJ, y anadir el resto de proyectos
#    a CLAUDE_WATCH_PROJECTS si hace falta.

# 3. Copiar la unit file y recargar systemd
sudo cp server/claude-watch.service /etc/systemd/system/claude-watch.service
sudo systemctl daemon-reload
sudo systemctl restart claude-watch

# 4. Comprobar
curl -H "X-Api-Key: <la clave generada>" https://claude-watch.automatito.win/projects
```

Aviso: reiniciar el servicio interrumpe brevemente el camino de las notificaciones (`/notify`) mientras uvicorn vuelve a arrancar.

### Como verificar que el modo lectura es de verdad de solo lectura

Despues de desplegar, antes de fiarse:

1. Pide desde el reloj (o con `curl` a `/ask` en modo `read`) que se cree un archivo, por ejemplo "crea un archivo llamado prueba.txt con el texto hola".
2. Comprueba que el archivo **no existe** en el proyecto: `ls prueba.txt` deberia fallar.
3. Comprueba que `git status` en ese proyecto sigue limpio.

Si el archivo SI existe, parar ahi y no usar el modo escritura hasta averiguar por que fallo la restriccion.

---

## Disponibilidad

Si el servidor se apaga o no es accesible:
- Claude Code **no se bloquea** — sigue trabajando normalmente
- Los resumenes **no se envian** hasta que el servidor vuelva

---

*El servidor trabaja 24/7 para mantenerte conectado con Claude.*
