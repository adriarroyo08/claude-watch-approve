# Apps Android — Tu control remoto

> Las apps de tu movil y tu reloj que te permiten aprobar o rechazar las acciones de Claude.

---

## Dos apps, un equipo

Claude Watch Approve incluye **dos apps** que trabajan juntas:

```
+-------------------+          +-------------------+
|    App Movil      |  <--->   |    App Reloj      |
|    (Android)      |          |    (WearOS)       |
|                   |          |                   |
|  Recibe alertas   |          |  Muestra alertas  |
|  del servidor     |          |  y te deja        |
|  y las reenvia    |          |  decidir          |
|  al reloj         |          |                   |
+-------------------+          +-------------------+
```

---

## App del Movil

### Para que sirve?

La app del movil es el **puente** entre el servidor y tu reloj. Hace dos cosas:

1. **Configuracion inicial** — Conectar tu movil con el servidor
2. **Reenvio de alertas** — Recibe notificaciones del servidor y las pasa a tu reloj

### Pantalla principal

Al abrir la app veras una pantalla simple con:

```
+-----------------------------+
|                             |
|   Claude Watch Approve      |
|                             |
|   URL del servidor          |
|   [________________________]|
|                             |
|   Clave API                 |
|   [________________________]|
|                             |
|   [ Guardar Configuracion ] |
|                             |
|   [ Registrar Dispositivo ] |
|                             |
|   Estado: Registrado OK     |
|                             |
+-----------------------------+
```

### Configuracion paso a paso

1. **Abre la app** ClaudeWatch en tu movil
2. **Introduce la URL** del servidor (te la dara quien configure el sistema)
3. **Introduce tu clave API** (tu clave personal de acceso)
4. **Pulsa "Save Settings"** para guardar
5. **Pulsa "Register Device"** para vincular tu movil con el servidor
6. Veras un mensaje de confirmacion si todo salio bien

**Despues de esto, no necesitas abrir la app de nuevo.** Funciona en segundo plano.

### Notificaciones en el movil

Si tu reloj no esta disponible o desconectado, tu movil tambien muestra notificaciones con botones de **Aprobar** y **Denegar**. Asi siempre tienes una forma de responder.

---

## App del Reloj (WearOS)

### Para que sirve?

Es la app principal donde tu **decides** si aprobar o rechazar las acciones de Claude Code.

### Pantalla de espera

Cuando no hay solicitudes pendientes:

```
     +--( )--+
     |       |
     | Claude|
     | Watch |
     |       |
     |Esperan|
     |do...  |
     +-------+
```

### Pantalla de aprobacion

Cuando llega una solicitud, tu reloj vibra y muestra:

```
     +--( )--+
     |Claude |
     |       |
     | Bash  |
     |rm -rf |
     |/tmp/..|
     |       |
     |[X][OK]|
     +-------+
```

- **Arriba:** "Claude" (para que sepas de donde viene)
- **Centro:** El tipo de accion y un resumen de lo que quiere hacer
- **Abajo:** Dos botones
  - **X (rojo)** — Rechazar
  - **OK (verde)** — Aprobar

### Notificaciones

Aunque no tengas la app abierta, recibes notificaciones con:

- **Vibracion doble** (breve-breve) para distinguirla de otras apps
- **Sonido personalizado** exclusivo de Claude Watch
- **Botones de accion** directamente en la notificacion
- **Icono diferente** segun lo que Claude quiere hacer:
  - Icono de gestion → Ejecutar comando
  - Icono de edicion → Editar archivo
  - Icono de guardar → Crear archivo
  - Icono de alerta → Otras acciones

### Tile (widget en la esfera)

Puedes anadir un **tile** a tu reloj que te muestra de un vistazo:

**Sin solicitudes pendientes:**
```
     +--( )--+
     |       |
     | Claude|
     | Watch |
     |No hay |
     |pendien|
     |tes    |
     +-------+
```

**Con solicitud pendiente:**
```
     +--( )--+
     |       |
     | Bash  |
     |       |
     |rm -rf |
     |/tmp/..|
     |       |
     +-------+
```

Para anadirlo, manten pulsada la esfera del reloj y desliza hasta encontrar "Claude Watch".

---

## Formas de responder

Tienes **4 formas** de aprobar o rechazar una accion:

| Donde | Como |
|-------|------|
| **Notificacion del reloj** | Pulsa Aprobar o Denegar en la notificacion |
| **App del reloj** | Abre la app y pulsa OK o X |
| **Notificacion del movil** | Pulsa Aprobar o Denegar en la notificacion del movil |
| **Tile del reloj** | Toca el tile para abrir la app con la solicitud |

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

### Necesito tener la app del reloj abierta todo el rato?
**No.** Las notificaciones llegan en segundo plano. Puedes responder directamente desde la notificacion sin abrir la app.

### Que pasa si mi reloj esta sin bateria?
Puedes aprobar o rechazar desde la **notificacion de tu movil** como alternativa.

### Consume mucha bateria la app del reloj?
**No.** Solo se activa cuando llega una solicitud. El resto del tiempo esta dormida.

### Puedo usar la app sin reloj, solo con el movil?
**Si.** Las notificaciones del movil tambien incluyen botones de Aprobar/Denegar.

### Que pasa si desinstalo la app del movil?
Las notificaciones dejaran de llegar tanto al movil como al reloj. Claude Code seguira funcionando, pero sin el sistema de aprobacion.

---

*Tu reloj, tu decision. Control total sobre Claude Code desde tu muneca.*
