# Stage Checks

Scripts para ejecutar y validar el pipeline por etapas, de forma incremental.

## Uso

Cada script ejecuta desde la Stage 1 hasta la stage indicada, para respetar dependencias:

- `python stage_checks/run_stage1_check.py`
- `python stage_checks/run_stage2_check.py`
- `python stage_checks/run_stage3_check.py`
- `python stage_checks/run_stage4_check.py`
- `python stage_checks/run_stage5_check.py`
- `python stage_checks/run_stage6_check.py`
- `python stage_checks/run_stage7_check.py`
- `python stage_checks/run_stage8_check.py`

Por defecto limpian `results/` antes de arrancar. Si quieres reutilizar salidas previas:

- `python stage_checks/run_stage6_check.py --no-clean`

## Qué validan

Cada script:

1. ejecuta las stages necesarias hasta la indicada
2. comprueba que existan artefactos clave de salida
3. imprime un pequeño resumen con rutas y estado

## Cuándo usarlos

- para localizar en qué stage aparece un error
- para aislar problemas de XFOIL, compresibilidad, tablas o figuras
- para depurar cambios sin lanzar siempre el pipeline completo
