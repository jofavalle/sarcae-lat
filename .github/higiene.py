#!/usr/bin/env python3
"""Higiene del repositorio: lo que no debe entrar en un repositorio de equipo.

Se ejecuta antes de abrir un PR y corre en CI en cada push. Sale con 1 si algo falla,
y dice el archivo y, cuando se puede, la línea. Solo usa la biblioteca estándar, y
necesita git.

Sobre los archivos versionados comprueba:

1. que no haya enlaces simbólicos: en el clon de otra persona están rotos, y Git para
   Windows los saca como archivos de texto que contienen la ruta;
2. que no haya archivos de cada uno: CLAUDE.local.md, .env (.env.example sí), y lo
   que Claude Code guarda dentro de .claude/ para una sola persona (la configuración
   local, la memoria local de sus agentes, sus worktrees y su estado de ejecución);
3. que ningún archivo lleve la ruta de un directorio personal (Linux, macOS, Windows,
   la carpeta de la WSL vista desde Windows), tampoco con las barras escapadas de un
   JSON, dentro de un binario ni en un texto en UTF-16. Lo comprimido no se abre;
4. que los textos estén en UTF-8: la Windows PowerShell que trae el sistema guarda
   con '>' en UTF-16, que en un diff no se lee;
5. que la capa del equipo exista: CLAUDE.md, .claude/settings.json y la red de cada
   herramienta (opencode.json, .codex/config.toml, .codex/rules/ y .devin/config.json).

Y sobre el árbol de trabajo:

6. que las skills de .agents/skills/ (las que leen Codex, OpenCode y Devin) sean idénticas,
   en las dos direcciones, a las de .claude/skills/ (las que lee Claude Code). Van copiadas
   porque no se admiten enlaces, y una copia que diverge da reglas distintas a cada agente;
7. que cada denegación de .claude/settings.json, que es la fuente, esté repetida en la red
   de las otras tres herramientas: en opencode.json como regla de shell "deny" sin ninguna
   regla de shell que no niegue detrás (gana la última que casa), en .codex/rules/ como
   prefix_rule "forbidden" y en .devin/config.json como Exec(...) en deny. Y cada lectura
   negada, Read(...), en opencode.json como regla de lectura "deny" sin ninguna regla de
   lectura que no niegue detrás, y en .devin/config.json como Read(...) en deny. A Codex no
   se le exige: desde el proyecto solo puede negar lecturas con un perfil de permisos que
   exige una ruta absoluta de lectura, distinta en cada sistema.

Fuera del CI avisa, sin fallar, si este clon no tiene activos los ganchos de .githooks/.

Uso:  python3 .github/higiene.py      (en Windows: py .github/higiene.py)
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# El comienzo de la ruta de un directorio personal: la carpeta de los usuarios y la
# primera letra del nombre, sin exigir barra final ni mirar cómo sigue (un nombre de
# Windows puede llevar espacios o tildes). La letra excluye los marcadores de los
# ejemplos, como '$' o '<', y la búsqueda hacia atrás excluye una URL cuyo camino
# pase por una carpeta con ese nombre. La ruta de Windows no la lleva: una letra de
# unidad seguida de la carpeta de usuarios ya es inconfundible, y al quitar los nulos
# de un binario la letra puede quedar pegada a lo que la precedía. Cada nombre de
# carpeta va escrito con una clase de caracteres en medio, para que este archivo no
# case consigo mismo.
LETRA = rb"[A-Za-z0-9_\x80-\xff]"
HOGARES = re.compile(
    rb"(?<![\w.-])\\?/h[o]me\\?/" + LETRA
    + rb"|(?<![\w.-])\\?/U[s]ers\\?/" + LETRA
    + rb"|/mnt/[a-z]/U[s]ers/" + LETRA
    + rb"|(?i:[a-z]:[\\/]+u[s]ers[\\/]+)" + LETRA
    + rb"|(?i:\\\\wsl(?:\.localhost|\$)\\[^\\\r\n]+\\h[o]me\\)" + LETRA
)

TEXTO = {
    ".md", ".txt", ".py", ".ipynb", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    ".json", ".html", ".htm", ".css", ".yml", ".yaml", ".toml", ".csv", ".tsv",
    ".sh", ".ps1", ".sql", ".r", ".tex", ".bib", ".svg", ".xml", ".ini", ".cfg", ".rules",
}
TEXTO_POR_NOMBRE = {".gitignore", ".gitattributes", ".env.example", "LICENSE", "README",
                    "pre-commit", "pre-push"}

# Lo que Claude Code guarda dentro de una carpeta .claude/ para una sola persona. Es
# la misma lista que el .gitignore del repositorio.
LOCALES_CLAUDE = {
    "settings.local.json", "agent-memory-local", "worktrees", "checkpoints", "mailbox",
    "scheduled_tasks.lock", "scheduled_tasks.json", "agent-registry.json", "first-run",
    "assistant-daemon-state.json",
}

CAPA = ("CLAUDE.md", ".claude/settings.json", "opencode.json", ".codex/config.toml",
        ".codex/rules/equipo.rules", ".devin/config.json")

# Lo de cada uno en las otras herramientas, además de AGENTS.local.md (las reglas
# personales que lee Devin): su configuración local. Como en el .gitignore.
LOCALES_OTRAS = {".devin/config.local.json"}


def git(*args):
    return subprocess.run(
        ["git", *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ).stdout


def versionados():
    """(modo, ruta) de cada entrada del índice."""
    salida = git("ls-files", "-s", "-z")
    for entrada in salida.split(b"\0"):
        if not entrada:
            continue
        cabecera, ruta = entrada.split(b"\t", 1)
        yield cabecera.split(b" ")[0].decode(), ruta.decode("utf-8", "surrogateescape")


def es_de_cada_uno(ruta):
    partes = ruta.split("/")
    nombre = partes[-1]
    if nombre == "CLAUDE.local.md" or nombre == "AGENTS.local.md":
        return True
    if "/".join(partes[-2:]) in LOCALES_OTRAS:
        return True
    if nombre == ".env" or (nombre.startswith(".env.") and nombre != ".env.example"):
        return True
    for i, parte in enumerate(partes[:-1]):
        if parte != ".claude":
            continue
        siguiente = partes[i + 1]
        if siguiente in LOCALES_CLAUDE:
            return True
        if siguiente == "routines" and len(partes) > i + 2 and partes[i + 2] == ".state":
            return True
    return False


def es_texto(ruta):
    nombre = ruta.rsplit("/", 1)[-1]
    return Path(nombre).suffix.lower() in TEXTO or nombre in TEXTO_POR_NOMBRE


def lecturas(datos):
    """Los bytes tal cual y, si llevan bytes nulos, también sin ellos.

    Quitar los nulos convierte el texto en UTF-16 (con o sin marca, en cualquier
    desplazamiento y aunque haya un carácter suelto que no se pueda decodificar) en
    algo que la expresión de arriba sí ve.
    """
    yield datos
    if b"\0" in datos:
        yield datos.replace(b"\0", b"")


def lineas_con_ruta(datos):
    vistas = set()
    for lectura in lecturas(datos):
        for coincidencia in HOGARES.finditer(lectura):
            vistas.add(lectura.count(b"\n", 0, coincidencia.start()) + 1)
    return sorted(vistas)


def comprobar_skills(raiz):
    agentes, claude = Path(raiz, ".agents", "skills"), Path(raiz, ".claude", "skills")
    if not claude.is_dir():
        return []
    if not agentes.is_dir():
        return [".agents/skills/: falta la copia de .claude/skills/ que leen Codex, OpenCode y Devin"]

    def contenido(base):
        return {p.relative_to(base).as_posix(): p.read_bytes() for p in base.rglob("*") if p.is_file()}

    a, c = contenido(agentes), contenido(claude)
    problemas = []
    for rel in sorted(set(a) | set(c)):
        if rel not in c:
            problemas.append(f".agents/skills/{rel}: falta su copia en .claude/skills/")
        elif rel not in a:
            problemas.append(f".claude/skills/{rel}: falta su copia en .agents/skills/")
        elif a[rel] != c[rel]:
            problemas.append(f"skills/{rel}: distinta en .agents y en .claude")
    return problemas


def leer_json(raiz, rel, problemas):
    try:
        return json.loads(Path(raiz, rel).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        problemas.append(f"{rel}: no se puede leer como JSON ({error})")
        return None


def denegaciones_fuente(ajustes):
    """Los prefijos de las denegaciones Bash(...) de .claude/settings.json.

    Solo las que empiezan por una orden: un patrón con comodín, como Bash(*carpeta/*), no
    tiene equivalente en las reglas de prefijo de Codex y de Devin, y no se les exige.
    """
    salida = []
    for entrada in ajustes.get("permissions", {}).get("deny", []):
        m = re.fullmatch(r"Bash\((.+?)(?::\*)?\)", entrada)
        if m and "*" not in m.group(1):
            salida.append(m.group(1))
    return salida


def lecturas_fuente(ajustes):
    """Los patrones de las lecturas negadas, Read(...), de .claude/settings.json, sin el ./"""
    salida = []
    for entrada in ajustes.get("permissions", {}).get("deny", []):
        m = re.fullmatch(r"Read\((.+)\)", entrada)
        if m:
            patron = m.group(1)
            salida.append(patron[2:] if patron.startswith("./") else patron)
    return salida


def reglas_codex(raiz):
    """(patrón, decisión) de cada prefix_rule de .codex/rules/*.rules, sin comentarios."""
    reglas = []
    for archivo in sorted(Path(raiz, ".codex", "rules").glob("*.rules")):
        texto = re.sub(r"#[^\n]*", "", archivo.read_text(encoding="utf-8"))
        for llamada in re.findall(r"prefix_rule\((.*?)\)\s*$", texto, re.S | re.M):
            patron = re.search(r"pattern\s*=\s*\[(.*?)\]", llamada, re.S)
            decision = re.search(r'decision\s*=\s*"(\w+)"', llamada)
            if patron and decision:
                reglas.append((re.findall(r'"((?:[^"\\]|\\.)*)"', patron.group(1)), decision.group(1)))
    return reglas


def comprobar_redes(raiz):
    problemas = []
    ajustes = leer_json(raiz, ".claude/settings.json", problemas)
    opencode = leer_json(raiz, "opencode.json", problemas)
    devin = leer_json(raiz, ".devin/config.json", problemas)
    if ajustes is None:
        return problemas
    fuente = denegaciones_fuente(ajustes)
    lecturas = lecturas_fuente(ajustes)

    if opencode is not None:
        # OpenCode casa con * cualquier ruta, así que ./**/.env se escribe *.env.
        de_lectura = [(i, r) for i, r in enumerate(opencode.get("permissions", []))
                      if r.get("action") in ("read", "*")]
        ultima_lectura_que_no_niega = max((i for i, r in de_lectura if r.get("effect") != "deny"),
                                          default=-1)
        for patron in lecturas:
            recurso = "*" + patron.rsplit("/", 1)[-1]
            posiciones = [i for i, r in de_lectura
                          if r.get("resource") == recurso and r.get("effect") == "deny"]
            if not posiciones:
                problemas.append(f"opencode.json: falta la lectura negada de '{patron}' "
                                 f'(read, "{recurso}", deny)')
            elif max(posiciones) < ultima_lectura_que_no_niega:
                problemas.append(f"opencode.json: la lectura negada de '{patron}' va antes de una regla "
                                 "de lectura que no niega, y gana la última que casa")

    if opencode is not None:
        reglas = opencode.get("permissions", [])
        de_shell = [(i, r) for i, r in enumerate(reglas) if r.get("action") in ("shell", "*")]
        if not any(r.get("action") == "shell" and r.get("resource") == "*" and r.get("effect") == "ask"
                   for _, r in de_shell):
            problemas.append('opencode.json: falta la regla base {"action": "shell", "resource": "*", '
                             '"effect": "ask"}; sin ella, OpenCode lo ejecuta todo sin preguntar')
        ultima_que_no_niega = max((i for i, r in de_shell if r.get("effect") != "deny"), default=-1)
        for prefijo in fuente:
            posiciones = [i for i, r in de_shell
                          if r.get("resource") == prefijo + " *" and r.get("effect") == "deny"]
            if not posiciones:
                problemas.append(f"opencode.json: falta la denegación de '{prefijo}' "
                                 f'(shell, "{prefijo} *", deny)')
            elif max(posiciones) < ultima_que_no_niega:
                problemas.append(f"opencode.json: la denegación de '{prefijo}' va antes de una regla de "
                                 "shell que no niega, y gana la última que casa: ponla al final")

    negadas_codex = {tuple(p) for p, d in reglas_codex(raiz) if d == "forbidden"}
    for prefijo in fuente:
        if tuple(prefijo.split()) not in negadas_codex:
            problemas.append(f".codex/rules/: falta prefix_rule(pattern = {json.dumps(prefijo.split())}, "
                             'decision = "forbidden")')

    if devin is not None:
        negadas_devin = set(devin.get("permissions", {}).get("deny", []))
        for prefijo in fuente:
            if f"Exec({prefijo})" not in negadas_devin:
                problemas.append(f'.devin/config.json: falta "Exec({prefijo})" en permissions.deny')
        for patron in lecturas:
            if f"Read({patron})" not in negadas_devin:
                problemas.append(f'.devin/config.json: falta "Read({patron})" en permissions.deny')
    return problemas


def aviso_ganchos(raiz):
    if os.environ.get("CI") or not Path(raiz, ".githooks").is_dir():
        return
    r = subprocess.run(["git", "config", "--get", "core.hooksPath"], stdout=subprocess.PIPE,
                       stderr=subprocess.DEVNULL, text=True)
    if r.stdout.strip() != ".githooks":
        print("aviso: los ganchos de .githooks/ no están activos en este clon; actívalos una vez "
              "con: git config core.hooksPath .githooks")


def main():
    raiz = git("rev-parse", "--show-toplevel").decode().strip()
    problemas = []
    rutas = []

    for modo, ruta in versionados():
        rutas.append(ruta)
        if modo == "120000":
            problemas.append(f"{ruta}: enlace simbólico versionado (en otro clon está roto)")
            continue
        if es_de_cada_uno(ruta):
            problemas.append(f"{ruta}: es de cada uno y no se versiona (git rm --cached)")
        archivo = Path(raiz, ruta)
        if not archivo.is_file():
            continue
        datos = archivo.read_bytes()

        for linea in lineas_con_ruta(datos):
            if es_texto(ruta):
                problemas.append(f"{ruta}:{linea}: ruta de un directorio personal (usa rutas relativas)")
            else:
                problemas.append(f"{ruta}: ruta de un directorio personal dentro de un binario")
                break

        if es_texto(ruta):
            if datos.startswith((b"\xff\xfe", b"\xfe\xff")):
                problemas.append(f"{ruta}: texto en UTF-16 (guárdalo en UTF-8; en Windows, desde PowerShell 7)")
            elif b"\0" in datos:
                problemas.append(f"{ruta}: texto con bytes nulos, probablemente UTF-16 sin marca (guárdalo en UTF-8)")
            else:
                try:
                    datos.decode("utf-8")
                except UnicodeDecodeError as error:
                    problemas.append(f"{ruta}: no está en UTF-8 (byte {error.start})")

    for ruta in CAPA:
        if ruta not in rutas:
            problemas.append(f"{ruta}: falta la capa del equipo")

    problemas += comprobar_skills(raiz)
    problemas += comprobar_redes(raiz)
    aviso_ganchos(raiz)

    for problema in problemas:
        print(problema)
    if problemas:
        print(f"\nhigiene: {len(problemas)} problemas en {len(rutas)} archivos versionados")
        return 1
    print(f"higiene en orden: {len(rutas)} archivos versionados")
    return 0


if __name__ == "__main__":
    sys.exit(main())
