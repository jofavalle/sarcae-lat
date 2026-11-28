# ADR-002. Proveedor del asistente

- **Fecha:** 2026-11-28, hora de El Salvador.
- **Estado:** prueba técnica completada. Proveedor pendiente de decisión para el público escolar.

## Contexto

La decisión [#18](https://github.com/jofavalle/sarcae-lat/issues/18) eligió probar Mistral Small 3.1
en Workers AI. La [orden #38](https://github.com/jofavalle/sarcae-lat/issues/38) comprueba la conexión,
la calidad con la batería escolar, el consumo y las condiciones de uso. El catálogo de Cloudflare
identifica el modelo como `@cf/mistralai/mistral-small-3.1-24b-instruct`. Mistral publica
Mistral Small 3.1 24B Instruct 2503 bajo Apache 2.0. Fuentes consultadas el 2026-11-27.
[Catálogo de Workers AI](https://developers.cloudflare.com/workers-ai/models/mistral-small-3.1-24b-instruct/)
· [Ficha publicada por Mistral](https://huggingface.co/mistralai/Mistral-Small-3.1-24B-Instruct-2503)
· [Texto de Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0).

## Contenido que procesa el proveedor

La Function envía las instrucciones fijas, la ficha ficticia con el registro indicado y la pregunta.
El contador D1 solo guarda el día UTC y el número total de llamadas reservadas. El flujo usa
inferencia sin estado y marca las respuestas HTTP para que no se almacenen en caché.

- Workers AI declara «Cloudflare does not use Customer Content processed by Workers AI to train AI
  models.» Las entradas y salidas de la inferencia sin estado se conservan el tiempo necesario para
  responder, con excepciones de seguridad y obligaciones legales. Cloudflare también puede conservar
  metadatos operativos. Consulta del 2026-11-27. [Uso de datos de Workers AI](https://developers.cloudflare.com/workers-ai/platform/data-usage/).
- El apartado 9 de las condiciones de Developer Platform contempla usar el contenido «as needed to
  provide and improve the Services». Ese permiso para operar y mejorar el servicio se lee junto con
  el compromiso de Workers AI sobre entrenamiento. Consulta del 2026-11-27. [Condiciones de Developer Platform](https://www.cloudflare.com/service-specific-terms-developer-platform/).

## Edad del público

- Cloudflare declara «Cloudflare’s Websites and Services are not intended for, nor designed to
  attract, individuals under the age of eighteen.» En la misma sección distingue sus servicios de los
  sitios y aplicaciones de clientes y hace a los clientes responsables de sus políticas con el
  público final. El asistente usa el sitio de un cliente y, a la vez, envía texto de escolares a
  Workers AI. Ese texto deja abierto cómo aplica la cláusula a la inferencia en este caso. Las
  condiciones públicas de Developer Platform y la página de Workers AI no documentan una excepción
  para esta integración. Consulta del 2026-11-27. [Política de privacidad de Cloudflare, sección 1](https://www.cloudflare.com/privacypolicy/)
  · [Condiciones de Developer Platform](https://www.cloudflare.com/service-specific-terms-developer-platform/)
  · [Uso de datos de Workers AI](https://developers.cloudflare.com/workers-ai/platform/data-usage/).
- Los términos de Mistral para consumidores fuera del EEE dicen «You must be at least thirteen (13)
  years old to use the Mistral AI Products.» También contemplan permiso parental para menores cuando
  corresponda. La política de uso de Mistral excluye despliegues en infraestructura de clientes o
  socios y «our open-source AI models and products.» La ficha de este modelo declara Apache 2.0 y
  esa licencia carece de cláusula de edad. Consulta del 2026-11-27. [Términos de Mistral](https://legal.mistral.ai/terms/row-consumer-terms/)
  · [Política de uso de Mistral](https://legal.mistral.ai/terms/usage-policy/?lang=en)
  · [Clasificación del modelo por Mistral](https://legal.mistral.ai/ai-governance/models/mistral-small-3/).
- Para los productos que Mistral proporciona a través de socios, su sección 2.2(c) restringe el
  envío de datos personales de menores de 13 años o de la edad aplicable de consentimiento digital.
  También restringe «allow minors to use the Mistral AI Products without consent from their parent
  or guardian». El catálogo identifica una versión abierta alojada por Cloudflare. Las fuentes
  públicas consultadas dejan sin confirmar si estos términos para socios rigen ese despliegue.
  Consulta del 2026-11-27. [Términos de despliegue mediante socios de Mistral](https://legal.mistral.ai/terms/partner-served-deployment-terms/)
  · [Catálogo de Workers AI](https://developers.cloudflare.com/workers-ai/models/mistral-small-3.1-24b-instruct/).

## Prueba y consumo

La Function reserva una de 60 consultas diarias antes de llamar a Workers AI. La operación D1 es
atómica y el cupo se reinicia a medianoche UTC. La vista previa tiene los dos bindings. Para
aprovisionar la base de prueba, aplica `functions/asistente/cupo.sql` una vez desde D1 o con
`wrangler d1 execute sarcae-lat-asistente-prueba --remote --file functions/asistente/cupo.sql`.

La [vista previa desplegada](https://5a12846c.sarcae-lat.pages.dev) contestó las 24 preguntas.
Cumplió todos los criterios en 16. Los [resultados](../asistente/resultados-20261128.md) conservan
las respuestas y el veredicto de cada criterio. Para el control independiente, elige dos preguntas
al azar, copia sus textos y registros a una petición con este formato y coteja las respuestas
con la tabla y sus criterios.

```sh
curl -fsS https://5a12846c.sarcae-lat.pages.dev/api/asistente \
  -H 'Content-Type: application/json' \
  --data '{"pregunta":"¿de dónde sacaron los datos de la lluvia?","registro":"estudiante"}'
```

Cloudflare publica 10.000 neuronas gratuitas al día por cuenta, 31.876 por millón de tokens de
entrada y 50.488 por millón de salida para este modelo. La pregunta 3 obtuvo HTTP 200 y Workers AI
registró 821 tokens de entrada y 87 de salida. El consumo equivalente calculado con esos valores,
`(821 × 31.876 + 87 × 50.488) / 1.000.000`, es de 30,56 neuronas, el 0,306 % de la cuota diaria.
Las demás consultas de la cuenta también consumen esa cuota. Tarifas consultadas el 2026-11-27.
[Tarifas de Workers AI](https://developers.cloudflare.com/workers-ai/platform/pricing/).

## Consecuencias

La llamada desde Pages funciona. La calidad observada falla en ocho preguntas, incluida una de
emergencia. La aplicabilidad de las condiciones de edad también sigue pendiente. La configuración
de producción deja deshabilitada la inferencia. El equipo puede pedir a Cloudflare una aclaración
escrita y volver a evaluar la calidad, probar otro proveedor según la #18 o usar solo las respuestas
de reserva.
