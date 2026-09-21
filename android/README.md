# Apps Android — Tu receptor de resumenes

> Las apps de tu movil y tu reloj que muestran los resumenes de Claude Code.

---

## Dos apps, un equipo

Claude Watch incluye **dos apps** que trabajan juntas:

```
  Desde el servidor (FCM push)
         │
         ▼
  ┌─────────────────────┐       Bluetooth/WiFi       ┌─────────────────────┐
  │                     │                             │                     │
  │    APP MOVIL        │  ── Wearable Data Layer ──> │    APP RELOJ        │
  │    (Android)        │                             │    (WearOS)         │
  │                     │                             │                     │
  │  - Recibe FCM push  │                             │  - Muestra resumen  │
  │  - Muestra notif    │                             │  - Vibra            │
  │  - Reenvia al reloj │                             │  - Notificacion     │
  │                     │                             │                     │
  └─────────────────────┘                             └─────────────────────┘
```

---

## App del Movil

### Para que sirve?

La app del movil es el **puente** entre el servidor y tu reloj. Hace dos cosas:

1. **Configuracion inicial** — Conectar tu movil con el servidor
2. **Reenvio de resumenes** — Recibe notificaciones del servidor y las pasa a tu reloj

### Pantalla principal

Al abrir la app veras una pantalla simple con:

```
  ╔═════════════════════════════════╗
  ║                                 ║
  ║   Claude Watch                  ║
  ║                                 ║
  ║   URL del servidor              ║
  ║   ┌───────────────────────────┐ ║
  ║   │ https://claude-watch...   │ ║
  ║   └───────────────────────────┘ ║
  ║                                 ║
  ║   Clave API                     ║
  ║   ┌───────────────────────────┐ ║
  ║   │ ************************  │ ║
  ║   └───────────────────────────┘ ║
  ║                                 ║
  ║   ┌───────────────────────────┐ ║
  ║   │   Guardar Configuracion   │ ║
  ║   └───────────────────────────┘ ║
  ║                                 ║
  ║   ┌───────────────────────────┐ ║
  ║   │   Registrar Dispositivo   │ ║
  ║   └───────────────────────────┘ ║
  ║                                 ║
  ║   Estado: Registrado OK         ║
  ║                                 ║
  ╚═════════════════════════════════╝
```

### Configuracion paso a paso

1. **Abre la app** ClaudeWatch en tu movil
2. **Introduce la URL** del servidor
3. **Introduce tu clave API**
4. **Pulsa "Save Settings"** para guardar
5. **Pulsa "Register Device"** para vincular tu movil
6. Veras un mensaje de confirmacion si todo salio bien

**Despues de esto, no necesitas abrir la app de nuevo.** Funciona en segundo plano.

### Dos claves, no una

Desde que el reloj puede preguntarle cosas a Claude, la pantalla de ajustes del
movil tiene **dos campos de clave**, no uno:

| Campo en la app | Variable en el servidor | Abre |
|---|---|---|
| **API Key** | `CLAUDE_WATCH_API_KEY` | `/notify` y `/register-device` (el hook) |
| **Clave del reloj** | `CLAUDE_WATCH_ASK_KEY` | `/projects` y `/ask*` (preguntar desde el reloj) |

Son claves distintas a proposito: si alguna vez hay que revocar la del reloj
(se pierde, se comparte por error...) eso no toca la del hook, y las
notificaciones de sesion siguen llegando sin cortes. Ninguna de las dos abre los
endpoints de la otra.

Al pulsar "Guardar Configuracion", el movil manda la URL del servidor y la
**Clave del reloj** al reloj por Wearable Data Layer, en la ruta
`/claude-watch/config`, dentro de un campo llamado `watch_key`. El reloj guarda
eso en su propio almacenamiento y lo usa para hablar directamente con el
servidor — no pasa por el movil en cada pregunta.

### Notificaciones en el movil

Tu movil tambien muestra los resumenes como notificaciones. Asi siempre te enteras, aunque tu reloj no este disponible.

---

## App del Reloj (WearOS)

### Para que sirve?

Es donde ves los **resumenes** de lo que Claude Code hizo.

### Pantalla de espera

Cuando no hay resumenes recientes:

```
        .───────.
       / Claude  \
      │  Watch    │
      │           │
      │ Esperando │
      │ resumenes │
       \  ...    /
        '───────'
```

### Pantalla de resumen

Cuando llega un resumen, tu reloj vibra y muestra:

```
        .───────.
       /  Claude  \
      │   Sesion   │
      │            │
      │ Refactori- │
      │ zado auth  │
      │ y tests    │
      │            │
       \  [ OK ]  /
        '───────'
```

- **Arriba:** "Claude" (origen del resumen)
- **Centro:** Tipo de evento y resumen del trabajo
- **Abajo:** Boton OK para cerrar

### Notificaciones

Aunque no tengas la app abierta, recibes notificaciones con:
- **Vibracion suave** para que lo notes
- **Resumen expandido** del trabajo realizado
- Se cierra automaticamente al tocarla

---

## Compilar en este servidor (aarch64)

Se puede compilar el APK en esta misma maquina, aunque sea aarch64. Gradle
descarga un `aapt2` x86-64, y hace falta correrlo bajo qemu con un sysroot
x86-64 (sin instalar paquetes de sistema, solo lo que hace falta para resolver
sus librerias):

```bash
SR=~/.cache/x86_64-sysroot
CID=$(docker create --platform linux/amd64 ubuntu:24.04 true)
mkdir -p $SR/lib $SR/lib64
docker cp -q $CID:/usr/lib/x86_64-linux-gnu $SR/lib/
docker cp -q -L $CID:/lib64/ld-linux-x86-64.so.2 $SR/lib64/
docker rm $CID
export QEMU_LD_PREFIX=$SR ANDROID_HOME=~/android-sdk
./gradlew :wear:assembleDebug :mobile:assembleDebug --no-daemon
```

`--no-daemon` no es opcional: un daemon de Gradle arrancado sin
`QEMU_LD_PREFIX` en el entorno falla con `libdl.so.2` al intentar usar `aapt2`,
y como el daemon persiste entre builds, una vez arrancado mal sigue mal hasta
que se mata.

El modulo `mobile` ademas necesita `android/mobile/google-services.json`, que
esta en `.gitignore` (trae la configuracion de Firebase) y hay que copiarlo a
mano antes de compilar ese modulo.

---

## Requisitos

| Dispositivo | Necesitas |
|-------------|-----------|
| **Reloj** | WearOS 3.0+ (Galaxy Watch 4+, Pixel Watch, TicWatch Pro 5...) |
| **Movil** | Android 9.0 o superior |
| **Vinculacion** | Movil y reloj deben estar conectados (Bluetooth/WiFi) |
| **Internet** | El movil necesita conexion a internet |

---

## Preguntas frecuentes

### Necesito tener la app del reloj abierta?
**No.** Las notificaciones llegan en segundo plano.

### Que pasa si mi reloj esta sin bateria?
Puedes ver los resumenes en las **notificaciones de tu movil**.

### Consume mucha bateria la app del reloj?
**No.** Solo se activa cuando llega un resumen. El resto del tiempo esta dormida.

### Puedo usar la app sin reloj, solo con el movil?
**Si.** El movil tambien recibe los resumenes como notificaciones.

---

*Tu reloj te mantiene informado de lo que Claude hace por ti.*
