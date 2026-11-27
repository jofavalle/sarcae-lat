---
name: relevo
description: Deja una orden a medias lista para que otra persona la continúe sin preguntar nada. Úsala cuando se acabe la ventana de uso, alguien tenga que irse o diga "relevo", "lo dejo aquí" o "que lo siga otro".
---

# Relevo de una orden a medias

La prueba de un buen relevo es que quien lo toma no tenga que preguntarle nada a quien lo dejó.

1. **Guardar lo hecho**, aunque esté incompleto: añadir los archivos por nombre, commit con un
   mensaje que lo diga ("Orden #N: etapa 1; falta la 2") y `git push -u origin HEAD`.
2. **La nota de relevo**, como comentario en la issue (`gh issue comment N`), con:
   - el nombre de la rama;
   - qué está hecho y qué falta;
   - el último comando que se ejecutó y su salida;
   - lo que se decidió por el camino y la orden no recoge.
3. **Soltar la orden**:
   `gh issue edit N --remove-assignee "@me" --remove-label en-curso --add-label lista`.

Quien la retome usa `/tomar-orden`, y en su paso 3 trae esta rama en vez de crear una.
