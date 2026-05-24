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

## Disponibilidad

Si el servidor se apaga o no es accesible:
- Claude Code **no se bloquea** — sigue trabajando normalmente
- Los resumenes **no se envian** hasta que el servidor vuelva

---

*El servidor trabaja 24/7 para mantenerte conectado con Claude.*
