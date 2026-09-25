# Claude Watch

> Recibe en tu smartwatch un resumen de lo que Claude Code ha hecho, justo cuando termina.

---

## Que es Claude Watch?

Claude Watch es un sistema de notificaciones que te mantiene informado de lo que Claude Code hace en tu ordenador, **directamente en tu reloj inteligente WearOS**.

Cuando Claude Code termina una tarea — ya sea escribir codigo, ejecutar comandos o modificar archivos — tu reloj vibra y te muestra un resumen de lo que hizo. Asi puedes dejar a Claude trabajando de forma autonoma y saber exactamente que ocurrio sin tener que estar mirando la pantalla del ordenador.

**Es como tener un asistente que te susurra al oido cuando ha terminado.**

---

## Como funciona?

### El flujo completo

```
                        CLAUDE WATCH — FLUJO DE NOTIFICACION

  +-----------+       +-----------+       +-----------+       +-----------+
  |           |       |           |       |           |       |           |
  |  Claude   | ----> | Servidor  | ----> |  Tu movil | ----> | Tu reloj  |
  |   Code    |  POST |  (nube)   |  FCM  | (Android) |  BT  |  (WearOS) |
  |           | /notify|          | push  |           | sync  |           |
  +-----------+       +-----------+       +-----------+       +-----------+
                                                                    |
       "Tarea                "Envia                "Reenvia          |
        terminada"            notif a               al reloj"    Tu lees
                              dispositivos"                     el resumen
```

### Paso a paso

1. Claude Code **termina** una tarea en tu ordenador
2. El hook envia el resumen al **servidor**
3. El servidor lo envia por **notificacion push** a tu movil
4. Tu movil lo reenvia a tu **reloj** por Bluetooth
5. Tu reloj **vibra** y muestra que hizo Claude

### Ejemplo practico

Le pides a Claude Code: *"Refactoriza el modulo de autenticacion y anade tests"*

Claude trabaja durante unos minutos. Cuando termina, **tu reloj vibra** y muestra:

```
         .───────.
        /  12  1  \
       │ 11    2   │
       │10  .   3  │      ╔═══════════════════════╗
       │ 9    4    │  ==>  ║  Claude: Sesion        ║
        \ 8  5  6 /       ║                         ║
         '───────'        ║  Refactorizado modulo   ║
          ╱    ╲          ║  de auth y anadidos 5   ║
     Tu reloj vibra       ║  tests unitarios        ║
                          ║                         ║
                          ║        [ OK ]           ║
                          ╚═══════════════════════╝
```

Asi sabes que ya termino y que hizo, sin interrumpir lo que estuvieras haciendo.

---

## Preguntar desde el reloj

El camino de vuelta: desde el reloj, dictas o escribes una pregunta, el servidor
ejecuta el CLI `claude` en el proyecto que elijas, y la respuesta vuelve a tu
muneca.

### El flujo de una pregunta

```
                    CLAUDE WATCH — PREGUNTAR DESDE EL RELOJ

  +-----------+                       +-----------+
  |           |    POST /ask          |           |
  |  Tu reloj | --------------------> | Servidor  |
  | (WearOS)  | <---- job_id -------  | (nube)    |
  |           |                       |           |
  | "pensando"|    GET /ask/{id}      | claude -p |
  |   ● ● ●   | --------------------> | (subproc) |
  |           | <---- running ------  |           |
  |           |      cada 2 s         |           |
  |           |                       |           |
  | respuesta | <---- done + texto -  |           |
  +-----------+                       +-----------+
```

### Dos modos, y una aprobacion de por medio

- **Lectura** (por defecto) — Claude solo mira: lee y busca en los archivos y
  puede ejecutar `git status`. Nunca escribe nada. `git log` y `git diff` no
  estan permitidos porque aceptan `--output=<fichero>` y podrian escribir.
- **Escritura** — Claude primero devuelve un **plan**, sin tocar nada. Tu reloj
  lo muestra con **Aprobar** / **Cancelar**. Solo si aprueba, el servidor ejecuta
  el plan y puede modificar archivos. Un plan sin aprobar caduca a los 5 minutos.

La respuesta llega corta, para que quepa en la pantalla del reloj, con un boton
"Mas" para el texto completo y "Al movil" para mandartela por notificacion push
(hasta unos 3.500 bytes, el limite de FCM; si es mas larga llega cortada con "…").

### El coste

Cada pregunta gasta tokens reales: medido, desde unos 0,07 USD para una consulta
trivial hasta unos 0,52 USD para una que lee varios archivos y ejecuta `git`. Por
eso hay un limite de peticiones por hora — no es una restriccion arbitraria, es lo
que evita un gasto descontrolado.

Configuracion, claves y detalles tecnicos en [`server/README.md`](server/README.md).

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
    ╔═══════════════════╗
    ║                   ║
    ║   Claude Watch    ║
    ║                   ║
    ║   Esperando       ║
    ║   resumenes...    ║
    ║                   ║
    ╚═══════════════════╝
```

### Cuando llega un resumen

Tu reloj vibra suavemente y muestra:

```
    ╔═══════════════════╗
    ║     Claude        ║
    ║                   ║
    ║     Sesion        ║
    ║                   ║
    ║  Refactorizado    ║
    ║  el modulo de     ║
    ║  autenticacion    ║
    ║  y anadidos 5     ║
    ║  tests unitarios  ║
    ║                   ║
    ║      [ OK ]       ║
    ╚═══════════════════╝
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
 ┌──────────────┐      ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
 │              │      │              │      │              │      │              │
 │  ORDENADOR   │ ──── │   SERVIDOR   │ ──── │    MOVIL     │ ──── │    RELOJ     │
 │              │      │              │      │              │      │              │
 │  Claude Code │ POST │  FastAPI     │ FCM  │  App puente  │  BT  │  WearOS app  │
 │  + Hook      │ ───> │  en la nube  │ ───> │  (2do plano) │ ───> │  Notificacion│
 │              │      │              │      │              │      │              │
 └──────────────┘      └──────────────┘      └──────────────┘      └──────────────┘
       Tu PC              Internet           Tu bolsillo           Tu muneca
```

1. **Ordenador:** Claude Code trabaja y al terminar el hook envia un resumen al servidor
2. **Servidor:** Recibe el resumen y lo envia como notificacion push (FCM) al movil
3. **Movil:** Recibe la notificacion, la muestra, y la reenvia al reloj por Bluetooth
4. **Reloj:** Vibra y muestra el resumen de lo que Claude hizo

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
