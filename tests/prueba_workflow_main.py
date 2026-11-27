#!/usr/bin/env python3
"""Pruebas del paso del workflow "main por PR" (.github/workflows/main-por-pr.yml).

Saca del YAML el guion del paso y lo ejecuta en bash, con las mismas opciones que GitHub
Actions (-eo pipefail), sustituyendo gh por una función que responde lo que pide cada caso.
No llama a GitHub ni abre issues: la función solo imprime ISSUE_CREADA cuando el guion la
pediría.

Uso: python3 tests/prueba_workflow_main.py [ruta del workflow]
     (en Windows, py; necesita el bash de Git for Windows)
Con una ruta, prueba ese archivo en lugar del versionado: sirve de control negativo contra una
versión anterior. Sale con 0 si todos los casos dan lo esperado.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
WORKFLOW = RAIZ / ".github" / "workflows" / "main-por-pr.yml"

# gh falso. COMMITS es lo que devuelve la comparación; RESP_<commit> es la respuesta de cada
# intento sobre ese commit, separada por comas: un número es el recuento de PR fusionados y f
# es un fallo de la API. Pasado el último valor, se repite el último.
GH_FALSO = r'''
sleep() { :; }
gh() {
  if [ "$1" = api ]; then
    case "$2" in
      */compare/*)
        if [ "${FALLA_COMPARE:-0}" = 1 ]; then echo '{"message":"error"}'; return 1; fi
        for c in $COMMITS; do echo "$c"; done
        return 0 ;;
      */commits/*/pulls)
        c=${2#*/commits/}; c=${c%/pulls}
        n=$(( $(cat "intentos_$c" 2>/dev/null || echo 0) + 1 )); echo "$n" > "intentos_$c"
        var="RESP_$c"; todas="${!var}"
        resp=$(printf '%s' "$todas" | cut -d, -f"$n")
        [ -n "$resp" ] || resp=$(printf '%s' "$todas" | awk -F, '{print $NF}')
        if [ "$resp" = f ]; then echo '{"message":"error"}'; return 1; fi
        echo "$resp"
        return 0 ;;
    esac
  fi
  if [ "$1" = issue ] && [ "$2" = create ]; then echo "ISSUE_CREADA"; return 0; fi
  echo "gh inesperado: $*" >&2
  return 1
}
'''

# (nombre, entorno, salida esperada, texto que debe aparecer, texto que no debe)
CASOS = [
    ("fusión de un PR", {"COMMITS": "c1 m1", "RESP_c1": "1", "RESP_m1": "1"},
     0, "en orden", "ISSUE_CREADA"),
    ("fusión que GitHub tarda en asociar", {"COMMITS": "m1", "RESP_m1": "0,0,1"},
     0, "en orden", "ISSUE_CREADA"),
    ("commit directo", {"COMMITS": "d1", "RESP_d1": "0", "SHA": "d1"},
     1, "ISSUE_CREADA", None),
    ("un cero y después la API falla", {"COMMITS": "m1", "RESP_m1": "0,f,f,f"},
     1, "no se pudo confirmar", "ISSUE_CREADA"),
    ("commit directo debajo de una fusión", {"COMMITS": "d1 m1", "RESP_d1": "0", "RESP_m1": "1"},
     1, "ISSUE_CREADA", None),
    ("push forzado", {"FORZADO": "true"},
     1, "ISSUE_CREADA", None),
    ("la comparación falla", {"FALLA_COMPARE": "1", "RESP_m1": "1"},
     1, "no se pudo consultar", "ISSUE_CREADA"),
    ("la API nunca responde", {"COMMITS": "m1", "RESP_m1": "f"},
     1, "no se pudo confirmar", "ISSUE_CREADA"),
]


def guion_del_paso(texto):
    """Las líneas del bloque 'run: |', sin su sangría."""
    lineas = texto.splitlines()
    for i, linea in enumerate(lineas):
        if linea.strip() == "run: |":
            sangria = len(linea) - len(linea.lstrip()) + 2
            cuerpo = []
            for siguiente in lineas[i + 1:]:
                if siguiente.strip() and len(siguiente) - len(siguiente.lstrip()) < sangria:
                    break
                cuerpo.append(siguiente[sangria:])
            return "\n".join(cuerpo) + "\n"
    return None


def buscar_bash():
    encontrado = shutil.which("bash")
    if encontrado:
        return encontrado
    for candidato in (r"C:\Program Files\Git\bin\bash.exe", r"C:\Program Files (x86)\Git\bin\bash.exe"):
        if Path(candidato).is_file():
            return candidato
    return None


def main():
    ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else WORKFLOW
    guion = guion_del_paso(ruta.read_text(encoding="utf-8"))
    if not guion or 'motivo=""' not in guion:
        print("FALLA  no se encontró el paso del workflow en " + str(ruta))
        return 1
    bash = buscar_bash()
    if not bash:
        print("omitidas: no hay bash con que ejecutar el paso; no se comprobó nada")
        return 0

    fallos = 0
    with tempfile.TemporaryDirectory() as tmp:
        for i, (nombre, extra, rc_esperado, debe, no_debe) in enumerate(CASOS):
            d = Path(tmp) / "caso{:02d}".format(i)
            d.mkdir()
            (d / "paso.sh").write_text(GH_FALSO + guion, encoding="utf-8", newline="\n")
            entorno = dict(os.environ, REPO="equipo/repo", SHA="m1", ANTES="a0", FORZADO="false",
                           QUIEN="prueba", SERVIDOR="https://github.com", COMMITS="m1")
            entorno.update(extra)
            r = subprocess.run([bash, "--noprofile", "--norc", "-eo", "pipefail", "paso.sh"],
                               cwd=d, env=entorno, capture_output=True, text=True)
            salida = r.stdout + r.stderr
            bien = (r.returncode == rc_esperado and debe in salida
                    and (no_debe is None or no_debe not in salida))
            print("{}  {} (salida {}, esperada {})".format("ok   " if bien else "FALLA", nombre,
                                                         r.returncode, rc_esperado))
            if not bien:
                fallos += 1
                print("       " + salida.strip().replace("\n", "\n       "))
    print("\npruebas del workflow main por PR: {} de {} bien".format(len(CASOS) - fallos, len(CASOS)))
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
