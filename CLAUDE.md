# sarcae-lat

SARCAE-LAT: sistema de aprendizaje sobre riesgos de calor y agua en escuelas latinoamericanas, con datos de ERA5, un mapa y una maqueta digital interactiva. Reto 10 de CoAfina 2026, equipo Itzpapálotl.

Esta capa (`CLAUDE.md`, `BITACORA.md` y `.claude/`) se versiona y es la misma para todo el
equipo: un cambio en ella se propone por PR, como cualquier otro. Lo de cada uno va en
`CLAUDE.local.md` o en `.claude/settings.local.json`, que no se versionan.

## Comandos

- Entorno: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
- Entrenar: <PENDIENTE: el comando de ejecucion, cuando el proyecto tenga uno (nacido 2026-11-27)>
- Verificar: `python3 .github/higiene.py`
- Higiene del repositorio: `python3 .github/higiene.py` (en Windows, `py .github/higiene.py`).
  Corre también en CI en cada push y en cada PR.
- Tablero: `gh issue list --label orden`. Cola de revisión: `gh pr list`.

**La puerta de verificación es `python3 .github/higiene.py`.**

## Convenciones

### Cómo se trabaja: órdenes, ramas y PR

- **Una orden es una issue** con la etiqueta `orden` y la plantilla de `.github/ISSUE_TEMPLATE/`.
  Tiene que bastar por sí sola: quien la ejecuta no estuvo cuando se decidió, y su sesión de
  Claude tampoco. Su estado va en etiquetas: `lista`, `en-curso` y `en-revision`.
- **Una orden se nombra por el número de su issue**, `#N`, y no por una numeración propia:
  issues y PR comparten numeración en GitHub, y una "OT-02" escrita a mano acabaría siendo la
  issue #3.
- **Una orden por sesión.** Al terminar, `/clear` o una sesión nueva. Para tomarla y devolverla
  está `/tomar-orden`; para dejarla a medias, `/relevo`; para revisar un PR, `/revisar-pr`.
- **Una rama por orden**, `<usuario>/orden-N`, desde `main` recién actualizado. A `main` no se
  escribe directamente: todo entra por PR.
- **El PR lleva evidencia** (`.github/pull_request_template.md`): el comando del criterio de
  aceptación con su salida literal, y el uso de IA. Cierra su orden con `Closes #N`, en inglés:
  GitHub no reconoce "Cierra #N", y la orden se quedaría abierta.
- **Trabajo abierto limitado:** una orden en curso por persona, y como mucho tres PR esperando
  revisión. Con la cola llena no se empieza otra orden: se prueba lo publicado.
- **Lo que se acuerda de palabra se escribe en la issue.** La sesión de Claude y quien haga un
  relevo no lo oyeron.

### Lo que no se hace

- `git add -A` ni `git add .`: los archivos se añaden por nombre, después de leer el diff.
- Commit sin que la persona haya leído el diff: por eso `git commit` pide permiso a propósito, y
  no se añade a la lista de lo permitido.
- Borrados (`rm -r`, `git reset --hard`, `git clean`, `git branch -D`) ni `git push --force`.
  Si alguno hace falta, lo ejecuta una persona. `.claude/settings.json` niega sus formas
  habituales, pero es una red y no una garantía: la misma orden escrita de otra manera puede
  pasar, y la regla vale igual.
- Claves en el código: van en `.env`, que no se versiona. Si hace falta una plantilla, se
  versiona `.env.example`, sin claves reales.
- Rutas absolutas de un directorio personal: siempre rutas relativas. La higiene las rechaza.
- Que el modelo lea datos enteros: un script los resume, y el modelo lee el resumen.

### Fuentes, licencias e IA

- Todo dato, código o texto de terceros se cita en el README, con su licencia.
- El uso de IA se declara en cada PR: qué se pidió, con qué herramienta y modelo, y qué se
  corrigió. Las órdenes y sus PR son el registro. Los commits no llevan atribución a la
  herramienta (`attribution` vacío en `.claude/settings.json`): la declaración va en el PR.

### Del proyecto

- **`data/raw/` es inmutable.** Lo que entra ahí no se edita ni se sobrescribe
  nunca; toda transformación escribe en `data/processed/`.
- Cada experimento vive en `experiments/<AAAAMMDD>-<slug>/` con su `config.yaml` y
  su `metrics.json`. Las métricas van al archivo, no al cuaderno ni a la salida.
- **La semilla se fija y se escribe en el `config.yaml`.** Un resultado sin semilla
  registrada no es reproducible y no se cita.
- La partición se hace antes de mirar los datos, y con embargo temporal si la
  variable objetivo depende del tiempo.
- Commits: mensaje en español, un cambio lógico por commit.
<PENDIENTE: las convenciones propias del proyecto que se aparten de lo estandar, cada una con su fecha y su motivo (nacido 2026-11-27)>

## Gotchas

- En Windows se trabaja en PowerShell 7, no en la Windows PowerShell que trae el sistema: esa
  guarda con `>` en UTF-16, y la higiene lo rechaza. Se instala con
  `winget install --id Microsoft.PowerShell --source winget`.
- Las reglas de `.claude/settings.json` se escriben para la herramienta Bash de Claude Code. Si en
  una máquina los comandos pasan por otra herramienta, puede que no se apliquen: lo de "Lo que no
  se hace" vale igual.
- **`data/` está en `.gitignore` entero.** Un dato intermedio guardado ahí
  desaparece del control de versiones sin avisar. La excepción prevista es
  `!data/**/.gitkeep`.
<PENDIENTE: las trampas reales del proyecto. Si al cabo del tiempo no hay ninguna, se dice que no hay y por que (nacido 2026-11-27)>
