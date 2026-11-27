#!/usr/bin/env python3
"""Pruebas de los ganchos de .githooks/: cada caso intenta algo contra un remoto desnudo en un
directorio temporal y comprueba que el gancho lo rechaza, o lo deja pasar si es lo normal. Al
final se mira el remoto, que es la comprobación independiente: si un gancho dejara pasar algo
sin decirlo, el remoto habría cambiado. Nunca toca el repositorio ni GitHub.

Uso: python3 tests/prueba_ganchos.py   (en Windows, py tests/prueba_ganchos.py; necesita el
sh que trae Git for Windows, que es con el que git ejecuta los ganchos)
Sale con 0 si todos los casos dan lo esperado.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
GANCHOS = RAIZ / ".githooks"
IDENTIDAD = ["-c", "user.name=prueba", "-c", "user.email=prueba@example.invalid",
             "-c", "commit.gpgsign=false"]


def git(cwd, *args):
    r = subprocess.run(["git", *IDENTIDAD, *args], cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def remoto_de(remoto, ref):
    rc, salida = git(remoto, "rev-parse", "--verify", "-q", ref)
    return salida.strip() if rc == 0 else None


def main():
    fallos = 0
    total = 0

    def caso(nombre, rc, salida, debe_pasar, texto=None):
        nonlocal fallos, total
        total += 1
        bien = (rc == 0) == debe_pasar and (texto is None or texto in salida)
        esperado = "pasa" if debe_pasar else "rechazado"
        print("{}  {} (salida {}, se espera: {})".format("ok   " if bien else "FALLA", nombre, rc, esperado))
        if not bien:
            fallos += 1
            print("       " + salida.strip().replace("\n", "\n       "))

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        remoto, clon = tmp / "remoto.git", tmp / "clon"
        git(tmp, "init", "-q", "--bare", "-b", "main", str(remoto))
        git(tmp, "clone", "-q", str(remoto), str(clon))
        # El primer commit y su push van antes de activar los ganchos: son el punto de partida.
        git(clon, "switch", "-q", "-c", "main")
        git(clon, "commit", "-q", "--allow-empty", "-m", "base")
        git(clon, "push", "-q", "origin", "main")
        main_inicial = remoto_de(remoto, "refs/heads/main")
        git(clon, "config", "core.hooksPath", str(GANCHOS))

        rc, s = git(clon, "commit", "--allow-empty", "-m", "en main")
        caso("commit en main", rc, s, False, "en main no se hace commit")

        git(clon, "switch", "-q", "-c", "prueba/orden-1")
        rc, s = git(clon, "commit", "--allow-empty", "-m", "en la rama")
        caso("commit en la rama de una orden", rc, s, True)
        rc, s = git(clon, "push", "origin", "prueba/orden-1")
        caso("push normal de la rama", rc, s, True)
        rama_publicada = remoto_de(remoto, "refs/heads/prueba/orden-1")

        rc, s = git(clon, "push", "origin", "prueba/orden-1:main")
        caso("push de la rama a main", rc, s, False, "a main no se empuja")

        git(clon, "commit", "-q", "--amend", "--allow-empty", "-m", "reescrito")
        rc, s = git(clon, "push", "--force", "origin", "prueba/orden-1")
        caso("push forzado de la rama", rc, s, False, "push forzado")
        rc, s = git(clon, "push", "--force-with-lease", "origin", "prueba/orden-1")
        caso("push con --force-with-lease", rc, s, False, "push forzado")

        rc, s = git(clon, "push", "origin", "--delete", "prueba/orden-1")
        caso("borrado de la rama remota", rc, s, False, "lo hace una persona")

        total += 1
        intacto = (remoto_de(remoto, "refs/heads/main") == main_inicial
                   and remoto_de(remoto, "refs/heads/prueba/orden-1") == rama_publicada)
        print("{}  el remoto sigue como lo dejó el push normal".format("ok   " if intacto else "FALLA"))
        if not intacto:
            fallos += 1

    print("\npruebas de los ganchos: {} de {} bien".format(total - fallos, total))
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
