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
