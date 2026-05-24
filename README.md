# Claude Watch

> Recibe en tu smartwatch un resumen de lo que Claude Code ha hecho, justo cuando termina.

---

## Que es Claude Watch?

Claude Watch es un sistema de notificaciones que te mantiene informado de lo que Claude Code hace en tu ordenador, **directamente en tu reloj inteligente WearOS**.

Cuando Claude Code termina una tarea — ya sea escribir codigo, ejecutar comandos o modificar archivos — tu reloj vibra y te muestra un resumen de lo que hizo. Asi puedes dejar a Claude trabajando de forma autonoma y saber exactamente que ocurrio sin tener que estar mirando la pantalla del ordenador.

**Es como tener un asistente que te susurra al oido cuando ha terminado.**

---

## Como funciona?

### El flujo en 3 pasos

```
1. Claude trabaja              2. Claude termina
   en tu ordenador                y te avisa
        |                            |
        v                            v
   +-----------+              +---------------+
   |  Claude   |  -- envia -> |   Tu reloj    |
   |   Code    |   resumen    |   WearOS      |
   +-----------+              +---------------+
                                     |
                                3. Tu ves el
                                   resumen de
                                   lo que hizo
```

### Ejemplo practico

Le pides a Claude Code: *"Refactoriza el modulo de autenticacion y anade tests"*

Claude trabaja durante unos minutos. Cuando termina, **tu reloj vibra** y muestra:

```
     +--( )--+
     |Claude |
     |       |
     |Sesion |
     |       |
     |Refacto|
     |rizado |
     |auth...|
     |       |
     |  [OK] |
     +-------+
```

Asi sabes que ya termino y que hizo, sin interrumpir lo que estuvieras haciendo.

---

## Que informacion recibes?

Cada vez que Claude termina una sesion de trabajo, recibes:

| Campo | Que te dice |
|-------|-------------|
| **Tipo** | Siempre "Sesion" (indica que Claude termino) |
| **Motivo** | Por que termino (tarea completada, error, etc.) |
| **Resumen** | Descripcion de lo que hizo durante la sesion |

---

## La app en tu reloj

### Pantalla principal

Cuando no hay resumenes recientes:

```
    +-----------------+
    |                 |
    |  Claude Watch   |
    |  Esperando      |
    |  resumenes...   |
    |                 |
    +-----------------+
```

### Cuando llega un resumen

Tu reloj vibra suavemente y muestra:

```
    +-----------------+
    |     Claude      |
    |                 |
    |     Sesion      |
    |                 |
    | Refactorizado   |
    | el modulo de    |
    | autenticacion   |
    | y anadidos 5    |
    | tests unitarios |
    |                 |
    |     [OK]        |
    +-----------------+
```

- **Titulo:** "Claude" + tipo de evento
- **Contenido:** Resumen del trabajo realizado
- **Boton OK:** Cierra el resumen

### Notificaciones

Aunque no tengas la app abierta, recibes una **notificacion** en tu reloj con:
- Vibracion suave para que lo notes
- El resumen completo del trabajo de Claude
- Se cierra automaticamente al tocarla

---

## La app en tu movil

La app del movil actua como **puente** entre el servidor y tu reloj. No necesitas interactuar con ella a diario.

### Configuracion inicial

Al abrir la app del movil, veras:

1. **URL del servidor** — La direccion donde se ejecuta el servicio
2. **API Key** — Tu clave personal de seguridad
3. **Boton "Save Settings"** — Guarda tu configuracion
4. **Boton "Register Device"** — Vincula tu movil al servidor

Una vez configurada, la app funciona en segundo plano automaticamente.

### Tambien recibes resumenes en el movil

Tu **movil tambien muestra los resumenes** como notificaciones, asi que aunque tu reloj no este disponible, siempre te enteras de lo que Claude hizo.

---

## Modo de uso ideal

Claude Watch esta pensado para usarse con Claude Code en **modo autonomo** (bypass). El flujo ideal es:

1. Le das una tarea a Claude Code
2. Dejas que trabaje sin interrupciones
3. Cuando termina, tu reloj te avisa con un resumen
4. Tu decides si necesitas revisar algo o darle otra tarea

Esto te permite **hacer otras cosas** mientras Claude trabaja, sabiendo que te avisara cuando haya terminado.

---

## Componentes del sistema

```
+------------------+     +------------------+     +------------------+
|   Tu ordenador   |     |    Tu movil      |     |   Tu reloj       |
|                  |     |    (Android)     |     |   (WearOS)       |
|  Claude Code     | --> |  App puente      | --> |  Resumenes       |
|  con notificador |     |  (segundo plano) |     |  de sesion       |
+------------------+     +------------------+     +------------------+
```

1. **Ordenador:** Claude Code trabaja normalmente y al terminar envia un resumen
2. **Movil:** Recibe el resumen y lo reenvia a tu reloj (tambien lo muestra como notificacion)
3. **Reloj:** Donde tu ves que hizo Claude

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
**No.** Las notificaciones llegan aunque la app este cerrada.

### Puedo ver los resumenes en el movil?
**Si.** Tu movil tambien recibe notificaciones con los resumenes.

### Que pasa si pierdo la conexion?
Claude Code sigue funcionando normalmente. Los resumenes simplemente no se envian hasta que vuelva la conexion.

### La app consume mucha bateria?
**No.** Solo se activa cuando llega un resumen. El resto del tiempo esta dormida.

### Funciona con cualquier reloj?
Solo con relojes que usen **WearOS 3.0 o superior** (Google Pixel Watch, Samsung Galaxy Watch 4+, TicWatch Pro 5, etc.).

### Puedo seguir usando el modo de aprobacion?
No. Esta version esta disenada exclusivamente para enviar resumenes. Claude trabaja de forma autonoma y tu recibes un informe cuando termina.

---

*Claude Watch — Siempre informado, desde tu muneca.*
