# Estructura del Proyecto

## Organización Profesional

Este proyecto sigue una estructura profesional tipo empresa, separando claramente código fuente, datos, resultados, scripts y documentación.

## Árbol de Directorios

```
tfg_vpf/
│
├── 📄 README.md                    # Documentación principal del proyecto
├── 📄 requirements.txt              # Dependencias Python
├── 📄 .gitignore                   # Archivos ignorados por Git
│
├── 📁 src/                         # Código fuente
│   └── vfp_analysis/              # Módulo principal
│       ├── __init__.py
│       ├── config.py              # Configuración global
│       ├── xfoil_runner.py        # Wrapper para XFOIL
│       ├── run_complete_pipeline.py  # Pipeline integrado
│       │
│       ├── core/                  # Lógica de negocio (Clean Architecture)
│       │   ├── domain/           # Modelos de dominio
│       │   │   ├── airfoil.py
│       │   │   ├── blade_section.py
│       │   │   ├── scoring.py
│       │   │   └── simulation_condition.py
│       │   └── services/         # Servicios de aplicación
│       │       ├── airfoil_selection_service.py
│       │       └── final_analysis_service.py
│       │
│       ├── ports/                 # Interfaces (Hexagonal Architecture)
│       │   └── xfoil_runner_port.py
│       │
│       ├── adapters/              # Implementaciones concretas
│       │   └── xfoil/
│       │       └── xfoil_runner_adapter.py
│       │
│       ├── compressibility/       # Módulo de corrección de compresibilidad
│       │   ├── config.py
│       │   ├── core/
│       │   │   ├── domain/
│       │   │   └── services/
│       │   ├── ports/
│       │   ├── adapters/
│       │   └── application/
│       │
│       ├── application/           # Scripts de aplicación
│       │   ├── run_airfoil_selection.py
│       │   └── run_final_simulations.py
│       │
│       ├── utils/                # Utilidades
│       │   └── cleanup.py
│       │
│       └── docs/                  # Documentación técnica
│           ├── README_overview.md
│           ├── README_stage1_airfoil_selection.md
│           └── README_stage2_final_analysis.md
│
├── 📁 data/                       # Datos de entrada
│   └── airfoils/                 # Archivos .dat de perfiles
│       ├── NACA 65-210.dat
│       ├── naca 65-410.dat
│       ├── naca63215.dat
│       └── naca0012.dat
│
├── 📁 results/                    # Resultados generados
│   ├── stage_1/                  # Selección de perfil
│   │   ├── airfoil_selection/
│   │   └── selected_airfoil.dat
│   │
│   ├── stage_2/                  # Análisis XFOIL a Mach 0.2
│   │   ├── final_analysis/
│   │   │   ├── takeoff/
│   │   │   ├── climb/
│   │   │   ├── cruise/
│   │   │   └── descent/
│   │   ├── max_efficiency_summary.csv
│   │   └── efficiency_mean_all_flights.png
│   │
│   └── stage_3/                  # Corrección de compresibilidad
│       ├── takeoff/
│       ├── climb/
│       ├── cruise/
│       ├── descent/
│       ├── corrected_efficiency_all_flights.png
│       └── corrected_efficiency_summary.csv
│
├── 📁 scripts/                    # Scripts ejecutables
│   └── main.py                    # Entrypoint principal
│
├── 📁 docs/                       # Documentación
│   ├── README.md
│   ├── STRUCTURE.md              # Este archivo
│   ├── methodology.md
│   ├── architecture.md
│   └── references/               # PDFs de referencia
│       ├── Bentley_D_2018.pdf
│       └── ...
│
├── 📁 tests/                      # Tests unitarios (opcional)
│
└── 📁 latextfg/                   # Documento LaTeX de la tesis
    ├── main.tex
    ├── chapters/
    │   ├── 01_introduccion/
    │   ├── 02_marco_teorico/
    │   ├── 03_metodologia/
    │   ├── 04_resultados/
    │   └── 05_conclusiones/
    ├── images/
    └── scripts/
```

## Principios de Organización

### 1. Separación de Responsabilidades

- **`src/`**: Solo código fuente Python
- **`data/`**: Solo datos de entrada (inmutables)
- **`results/`**: Solo resultados generados (regenerables)
- **`scripts/`**: Solo scripts ejecutables
- **`docs/`**: Solo documentación

### 2. Arquitectura Hexagonal

El código sigue el patrón **Ports & Adapters** (Hexagonal Architecture):

- **`core/domain/`**: Entidades y modelos de dominio (sin dependencias externas)
- **`core/services/`**: Lógica de negocio
- **`ports/`**: Interfaces abstractas
- **`adapters/`**: Implementaciones concretas (XFOIL, filesystem, etc.)

### 3. Modularidad

- Cada módulo (`compressibility/`, `core/`, etc.) es independiente
- Las dependencias van hacia adentro (hacia `core/`)
- Los adapters implementan interfaces definidas en `ports/`

### 4. Configuración Centralizada

- `config.py`: Configuración global del proyecto
- `compressibility/config.py`: Configuración específica del módulo
- Todas las rutas se calculan relativas a `ROOT_DIR`

## Flujo de Datos

```
data/airfoils/*.dat
    ↓
[Stage 1: Selección]
    ↓
results/stage_1/selected_airfoil.dat
    ↓
[Stage 2: Análisis XFOIL]
    ↓
results/stage_2/final_analysis/
    ↓
[Stage 3: Corrección Compresibilidad]
    ↓
results/stage_3/
```

## Convenciones de Nomenclatura

- **Archivos Python**: `snake_case.py`
- **Clases**: `PascalCase`
- **Funciones/Variables**: `snake_case`
- **Constantes**: `UPPER_SNAKE_CASE`
- **Directorios**: `snake_case/`

## Mantenimiento

### Añadir Nuevo Perfil

1. Añadir archivo `.dat` a `data/airfoils/`
2. Actualizar `config.AIRFOILS` en `src/vfp_analysis/config.py`

### Añadir Nueva Condición de Vuelo

1. Actualizar `re_table` en `run_complete_pipeline.py`
2. Actualizar `TARGET_MACH` en `compressibility/config.py` (si aplica)

### Limpiar Resultados

```bash
# Los resultados se limpian automáticamente al ejecutar el pipeline
# O manualmente:
rm -rf results/
```

## Versionado

- **Git**: El proyecto está preparado para Git
- **`.gitignore`**: Excluye `__pycache__/`, `*.pyc`, resultados temporales
- **Resultados**: Opcionalmente versionables (descomentar en `.gitignore`)

---

**Última actualización**: Marzo 2026
