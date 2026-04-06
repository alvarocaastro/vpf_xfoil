# 🚀 Quick Start Guide

## Ejecutar el Pipeline Completo

Para ejecutar **TODO el análisis aerodinámico** con un solo comando:

```bash
python run_analysis.py
```

## ¿Qué hace?

Este comando ejecuta automáticamente:

1. ✅ **Limpia** resultados anteriores
2. ✅ **Selecciona** el mejor perfil de `data/airfoils/`
3. ✅ **Ejecuta** 12 simulaciones XFOIL
4. ✅ **Aplica** corrección de compresibilidad
5. ✅ **Calcula** métricas de rendimiento
6. ✅ **Genera** tablas CSV para LaTeX
7. ✅ **Crea** todas las figuras para la tesis
8. ✅ **Analiza** Variable Pitch Fan (VPF)
9. ✅ **Analiza** Teoría de Cascadas
10. ✅ **Analiza** Impacto en Consumo Específico de Combustible (SFC)

## Resultados

Todos los resultados se organizan automáticamente por stage:

```
results/
├── stage_1/  # Selección de perfil
│   └── airfoil_selection/
│
├── stage_2/  # Simulaciones XFOIL
│   └── final_analysis/<flight>/<section>/
│
├── stage_3/  # Corrección de compresibilidad
│   └── <flight>/<section>/
│
├── stage_4/  # Métricas y tablas
│   └── tables/
│
├── stage_5/  # Figuras para tesis
│   └── figures/
│
├── stage_6/  # Análisis VPF
│   ├── figures/
│   ├── tables/
│   └── vpf_analysis_summary.txt
│
├── stage_7/  # Análisis de cascadas
│   ├── figures/
│   ├── tables/
│   └── cascade_dataset.csv
│
└── stage_8/  # Análisis SFC
    ├── figures/
    ├── tables/
    └── sfc_analysis_summary.txt
```

## Configuración

Edita los archivos de configuración para cambiar parámetros:

- `config/analysis_config.yaml`: Parámetros de simulación XFOIL
- `config/cascade_config.yaml`: Parámetros de cascadas (chord, spacing, velocidades)
- `config/engine_parameters.yaml`: Parámetros del motor (SFC baseline, eficiencia fan)

## Tiempo

**Total**: ~15-20 minutos

- Selección: ~2-3 min
- XFOIL: ~10-15 min
- Postprocesado: ~30 seg

---

**¡Listo!** Ejecuta `python run_analysis.py` y obtén todos los resultados automáticamente.
