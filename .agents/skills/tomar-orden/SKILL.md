---
name: tomar-orden
description: Toma una orden de trabajo (una issue con la etiqueta orden), la ejecuta en su rama y la devuelve con un PR con evidencia. Úsala cuando alguien diga que toma, empieza o continúa la orden #N, o pegue la frase de arranque de una orden.
---

# Tomar una orden

Una orden es una issue con la etiqueta `orden`, y se nombra por su número: la orden #N es la
issue N. Tiene que bastar por sí sola; si falta algo para ejecutarla, se pregunta en la issue y
no se adivina.

1. **Leer la orden entera**, con sus comentarios: `gh issue view N --comments`. Si hay una nota
   de relevo, es la continuación del trabajo de otra persona: se lee también su rama.
2. **Marcarla como tomada**: `gh issue comment N --body "la tomo"` y
   `gh issue edit N --add-assignee "@me" --remove-label lista --add-label en-curso`.
3. **La rama.** Orden nueva: `git switch main`, `git pull` y `git switch -c <usuario>/orden-N`.
   Relevo: `git fetch` y `git switch` a la rama que dice la nota.
4. **Ejecutar solo lo que pide la orden**, y nada de lo que dice "no tocar". Lo que aparezca
   fuera de alcance se anota en la issue para una orden nueva.
5. **Comprobar** con el comando del criterio de aceptación y con su control, y leer la salida.
   Si no cuadra, no se devuelve: se corrige o se explica en la issue.
6. **Enseñar el diff y la salida** a la persona, y esperar a que los lea.
7. **Devolver**: añadir los archivos por nombre (nunca `git add -A` ni `git add .`), commit,
   `git push -u origin HEAD` y `gh pr create` con la plantilla del PR, que pide la salida
   literal del criterio y el uso de IA. La descripción lleva `Closes #N`, con el número de la
   issue y en inglés. Después, `gh issue edit N --remove-label en-curso --add-label en-revision`.

Si la ventana de uso se acaba a mitad, en lugar de los pasos 6 y 7 va `/relevo`.
