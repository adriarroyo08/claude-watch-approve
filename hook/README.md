# Hook — El notificador de Claude Code

> Este componente avisa a tu reloj cuando Claude Code termina una tarea.

---

## Que hace?

Cuando Claude Code termina de trabajar, el hook envia automaticamente un resumen de lo que hizo a tu reloj. No interviene durante el trabajo de Claude — solo al final.

```
  ┌─────────────────────────────────────────────┐
  │             Claude Code trabajando           │
  │                                              │
  │   Editando archivos, ejecutando comandos,    │
  │   escribiendo tests, refactorizando...       │
  │                                              │
  └──────────────────┬──────────────────────────┘
                     │
                     ▼
          ┌─────────────────────┐
          │  Claude termina     │
          │  la tarea           │
          └──────────┬──────────┘
                     │
                     ▼
          ┌─────────────────────┐
          │  Hook se activa     │
          │  automaticamente    │
          └──────────┬──────────┘
                     │
                     ▼
          ┌─────────────────────┐
          │  Envia resumen      │
          │  POST /notify       │
          │  al servidor        │
          └──────────┬──────────┘
                     │
                     ▼
          ┌─────────────────────┐
          │  Servidor → Movil   │
          │  → Reloj            │
          │                     │
          │  Tu ves que hizo    │
          └─────────────────────┘
```

---

## Que informacion se envia?

Solo lo necesario para que sepas que paso:

| Dato | Ejemplo |
|------|---------|
| Tipo de evento | "Sesion" |
| Motivo de fin | "Claude ha terminado (end_turn)" |
| Resumen del trabajo | "Refactorizado el modulo de auth, anadidos 5 tests..." |

El resumen se limita a 500 caracteres para que sea legible en el reloj.

---

## Como se comporta?

| Situacion | Que pasa |
|-----------|----------|
| Claude termina normalmente | Envia resumen al reloj |
| Claude termina con error | Envia resumen indicando el error |
| Servidor no disponible | No pasa nada, Claude sigue funcionando |
| Sin resumen disponible | Usa el ultimo mensaje de Claude como resumen |

El hook **nunca bloquea** el trabajo de Claude. Es completamente pasivo.

---

*El hook trabaja en silencio para mantenerte informado.*
