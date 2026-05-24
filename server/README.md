# Servidor — El centro de comunicaciones

> Este componente es el intermediario que conecta tu ordenador con tu reloj.

---

## Que hace?

El servidor es el **puente** entre Claude Code (en tu ordenador) y las apps de tu movil y reloj. Se encarga de:

1. **Recibir solicitudes** — Cuando Claude quiere hacer algo, el servidor recibe el aviso
2. **Notificar a tus dispositivos** — Envia la alerta a tu movil, que la reenvia al reloj
3. **Guardar las decisiones** — Registra si aprobaste o rechazaste cada accion
4. **Informar a Claude** — Cuando respondes, el servidor le dice a Claude tu decision

```
Tu ordenador                    Tus dispositivos
     |                                |
     |   "Claude quiere               |
     |    ejecutar rm -rf"            |
     |          |                      |
     +--------> SERVIDOR >----------->+
     |          |                      |
     |   Guarda la solicitud      Te llega la
     |   y espera respuesta       notificacion
     |          |                      |
     |          |          "Aprobado!" |
     +<-------- SERVIDOR <-----------<+
     |          |
     |   Claude recibe
     |   tu decision
```

---

## Que informacion gestiona?

### Solicitudes de aprobacion

Cada vez que Claude necesita tu permiso, el servidor crea un registro con:

| Campo | Que es |
|-------|--------|
| Tipo de accion | Que quiere hacer Claude (Bash, Edit, Write...) |
| Resumen | Descripcion corta de la accion |
| Estado | Pendiente, Aprobado o Denegado |
| Fecha de creacion | Cuando se creo la solicitud |
| Fecha de resolucion | Cuando respondiste |

### Dispositivos registrados

El servidor sabe a que dispositivos enviar las notificaciones. Cuando configuras la app del movil y pulsas "Register Device", tu movil se registra aqui.

---

## Estados de una solicitud

Una solicitud pasa por estos estados:

```
  Pendiente ──────> Aprobada
      |
      └────────────> Denegada
```

1. **Pendiente** — Acaba de llegar, esperando tu respuesta
2. **Aprobada** — Pulsaste OK/Aprobar, Claude puede ejecutar
3. **Denegada** — Pulsaste X/Denegar, Claude no ejecuta

---

## Seguridad

- **Autenticacion** — Toda comunicacion requiere una clave secreta. Sin ella, nadie puede enviar solicitudes ni ver decisiones.
- **Solo tu decides** — El servidor nunca aprueba ni deniega por su cuenta, solo transmite tu decision.
- **Datos minimos** — Solo se guarda el tipo de accion y un resumen corto, nunca el contenido completo de archivos o comandos largos.

---

## Disponibilidad

El servidor necesita estar funcionando para que el sistema de aprobacion opere. Si el servidor se apaga o no es accesible:

- Claude Code **no se bloquea** — continua trabajando normalmente
- Las solicitudes de aprobacion **no se envian** hasta que el servidor vuelva
- No se pierde ningun dato cuando el servidor se reinicia

---

*El servidor trabaja 24/7 para mantenerte conectado con Claude.*
