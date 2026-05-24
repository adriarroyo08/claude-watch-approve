# Claude Watch Approve

> Aprueba o rechaza las acciones de Claude Code directamente desde tu smartwatch.

---

## Que es Claude Watch Approve?

Claude Watch Approve es un sistema de seguridad personal que te permite supervisar y controlar lo que hace Claude Code en tu ordenador, **directamente desde tu reloj inteligente WearOS**.

Cuando Claude Code quiere hacer algo importante en tu sistema — como ejecutar un comando, modificar un archivo o escribir codigo nuevo — tu reloj vibra y te muestra exactamente que quiere hacer. Con un simple toque, decides si lo permites o lo bloqueas.

**Es como tener un guardia de seguridad en tu muneca.**

---

## Como funciona?

### El flujo en 4 pasos

```
1. Claude quiere hacer algo       2. Tu reloj vibra
   en tu ordenador                   y te avisa
        |                               |
        v                               v
   +-----------+                 +---------------+
   |  Claude   |  --- envia ---> |   Tu reloj    |
   |   Code    |                 |   WearOS      |
   +-----------+                 +---------------+
                                        |
                                   Tu decides:
                                  Aprobar o Denegar
                                        |
        +-----------+                   |
        |  Claude   | <--- respuesta ---+
        |   Code    |
        +-----------+
              |
   3. Si aprobaste:              4. Si rechazaste:
      Claude ejecuta la accion      Claude se detiene
```

### Ejemplo practico

Imagina que le pides a Claude Code: *"Limpia los archivos temporales del proyecto"*

1. Claude decide ejecutar el comando `rm -rf /tmp/cache`
2. **Tu reloj vibra** y muestra:
   - **Herramienta:** Bash
   - **Detalle:** `rm -rf /tmp/cache`
3. Tu miras el reloj y pulsas:
   - **OK** (boton verde) → Claude ejecuta el comando
   - **X** (boton rojo) → Claude no hace nada y busca otra forma

---

## Que acciones requieren tu aprobacion?

### Acciones que SI necesitan aprobacion

| Accion | Que significa |
|--------|--------------|
| **Ejecutar comandos** | Claude quiere ejecutar algo en la terminal (instalar paquetes, borrar archivos, ejecutar scripts...) |
| **Editar archivos** | Claude quiere modificar un archivo existente en tu proyecto |
| **Crear archivos** | Claude quiere crear un archivo nuevo |
| **Editar notebooks** | Claude quiere modificar un cuaderno Jupyter |
| **Acciones externas** | Claude quiere interactuar con servicios externos (enviar mensajes, crear issues, publicar codigo...) |

### Acciones que NO necesitan aprobacion

| Accion | Por que es segura |
|--------|-------------------|
| **Leer archivos** | Solo mira, no toca nada |
| **Buscar archivos** | Solo busca nombres de archivos |
| **Buscar texto** | Solo busca texto dentro de archivos |
| **Buscar en internet** | Solo consulta informacion |
| **Investigar** | Claude piensa y analiza, sin modificar nada |

---

## La app en tu reloj

### Pantalla principal

Cuando no hay solicitudes pendientes, tu reloj muestra:

```
    +-----------------+
    |                 |
    |  Claude Watch   |
    |  Esperando...   |
    |                 |
    +-----------------+
```

### Cuando llega una solicitud

Tu reloj vibra con un patron doble (breve-breve) y muestra:

```
    +-----------------+
    |     Claude      |
    |                 |
    |      Bash       |
    | rm -rf /tmp/... |
    |                 |
    |  [X]      [OK]  |
    |  rojo    verde  |
    +-----------------+
```

- **Titulo:** El tipo de accion (Bash, Edit, Write...)
- **Detalle:** Un resumen de lo que Claude quiere hacer
- **Boton X (rojo):** Rechazar la accion
- **Boton OK (verde):** Aprobar la accion

### Notificaciones

Aunque no tengas la app abierta, recibes una **notificacion** en tu reloj con:
- Vibracion personalizada para que lo distingas de otras notificaciones
- Sonido propio
- Botones de **Aprobar** y **Denegar** directamente en la notificacion (sin necesidad de abrir la app)
- Icono diferente segun el tipo de accion

### Tile (acceso rapido)

Puedes anadir un **tile** (widget) a la esfera de tu reloj que muestra:
- Si no hay solicitudes: *"No pending requests"*
- Si hay una solicitud pendiente: El nombre de la herramienta y un resumen

Asi puedes ver de un vistazo si Claude necesita algo, sin abrir la app.

---

## La app en tu movil

La app del movil actua como **puente** entre el servidor y tu reloj. No necesitas interactuar con ella a diario.

### Configuracion inicial

Al abrir la app del movil, veras una pantalla sencilla con:

1. **URL del servidor** — La direccion donde se ejecuta el servicio
2. **API Key** — Tu clave personal de seguridad
3. **Boton "Save Settings"** — Guarda tu configuracion
4. **Boton "Register Device"** — Vincula tu movil al servidor

Una vez configurada, la app funciona en segundo plano automaticamente.

### Tambien recibes notificaciones en el movil

Si tu reloj no esta disponible, tu **movil tambien muestra las solicitudes** con botones de Aprobar/Denegar, asi que siempre tienes una forma de responder.

---

## Resumen de sesion

Cuando Claude termina una tarea, recibes una **notificacion resumen** en tu reloj con lo que hizo. Asi puedes estar al tanto de todo sin estar mirando la pantalla del ordenador.

---

## Seguridad y timeouts

### Que pasa si no respondo?

Si no respondes en **5 minutos**, la accion se **bloquea automaticamente** por seguridad. Claude no hara nada sin tu permiso explícito.

### Que pasa si pierdo la conexion?

Si el servidor no esta disponible (sin internet, servidor apagado...), Claude **continua funcionando normalmente**. El sistema esta disenado para no bloquear tu trabajo si hay un problema de conexion.

### Resumen de comportamiento

| Situacion | Que ocurre |
|-----------|------------|
| Apruebas en el reloj | Claude ejecuta la accion |
| Rechazas en el reloj | Claude no ejecuta la accion |
| No respondes en 5 min | La accion se bloquea (por seguridad) |
| Sin conexion al servidor | Claude continua normalmente |

---

## Componentes del sistema

Claude Watch Approve se compone de tres partes que trabajan juntas:

```
+------------------+     +------------------+     +------------------+
|   Tu ordenador   |     |    Tu movil      |     |   Tu reloj       |
|                  |     |    (Android)     |     |   (WearOS)       |
|  Claude Code     | --> |  App puente      | --> |  App de          |
|  con vigilancia  |     |  (segundo plano) |     |  aprobacion      |
+------------------+     +------------------+     +------------------+
```

1. **Ordenador:** Claude Code funciona como siempre, pero con un vigilante que detecta acciones importantes
2. **Movil:** Recibe las alertas y las reenvia a tu reloj (tambien puede aprobar/denegar)
3. **Reloj:** Donde tu decides si aprobar o rechazar cada accion

---

## Requisitos

| Dispositivo | Requisito minimo |
|-------------|-----------------|
| Reloj | WearOS 3.0 o superior |
| Movil | Android 9.0 o superior |
| Movil y reloj | Deben estar vinculados entre si |
| Conexion | El movil necesita internet |

---

## Preguntas frecuentes

### Necesito tener la app del reloj abierta?
**No.** Las notificaciones llegan aunque la app este cerrada. Puedes aprobar o denegar directamente desde la notificacion.

### Puedo aprobar desde el movil en vez del reloj?
**Si.** Si tu reloj no esta accesible, puedes responder desde la notificacion del movil.

### Que pasa si apruebo sin querer?
Claude ejecutara la accion. Si quieres mas seguridad, revisa siempre el detalle de lo que Claude quiere hacer antes de pulsar.

### Puedo cambiar el tiempo de espera?
**Si.** El tiempo por defecto es de 5 minutos, pero se puede ajustar en la configuracion del sistema.

### La app consume mucha bateria?
**No.** La app del reloj solo se activa cuando recibe una solicitud. El resto del tiempo esta en reposo.

### Funciona con cualquier reloj?
Solo con relojes que usen **WearOS 3.0 o superior** (Google Pixel Watch, Samsung Galaxy Watch 4+, TicWatch Pro 5, etc.).

---

*Claude Watch Approve — Control total desde tu muneca.*
