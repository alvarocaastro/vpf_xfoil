# Instrucciones de Ejecución del Proyecto

## Comando Principal (Recomendado)

Para ejecutar el entorno integrado de análisis (10 steps estructurados en 8 stages):

```bash
python run_analysis.py
```

O desde la raíz del proyecto:

```bash
cd C:\Users\Alvaro\Desktop\tfg_vpf
.\.venv\Scripts\python run_analysis.py
```

## ¿Qué hace este comando?

1. **Limpia automáticamente** todos los resultados anteriores de `results/`
2. **Stage 1**: Selección automática de perfil óptimo
3. **Stage 2**: Ejecuta 12 simulaciones XFOIL a Mach 0.2
4. **Stage 3**: Aplica corrección de compresibilidad
5. **Stage 4**: Calcula métricas de rendimiento y genera tablas
6. **Stage 5**: Genera las figuras representativas de los resultados
7. **Stage 6**: Análisis Aerodinámico Variable Pitch Fan (VPF)
8. **Stage 7**: Análisis Cinemático (Triángulos de Velocidades)
9. **Stage 8**: Análisis de Impacto en Consumo Específico de Combustible (SFC)

## Resultados

Los resultados se generan automáticamente organizados por stage:

- `results/stage_1/` - Selección de perfil
- `results/stage_2/` - Análisis XFOIL completo
- `results/stage_3/` - Corrección de compresibilidad
- `results/stage_4/` - Métricas y tablas CSV
- `results/stage_5/` - Figuras de resultados
- `results/stage_6/` - Análisis Aerodinámico VPF
- `results/stage_7/` - Análisis Cinemático (Triángulos de Velocidad)
- `results/stage_8/` - Análisis SFC (Dampening)

## Comando Alternativo (Legacy)

También disponible el script anterior que ejecuta solo los 3 stages básicos:

```bash
python scripts/main.py
```

## Nota Importante

⚠️ **Nota**: Cada nueva ejecución sobrescribe la carpeta `results/` para mantener la consistencia de los datos analizados.

Si quieres conservar resultados anteriores, cópialos a otra ubicación antes de ejecutar.

## Tiempo Estimado

- **Stage 1**: ~2-3 minutos (4 perfiles × XFOIL)
- **Stage 2**: ~10-15 minutos (12 simulaciones XFOIL)
- **Stage 3**: ~10 segundos (corrección de compresibilidad)
- **Stage 4-8**: ~30 segundos (postprocesado y análisis)

**Total**: ~15-20 minutos aproximadamente

## Requisitos Previos

1. ✅ XFOIL instalado en: `C:\Users\Alvaro\Downloads\XFOIL6.99\xfoil.exe`
2. ✅ Perfiles `.dat` en `data/airfoils/`
3. ✅ Entorno virtual activado (`.venv`)
4. ✅ Dependencias instaladas (`pip install -r requirements.txt`)

---

Para iniciar el cálculo, ejecutar `python run_analysis.py`.
