# Hook — El vigilante de Claude Code

> Este componente es el "ojo" que vigila lo que Claude Code quiere hacer en tu ordenador.

---

## Que hace?

Cada vez que Claude Code quiere realizar una accion, el hook lo intercepta **antes** de que ocurra y decide si necesita tu aprobacion.

```
Claude quiere ejecutar algo
         |
    Es peligroso?
    /          \
  NO            SI
   |              |
Se ejecuta    Te avisa en
sin mas       tu reloj y
              espera tu
              respuesta
```

---

## Que acciones vigila?

### Necesitan aprobacion

- **Ejecutar comandos** — Cualquier cosa que Claude quiera ejecutar en tu terminal
- **Editar archivos** — Modificar archivos existentes de tu proyecto
- **Crear archivos** — Escribir archivos nuevos
- **Editar notebooks** — Modificar cuadernos Jupyter
- **Acciones en servicios externos** — Como crear issues en GitHub, enviar mensajes, publicar en servicios conectados, etc. (excepto las que solo leen informacion)

### No necesitan aprobacion (son seguras)

- Leer archivos (solo mira, no toca)
- Buscar archivos o texto
- Buscar en internet
- Investigar y analizar
- Consultar listas y estados

---

## Como se comporta?

### Cuando detecta una accion peligrosa

1. Envia los detalles de lo que Claude quiere hacer al servidor
2. Espera tu respuesta (aprobacion o rechazo)
3. Comprueba cada 2 segundos si ya has respondido
4. Tiene un limite de espera de 5 minutos

### Segun tu respuesta

| Tu respuesta | Que pasa |
|-------------|----------|
| **Apruebas** | Claude ejecuta la accion normalmente |
| **Rechazas** | Claude no ejecuta la accion y busca alternativas |
| **No respondes** (5 min) | La accion se bloquea por seguridad |
| **Servidor caido** | Claude continua sin restricciones (para no bloquear tu trabajo) |

---

## Resumen de sesion

Ademas de vigilar acciones, cuando Claude termina una conversacion, el hook envia un **resumen** a tu reloj para que sepas que ocurrio sin tener que mirar el ordenador.

El resumen incluye:
- Que hizo Claude durante la sesion
- Por que termino (finalizo la tarea, error, etc.)

---

## Que informacion se envia al reloj?

Solo se envia lo minimo necesario para que puedas tomar una decision:

| Dato | Ejemplo |
|------|---------|
| Tipo de accion | "Bash", "Edit", "Write" |
| Resumen corto | "rm -rf /tmp/cache" o "Edit /src/app.py" |

No se envian contrasenas, tokens, ni el contenido completo de los archivos.

---

*El hook trabaja en silencio para que tu tengas el control.*
