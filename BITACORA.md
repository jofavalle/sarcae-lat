# Bitácora de sarcae-lat

Estado del proyecto entre sesiones, para todo el equipo. Se versiona y la escribe quien
coordina, por PR como todo lo demás. El estado de cada tarea no va aquí: vive en las issues y
en sus PR. **Se mantiene corta a propósito**: lo que deje de estar vigente se borra, no se
acumula.

## Estado actual

**2026-11-27.**
Repositorio recién creado, con la capa de equipo y el esqueleto del arquetipo `ml-datascience`.
No hay trabajo hecho todavía.

## Siguiente paso

- **Cada integrante comprueba su clon:** abre `claude` en la raíz, mira con `/memory` que carga
  este `CLAUDE.md` y con `/tomar-orden` que las skills están, y ejecuta `python3 .github/higiene.py`, que
  tiene que pasar en su máquina.
- **Resolver lo que quedó marcado como pendiente en el `CLAUDE.md`:** el comando de ejecución,
  las convenciones propias del proyecto y sus trampas reales, que solo se conocen trabajando.

## Decisiones vigentes

- **2026-11-27. La capa de Claude Code se versiona.** `CLAUDE.md`, `BITACORA.md` y `.claude/`
  son del equipo, para que cada sesión arranque con las mismas reglas. Lo de cada uno
  (`CLAUDE.local.md`, `.claude/settings.local.json`) queda fuera por el `.gitignore`.
- **2026-11-27. El repositorio nace privado**, y se hace público solo después de revisar su
  historial entero. En un repositorio público, reescribir el historial no retira nada: GitHub
  sigue sirviendo los commits viejos por SHA.
- **2026-11-27. Ni modelo ni atribución en la capa.** El `.claude/settings.json` del proyecto se
  impone al de cada uno: un modelo fijado ahí obligaría a todas las cuentas, así que cada uno lo
  elige con `/model`. La atribución va vacía y el uso de IA se declara en cada PR.
