# Variable Pitch Fan (VPF) Aerodynamic Analysis

Análisis aerodinámico profesional de perfiles alares para fan blades de turbofan mediante simulación XFOIL y corrección de compresibilidad.

## 📋 Descripción del Proyecto

Este proyecto implementa un pipeline completo de análisis aerodinámico para la selección y evaluación de perfiles alares en condiciones de vuelo realistas. El sistema utiliza XFOIL para simulaciones incompresibles y aplica correcciones de compresibilidad mediante el modelo Prandtl-Glauert.

### Características Principales

- **Arquitectura Hexagonal (Ports & Adapters)**: Diseño limpio, modular y testeable
- **Pipeline Automatizado**: Ejecución secuencial de 10 steps (organizados en 8 stages) sin intervención manual
- **Análisis Multi-Condición**: Evaluación en 4 condiciones de vuelo (Takeoff, Climb, Cruise, Descent)
- **Análisis Multi-Sección**: Simulación de 3 secciones radiales del blade (root, mid_span, tip)
- **Corrección de Compresibilidad**: Postprocesado para Mach numbers representativos
- **Visualización Profesional**: Gráficos de calidad para publicación en tesis

## 🏗️ Estructura del Proyecto

```
tfg_vpf/
├── README.md                 # Este archivo
├── requirements.txt          # Dependencias Python
├── setup.py                  # Configuración del paquete (opcional)
│
├── src/                      # Código fuente
│   └── vfp_analysis/         # Módulo principal
│       ├── __init__.py
│       ├── config.py         # Configuración global
│       ├── xfoil_runner.py  # Wrapper para XFOIL
│       ├── run_complete_pipeline.py  # Pipeline integrado
│       │
│       ├── core/             # Lógica de negocio
│       │   ├── domain/       # Modelos de dominio
│       │   └── services/     # Servicios de aplicación
│       │
│       ├── ports/            # Interfaces abstractas
│       ├── adapters/         # Implementaciones concretas
│       │   └── xfoil/
│       │
│       ├── compressibility/  # Módulo de corrección de compresibilidad
│       │   ├── core/
│       │   ├── ports/
│       │   └── adapters/
│       │
│       ├── application/      # Scripts de aplicación
│       └── utils/            # Utilidades
│
├── data/                     # Datos de entrada
│   └── airfoils/            # Archivos .dat de perfiles
│
├── results/                  # Resultados generados (organizados por stage)
│   ├── stage_1/             # Selección de perfil
│   ├── stage_2/             # Análisis XFOIL a Mach 0.2
│   ├── stage_3/             # Corrección de compresibilidad
│   ├── stage_4/             # Métricas y tablas
│   ├── stage_5/             # Figuras de resultados
│   ├── stage_6/             # Análisis Aerodinámico Variable Pitch Fan
│   ├── stage_7/             # Análisis Cinemático (Triángulos de Velocidad)
│   └── stage_8/             # Análisis de Impacto SFC (con factor Dampening)
│
├── scripts/                  # Scripts ejecutables
│   └── main.py              # Entrypoint principal
│
├── docs/                     # Documentación
│   ├── README.md
│   ├── methodology.md
│   ├── architecture.md
│   └── references/          # PDFs de referencia
│
├── tests/                    # Tests unitarios
│   └── TEST_RESULTS.md      # Resultados de tests
│
├── config/                   # Configuración
│   └── analysis_config.yaml  # Parámetros de simulación
│
├── notebooks/                # Análisis exploratorio (opcional)
│   └── analysis_results.ipynb
│
└── latextfg/                 # Documento LaTeX de la tesis
    ├── main.tex
    ├── chapters/
    └── images/
```

## 🚀 Instalación

### Requisitos Previos

- **Python 3.8+**
- **XFOIL 6.99** instalado y accesible
- **Git** (opcional, para control de versiones)

### Pasos de Instalación

1. **Clonar o descargar el proyecto**:
   ```bash
   cd C:\Users\Alvaro\Desktop\tfg_vpf
   ```

2. **Crear entorno virtual** (recomendado):
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   # o
   source .venv/bin/activate  # Linux/Mac
   ```

3. **Instalar dependencias**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar XFOIL**:
   - Verificar que XFOIL esté en: `C:\Users\Alvaro\Downloads\XFOIL6.99\xfoil.exe`
   - Si está en otra ubicación, editar `src/vfp_analysis/config.py` y actualizar `XFOIL_EXECUTABLE`

5. **Verificar datos de entrada**:
   - Los archivos `.dat` de perfiles deben estar en `data/airfoils/`
   - Verificar que los nombres coincidan con `config.AIRFOILS` en `config.py`

## 💻 Uso

### Ejecución del Pipeline Completo (Recomendado)

**Para ejecutar TODO el proyecto** con pipeline científico completo y reproducible:

```bash
python run_analysis.py
```

Este comando ejecuta automáticamente:
1. ✅ **Step 1**: Limpia resultados anteriores (todos los stage_*)
1. **Step 1**: Limpia resultados anteriores (todos los stage_*)
2. **Step 2 / Stage 1**: Selección automática de perfil óptimo
3. **Step 3 / Stage 2**: Análisis XFOIL a Mach 0.2 (12 simulaciones)
4. **Step 4 / Stage 3**: Corrección de compresibilidad
5. **Step 5 / Stage 4**: Cálculo de métricas de rendimiento
6. **Step 6 / Stage 4**: Exportación de tablas CSV para LaTeX
7. **Step 7 / Stage 5**: Generación interpolada de gráficas
8. **Step 8 / Stage 6**: Análisis Integrado de Variable Pitch Fan (VPF)
9. **Step 9 / Stage 7**: Análisis Cinemático y Paso Mecánico
10. **Step 10 / Stage 8**: Análisis de Impacto en SFC

**Resultados organizados por stage**:
- `results/stage_1/`: Selección de perfil (airfoil_selection/, selected_airfoil.dat)
- `results/stage_2/`: Simulaciones XFOIL (final_analysis/<flight>/<section>/)
- `results/stage_3/`: Corrección de compresibilidad (<flight>/<section>/)
- `results/stage_4/`: Métricas y tablas CSV (tables/)
- `results/stage_5/`: Figuras para tesis (figures/)
- `results/stage_6/`: Análisis VPF (figures/, tables/, finalresults_stage6.txt)
- `results/stage_7/`: Análisis Cinemático (figures/, tables/, finalresults_stage7.txt)
- `results/stage_8/`: Análisis SFC (figures/, tables/, finalresults_stage8.txt)

**Nota**: Cada ejecución borra resultados anteriores para garantizar reproducibilidad.

**Tiempo estimado**: ~15-20 minutos

### Ejecución Alternativa (Script Legacy)

También disponible el script anterior:

```bash
python scripts/main.py
```

Este ejecuta los 3 stages básicos (selección, XFOIL, compresibilidad) sin el postprocesado completo.

### Pipeline por Stages

El pipeline ejecuta secuencialmente 10 steps organizados en 8 stages:

1. **Step 1: Limpieza de Resultados**
   - Elimina todos los resultados anteriores de `results/stage_*`

2. **Step 2 / Stage 1: Selección de Perfil**
   - Lee todos los `.dat` de `data/airfoils/`
   - Ejecuta simulaciones XFOIL comparativas
   - Calcula scores basados en eficiencia máxima, stall angle y drag promedio

3. **Step 3 / Stage 2: Análisis XFOIL a Mach 0.2**
   - Usa el perfil seleccionado en Stage 1
   - Simula 12 casos: 4 condiciones de vuelo × 3 secciones radiales

4. **Step 4 / Stage 3: Corrección de Compresibilidad**
   - Aplica corrección Prandtl-Glauert a resultados de Stage 2
   - Mach numbers objetivo: Takeoff (0.30), Climb (0.70), Cruise (0.85), Descent (0.75)

5. **Step 5 / Stage 4: Cálculo de Métricas de Rendimiento**
   - Calcula métricas aerodinámicas clave (eficiencia máxima, alpha_opt, CL_max)

6. **Step 6 / Stage 4: Exportación de Tablas**
   - Genera tablas CSV listas para LaTeX

7. **Step 7 / Stage 5: Generación de Figuras**
    - Exportación de métricas a formato gráfico PNG.

8. **Step 8 / Stage 6: Análisis Variable Pitch Fan (VPF)**
   - Analiza óptimos aerodinámicos (Δα) relativos a condición de crucero.
   - Genera figuras y tablas específicas de VPF.

9. **Step 9 / Stage 7: Análisis Cinemático (Triángulos de Velocidad)**
   - Conecta resultados aerodinámicos con un modelo físico motriz del actuador.
   - Resuelve el triángulo de velocidad ($V_{ax}$, $U$, $\phi$) para separar la incidencia puramente aerodinámica del giro mecánico real de la pala ($\Delta\beta$).

10. **Step 10 / Stage 8: Análisis de Impacto SFC**
    - Evaluación de mejoras en SFC global.
    - Empleo de factor empírico de transferencia para modelar flujos secundarios del rotor.

### Resultados Generados

#### Stage 1 (`results/stage_1/`)
- `airfoil_selection/`: Polares comparativos de todos los perfiles
- `selected_airfoil.dat`: Nombre del perfil seleccionado

#### Stage 2 (`results/stage_2/`)
- `final_analysis/<flight>/<section>/`: 12 simulaciones individuales
  - `polar.dat`, `polar.csv`: Datos completos del polar
  - `cl_alpha.csv`, `cd_alpha.csv`: Coeficientes vs ángulo de ataque
  - `cl_alpha_plot.png`, `cd_alpha_plot.png`: Gráficos individuales
  - `efficiency_plot.png`: Eficiencia CL/CD vs alpha con máximo marcado
  - `polar_plot.png`: Polar CL vs CD

#### Stage 3 (`results/stage_3/`)
- `<flight>/<section>/`: Resultados corregidos por compresibilidad
  - `corrected_polar.csv`: Polar completo corregido
  - `corrected_cl_alpha.csv`, `corrected_efficiency.csv`: Datos corregidos
  - `corrected_plots.png`: Comparación original vs corregido

#### Stage 4 (`results/stage_4/`)
- `tables/`: Tablas CSV listas para LaTeX
  - `efficiency_by_condition.csv`, `alpha_opt_by_condition.csv`
  - `summary_table.csv`, `vpf_optimal_pitch.csv`, etc.

#### Stage 5 (`results/stage_5/`)
- `figures/`: Figuras de calidad para publicación
  - `cl_alpha_*.png`, `cd_alpha_*.png`, `efficiency_*.png`, etc.

#### Stage 6 (`results/stage_6/`)
- `figures/`: Figuras de análisis VPF
- `tables/`: Tablas VPF (vpf_optimal_pitch.csv, vpf_pitch_adjustment.csv)
- `vpf_analysis_summary.txt`: Resumen del análisis

#### Stage 7 (`results/stage_7/`)
- `figures/`: Figuras de análisis de cascadas
- `tables/`: Tablas de cascadas (cascade_solidity.csv, flow_angles.csv, etc.)
- `cascade_dataset.csv`: Dataset consolidado

#### Stage 8 (`results/stage_8/`)
- `figures/`: Figuras de análisis SFC
- `tables/`: Tablas SFC (sfc_analysis.csv)
- `sfc_analysis_summary.txt`: Resumen del análisis

## ⚙️ Configuración

### Archivo de Configuración Centralizado

**Toda la configuración** se encuentra en:

`config/analysis_config.yaml`

Este archivo contiene:
- Números de Reynolds por condición y sección
- Valores de Ncrit por condición de vuelo
- Rangos de ángulo de ataque
- Mach numbers objetivo para compresibilidad
- Rutas de salida
- Configuración de gráficos

**Modificar parámetros**: Edita `config/analysis_config.yaml` y ejecuta `python run_analysis.py`

### Perfiles Alares

Los perfiles se definen en `src/vfp_analysis/config.py` (el módulo se llama `vfp_analysis` por razones históricas, pero el proyecto es sobre VPF - Variable Pitch Fan):

```python
AIRFOILS: Final[list[AirfoilSpec]] = [
    {
        "name": "NACA 65-410",
        "dat_file": "naca 65-410.dat",
        "family": "NACA 65-series",
        ...
    },
    ...
]
```

### Ejemplo de Configuración YAML

```yaml
reynolds:
  takeoff:
    root: 2.5e6
    mid_span: 4.5e6
    tip: 7.0e6
  ...

target_mach:
  takeoff: 0.30
  climb: 0.70
  cruise: 0.85
  descent: 0.75
```

## 📊 Perfiles Alares Analizados

1. **NACA 65-210**: Perfil de difusión controlada, 2% camber, 10% thickness
2. **NACA 65-410**: Perfil de difusión controlada, 4% camber, 10% thickness
3. **NACA 63-215**: Perfil de flujo laminar adaptado a turbomaquinaria
4. **NACA 0012**: Perfil simétrico de referencia, 12% thickness

## 🔬 Metodología

### Stage 1: Selección de Perfil

- **Condición de referencia**: Re = 3.0e6, M = 0.2, α = [-5°, 20°], step = 0.15°
- **Criterio de selección**: Score combinado de:
  - Máxima eficiencia CL/CD
  - Ángulo de stall
  - Drag promedio

### Stage 2: Análisis Final

- **Mach number**: 0.2 (incompresible, limitación de XFOIL)
- **Rango de alpha**: [-5°, 23°], step = 0.15°
- **Ncrit**: Variable por condición (5.0-7.0, representando turbulencia del entorno)
- **12 simulaciones**: 4 condiciones × 3 secciones

### Stage 3: Corrección de Compresibilidad

- **Modelo**: Prandtl-Glauert
- **Aplicación**: Corrección de CL, CD sin corregir (estrategia conservadora)
- **Validación**: Aproximación válida para M < 0.8

### Stage 4: Métricas y Tablas

- **Métricas calculadas**: Eficiencia máxima, alpha_opt (segundo pico), CL_max
- **Tablas generadas**: Eficiencia por condición, alpha_opt, resúmenes completos
- **Formato**: CSV listo para importación en LaTeX

### Stage 5: Figuras para Documentación

- **Tipos de figuras**: `efficiency_by_section`, `alpha_opt_vs_condition`.
- **Formato**: Archivos PNG para integración en memoria.

### Stage 6: Análisis Variable Pitch Fan

- **Objetivo**: Demostrar los beneficios de la optimización del paso aerodinámico (Delta Alpha).
- **Resultados**: Curvas de comportamiento y variaciones angulares relativas.

### Stage 7: Análisis Cinemático (Paso Físico Real)

- **Objetivo**: Añadir rigor al estimar cómo cambiar de condición de vuelo (ej: Takeoff a Cruise) altera masivamente el triángulo de velocidades y el `inflow angle`.
- **Parámetros**: RPM Fan asimiladas y `target_mach` combinados para obtener el `Delta Beta` mecánico.
- **Resultados**: Tablas desglosadas de $\Delta\alpha_{aero}$ vs $\Delta\beta_{mech}$.

### Stage 8: Análisis de SFC

- **Modelo**: Conversión de eficiencia perfil a eficiencia motor empleando `profile_efficiency_transfer` de mitigación (0.65 propuesto empíricamente en `engine_parameters.yaml`).

## 🧪 Testing

```bash
# Ejecutar tests (si están implementados)
python -m pytest tests/
```

## 📝 Documentación Adicional

- `docs/PIPELINE.md`: Documentación completa del pipeline (10 steps, 8 stages)
- `QUICK_START.md`: Guía rápida de inicio
- `EJECUTAR.md`: Guía detallada de ejecución
- `tests/README.md`: Documentación de tests
- `tests/TEST_RESULTS.md`: Resultados de tests
- `src/vfp_analysis/docs/`: Documentación técnica por módulo

## 🤝 Contribución

Este es un proyecto académico para tesis de grado. Para modificaciones:

1. Mantener la arquitectura hexagonal
2. Seguir principios de Clean Code
3. Documentar cambios significativos
4. Verificar que el pipeline completo funcione

## 📄 Licencia

Proyecto académico - Uso educativo.

## 👤 Autor

Alvaro - Trabajo Fin de Grado (TFG)

## 🙏 Agradecimientos

- XFOIL (Mark Drela, MIT)
- Bibliografía: Saravanamuttoo, Farokhi, Bertin & Cummings

---

**Última actualización**: Marzo 2026
