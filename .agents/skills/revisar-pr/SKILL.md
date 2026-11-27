---
name: revisar-pr
description: Revisa el PR de una orden antes de fusionarlo, contra la orden y su criterio de aceptación. Úsala cuando haya que revisar, aprobar o fusionar un PR, o mirar la cola de revisión.
---

# Revisar un PR

Lo mecánico ya lo comprobó quien ejecutó la orden; quien revisa se queda con lo que exige juicio.

1. **La cola**: `gh pr list`. Con tres o más esperando, se revisa antes de publicar órdenes
   nuevas.
2. **Contra la orden**: `gh pr view N` y la issue que cierra. ¿Hace lo que pide, y nada de lo
   que dice "no tocar"?
3. **La evidencia**: la salida del criterio de aceptación tiene que estar en el PR, literal. Si
   hay dudas, se repite el comando en su rama (`gh pr checkout N`) y se compara.
4. **El diff entero**: `gh pr diff N`. Sobre todo lo que exige juicio: cifras, unidades, lo que
   dice el modelo. Y que no entren claves, rutas personales ni archivos de cada uno. Los checks
   de CI, en verde: `gh pr checks N`.
5. **Decidir**: fusionar si todo cuadra, o comentar en el PR qué falta, de forma concreta, para
   que se corrija en la misma rama.
