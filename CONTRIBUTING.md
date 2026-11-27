# Cómo empezar a trabajar

Este repositorio trae versionada la configuración común de Claude Code, y se hereda al clonar:

- `CLAUDE.md`, las reglas del equipo;
- `.claude/settings.json`, los permisos y las denegaciones;
- `.claude/skills/`, los comandos `/tomar-orden`, `/relevo` y `/revisar-pr`;
- `.claude/agents/`, un revisor independiente que se usa solo cuando se pide.

`AGENTS.md` lleva las mismas reglas a otros asistentes, y cada uno trae su red con las mismas
denegaciones: `.codex/` para Codex, `opencode.json` para OpenCode y `.devin/config.json` para
Devin CLI, con las skills copiadas en `.agents/skills/`. Los ganchos de `.githooks/` valen para
todos, porque los ejecuta git. Lo de cada uno va en `CLAUDE.local.md`,
`.claude/settings.local.json`, `AGENTS.local.md` o `.devin/config.local.json`, que no se
versionan. Un cambio en lo común se propone por PR, como cualquier otro.

## Comprobación del primer día

Se hace una vez en cada máquina y lleva unos quince minutos. Cada salida se pega como comentario
en una issue titulada "Preparación verificada"; si todavía no existe, la abre quien llegue
primero. Un "ya lo tengo" sin salida no cuenta, y lo que no se comprobó aparece en plena
entrega. En Windows, todo en PowerShell 7.

1. **Clonar, activar los ganchos y pasar la higiene.** Aceptar la invitación, clonar con
   `gh repo clone` fuera de OneDrive, entrar en `sarcae-lat` y activar los ganchos con
   `git config core.hooksPath .githooks`; `git config --get core.hooksPath` tiene que imprimir
   `.githooks`. Después, `py .github/higiene.py` (fuera de Windows, `python3 .github/higiene.py`):
   tiene que salir con 0 y sin el aviso de los ganchos.
2. **Abrir `claude` dentro del clon.** La primera vez pregunta si se confía en la carpeta: sí.
   Sin esa confianza, Claude Code ignora la lista de lo permitido del proyecto y lo pregunta
   todo; las denegaciones, en cambio, valen igual.
3. **`/memory`**: tiene que aparecer el `CLAUDE.md` del proyecto.
4. **Escribir `/` y mirar la lista**: tienen que estar `/tomar-orden`, `/relevo` y
   `/revisar-pr`.
5. **`/permissions`**: tienen que aparecer las denegaciones del proyecto, por ejemplo
   `Bash(git add -A:*)`.
6. **Pedirle a Claude que ejecute `git clean -n`**: tiene que salir denegado. Si no lo
   estuviera, esa orden solo lista y no borra nada, pero se avisa en la issue. Y pedirle que
   ejecute la higiene (`py .github/higiene.py`, o `python3`): tiene que correr sin preguntar.
   Si pregunta, la carpeta no está en confianza. `git status` no sirve para esto, porque
   Claude Code lo deja correr siempre.
7. **`/status`**: la cuenta y el modelo, copiados tal cual.
8. **`git check-ignore -v .claude/settings.local.json`**: tiene que nombrar el `.gitignore`.
   Ahí va lo de cada uno, como el modelo preferido.
9. **Con otro asistente**, según cuál. Lo que se puede comprobar sin gastar cuota, así:
   - **Codex**: al abrirlo por primera vez en el clon, confiar en el proyecto; sin eso no carga
     `.codex/`. `codex debug prompt-input "hola"` tiene que contener "Instrucciones para
     asistentes de IA" (con `| grep -c` o, en PowerShell, `| Select-String -SimpleMatch`), y
     `codex execpolicy check --rules .codex/rules/equipo.rules -- git clean -n` tiene que dar
     `"decision":"forbidden"`.
   - **OpenCode**: `opencode debug agents` tiene que listar `"git clean *"` con
     `"effect": "deny"` (`| grep -c '"git clean \*"'` cuenta 7, uno por agente; en PowerShell,
     `(opencode debug agents | Select-String -SimpleMatch '"git clean *"').Count`).
   - **Devin CLI**: poner `"attribution": false` en su configuración de usuario, que no se
     puede fijar en el proyecto: `~/.config/devin/config.json` o, en Windows,
     `%APPDATA%\devin\config.json`. Si no existe, se crea con ese contenido; si existe, se añade
     la clave sin borrar las demás. Pedirle que ejecute `git clean -n`: tiene que salir
     denegado. Las skills le salen dos veces, como `/agents:<nombre>` y `/claude:<nombre>`,
     porque lee las dos copias: son la misma.
   - **Devin en la nube**: no hay red en el repositorio, solo los ganchos (si su máquina los
     activa, como pide `AGENTS.md`) y el aviso del CI. Sus PR se revisan con más cuidado.
   Con cualquiera de ellos, preguntarle qué reglas sigue en este repositorio: tiene que citar
   `AGENTS.md` y `CLAUDE.md`.

## Lo de cada uno

- **El modelo y el esfuerzo** se eligen con `/model` según la tarea, o en
  `.claude/settings.local.json`. El `settings.json` del proyecto no fija modelo a propósito: se
  impondría a la cuenta de todos.
- **Los commits no llevan atribución a la herramienta**, y el uso de IA se declara en el PR,
  como pide su plantilla.
