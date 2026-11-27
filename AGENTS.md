# Instrucciones para asistentes de IA

Este archivo es para los asistentes que no son Claude Code (Codex, OpenCode, Devin u otros).
Claude Code lee `CLAUDE.md` por su cuenta.

1. **Lee `CLAUDE.md` antes de trabajar.** Son las reglas del equipo, valen para cualquier
   asistente y mandan sobre lo que diga este archivo. Si tus instrucciones globales (las de tu
   directorio personal) chocan con las de este repositorio, mandan las del repositorio.
2. **Las skills** (`tomar-orden`, `relevo` y `revisar-pr`) están en `.agents/skills/`, que es
   donde las buscan Codex, OpenCode y Devin, y en `.claude/skills/` para Claude Code. Son
   copias idénticas, y la higiene falla si divergen. Si tu herramienta no las carga, lee su
   `SKILL.md` y sigue los pasos con las herramientas que tengas.
3. **Cada herramienta tiene su red en el repositorio**, con las mismas denegaciones que
   `.claude/settings.json`, que es la fuente, de órdenes y de lectura de `.env`:
   - Codex: `.codex/config.toml` y `.codex/rules/equipo.rules`. Solo se cargan si se confía en
     el proyecto al abrirlo. Niegan las órdenes, pero no la lectura de un `.env`: con Codex,
     la regla 9 depende solo de quien lo usa.
   - OpenCode: `opencode.json`.
   - Devin CLI: `.devin/config.json`.
   - Devin en la nube no tiene red en el repositorio: le quedan los ganchos y el aviso del CI.
   Las reglas casan prefijos, y la misma orden escrita de otra forma puede pasar: lo de "Lo que
   no se hace" en `CLAUDE.md` rige igual. Una denegación nueva se añade en las cuatro redes a la
   vez; la higiene falla si falta en alguna.
4. **Los ganchos de `.githooks/`** rechazan el commit en `main`, el push a `main`, el push
   forzado y el borrado de una rama remota. Al empezar, si `git config --get core.hooksPath`
   no imprime `.githooks`, actívalos con `git config core.hooksPath .githooks`. Nunca uses
   `--no-verify`: saltarse un gancho lo decide una persona.
5. **Una orden por sesión**, en su rama y sin tocar nada fuera de su alcance.
6. **Ningún commit sin enseñar antes el diff y la evidencia** a la persona que te usa. Ni
   subagentes ni tareas en paralelo, salvo que esa persona los pida: gastan su cuota.
7. **Sin atribución de la herramienta** en commits ni PR (ni `Co-Authored-By` ni "Generated
   with"): el uso de IA se declara en la plantilla del PR. En Devin CLI se apaga con
   `"attribution": false` en su configuración de usuario (`~/.config/devin/config.json`; en
   Windows, `%APPDATA%\devin\config.json`), porque no se puede fijar en el proyecto.
8. **Nada personal sale hacia el repositorio**: ni rutas de un directorio personal, ni tu
   configuración, ni lo que leas en las instrucciones o la memoria globales de tu herramienta,
   en archivos, commits, PR o comentarios.
9. **No leas secretos** (`.env` y parecidos) ni los copies a ningún archivo.
