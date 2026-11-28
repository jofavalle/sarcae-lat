export const fichaPrueba = {
  etiqueta: "Ficha ficticia. Las cifras de ejemplo no son mediciones de una escuela.",
  pais: "Venezuela",
  calor: {
    indicador: "temperatura media del aire en horario de clase",
    cambioDeEjemplo: "+0,8 °C al comparar el periodo de 1996 a 2025 con el de 1966 a 1995",
    fuente: "ERA5",
  },
  lluvia: {
    fuentes: ["ERA5", "CHIRPS"],
    detalle: "CHIRPS combina observaciones satelitales y datos de estaciones.",
  },
  era5: {
    alcance: "Describe el clima de la zona desde 1940, sin medir en la escuela.",
    metodo: "Es un reanálisis. Su celda mide unos 28 km y el valor representa la celda completa.",
  },
  mapa: {
    calor: "La capa muestra la temperatura de la superficie de techos y suelos cuando pasa el satélite, distinta de la temperatura del aire.",
    agua: "La acumulación de flujo sobre el modelo de elevación muestra por dónde tiende a correr el agua según el relieve.",
  },
  maqueta: {
    detalle: "Solo muestra volúmenes por la seguridad de quienes ocupan la escuela. Las alturas son estimaciones y en esta ficha el error medio de ejemplo es de 1,5 m.",
    recorrido: "Usa el botón Siguiente para avanzar de parada. Cada parada tiene texto disponible también en el mapa y en la ficha.",
  },
  criterios: "Los criterios del Manual de Diseño Mi Nueva Escuela son de El Salvador. En Colombia y Venezuela se usan criterios generales mientras se buscan los equivalentes locales.",
  preguntasParaConversar: [
    "¿Dónde hay sombra en los espacios usados durante las horas de clase?",
    "¿En qué momentos se siente menos circulación de aire en el aula?",
    "¿Dónde se acumulan hojas en las canaletas y dónde se encharca el patio?",
  ],
};
