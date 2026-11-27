---
name: Orden de trabajo
about: Una tarea que se puede ejecutar sin preguntarle nada a quien la escribió
title: "Orden: verbo y resultado"
labels: orden, lista
---

**Objetivo.** Una frase con un verbo y un resultado que se pueda comprobar.

**Tamaño.** S (cabe en media ventana de uso) o M (dos etapas, con punto de relevo).

**Leer antes.** Las rutas que hacen falta, y ninguna más.

**No tocar.** Lo que queda fuera: archivos, carpetas y dependencias. Dos órdenes en curso no
editan el mismo archivo.

**Restricciones.** Versiones y bibliotecas permitidas, dónde va la salida, rutas relativas.

**Criterio de aceptación.**
- Comando:
- Debe imprimir:
- Control independiente: una comprobación que no repita el cálculo y que fallaría si la regla
  se aplicara mal.

**Punto de relevo** (solo en M). Qué queda hecho al terminar la etapa 1, y con qué mensaje de
commit se marca.

**Frase de arranque.** Para pegar en Claude Code, abierto en la raíz del clon, cambiando N por
el número de esta issue:

> Toma la orden #N con /tomar-orden y resuélvela siguiendo sus restricciones. Al terminar,
> ejecuta el comando del criterio de aceptación, enséñame su salida literal y el diff, y espera
> a que lo lea antes del commit.
