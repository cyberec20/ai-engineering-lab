# Playbooks

Esta carpeta reune guias practicas y marcos reutilizables para trabajo con agentes, debugging y migraciones a Docker.

## Contenido
- `01_system_prompt_playbook.md`: plantilla base para system prompts y project contexts, con secciones inmutables/mutables.
- `02_debugging_strategy.md`: estrategia de debugging multi-nivel (observabilidad externa + logging interno).
- `03_python_docker_migration_constitution.md`: reglas y checklist para migrar proyectos Python a Docker y produccion.

## Uso recomendado
- Toma el playbook de system prompt como base para nuevos proyectos.
- Aplica la estrategia de debugging cuando uses agentes o tools opacos.
- Usa la constitucion de migracion como contrato si vas a dockerizar.
