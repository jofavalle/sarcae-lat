// Esqueleto de la primera pantalla: por ahora solo enlaza la hora del día con su lectura.
// Las cifras, la maqueta y el recorrido llegan con el contrato de datos, y la interfaz no
// recalcula lo que ya calculó Python (ADR-001).

const hora = document.getElementById("hora");
const lectura = document.getElementById("hora-grande");

function textoHora(h) {
  const hh = Math.floor(h);
  const mm = Math.round((h - hh) * 60);
  return `${hh}:${String(mm).padStart(2, "0")}`;
}

function pintar() {
  const texto = textoHora(Number(hora.value));
  lectura.textContent = texto;
  hora.setAttribute("aria-valuetext", texto);
}

hora.addEventListener("input", pintar);
pintar();
