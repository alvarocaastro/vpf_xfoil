# Complete Aerodynamic Analysis Pipeline

## Overview

The `run_analysis.py` script executes a complete, reproducible scientific pipeline for aerodynamic analysis. This pipeline automates all stages from airfoil selection to final publication-quality results.

## Quick Start

Execute the complete pipeline with a single command:

```bash
python run_analysis.py
```

## Pipeline Stages

The pipeline executes 10 sequential stages:

### Step 1: Clean Previous Results

Automatically removes old files from all stage directories:
- `results/stage_1/` through `results/stage_8/`

**Note**: Raw input files in `data/` are never deleted.

### Step 2: Automated Airfoil Selection

- Loads all `.dat` airfoil files from `data/airfoils/`
- Runs XFOIL simulations for comparison
- Applies scoring algorithm (max L/D, stall angle, average drag)
- Selects best airfoil automatically
- Stores results in `results/stage_1/airfoil_selection/`

### Step 3: XFOIL Aerodynamic Simulations

- Uses the selected airfoil from Step 2
- Runs simulations for all flight conditions × blade sections:
  - **Flight conditions**: Takeoff, Climb, Cruise, Descent
  - **Blade sections**: root, mid_span, tip
  - **Total**: 12 simulations
- Generates polar data (alpha, CL, CD, CL/CD)
- Stores polars in `results/stage_2/final_analysis/`

### Step 4: Compressibility Corrections

- Applies Prandtl-Glauert correction to Mach 0.2 results
- Target Mach numbers:
  - Takeoff: 0.30
  - Climb: 0.70
  - Cruise: 0.85
  - Descent: 0.75
- Generates corrected aerodynamic data
- Stores results in `results/stage_3/`

### Step 5: Compute Performance Metrics

Automatically computes key metrics:
- **Maximum efficiency**: (CL/CD)_max
- **Optimal angle of attack**: alpha_opt = argmax(CL/CD)
- **Maximum lift coefficient**: CL_max
- **Lift and drag at optimal angle**: CL_at_opt, CD_at_opt

### Step 6: Export Summary Tables

Generates CSV tables ready for LaTeX import:
- `efficiency_by_condition.csv`: Maximum efficiency by flight condition and section
- `alpha_opt_by_condition.csv`: Optimal angle of attack by condition
- `clcd_max_by_section.csv`: Maximum CL/CD by blade section
- `summary_table.csv`: Comprehensive summary with all metrics

All tables stored in `results/stage_4/tables/`

### Step 7: Generate Publication-Quality Figures

Automatically generates all required plots:

**Individual plots** (per flight condition × section):
- CL vs alpha
- CD vs alpha
- CL/CD vs alpha (with maximum marked)
- Polar plot (CL vs CD)

**Summary plots**:
- Optimal angle of attack vs flight condition
- Maximum efficiency vs Reynolds number
- Efficiency comparison by blade section

All figures stored in `results/stage_5/figures/` with:
- High resolution (300 DPI)
- Clear axis labels with units
- Grid enabled
- Legends
- Publication-ready format

### Step 8: Variable Pitch Fan Analysis

- Loads aerodynamic data from previous stages
- Computes optimal incidence angles (using second efficiency peak)
- Calculates pitch adjustments relative to cruise condition
- Generates VPF-specific figures:
  - Optimal angle vs flight condition
  - Required pitch adjustment
  - Efficiency curves with optimal points
  - Section comparison
- Creates analysis summary text

Results stored in:
- `results/stage_6/tables/vpf_optimal_pitch.csv`
- `results/stage_6/tables/vpf_pitch_adjustment.csv`
- `results/stage_6/figures/` (all VPF figures)
- `results/stage_6/vpf_analysis_summary.txt`

### Step 9: Specific Fuel Consumption Impact Analysis

- Loads aerodynamic efficiency data from previous stages
- Uses baseline engine parameters from configuration
- Estimates fan efficiency improvements from aerodynamic gains
- Computes SFC reductions using simplified propulsion model
- Generates SFC-specific figures:
  - SFC vs flight condition (baseline vs VPF)
  - SFC reduction percentage
  - Fan efficiency improvement
  - Aerodynamic efficiency vs SFC relationship
- Creates analysis summary text

Results stored in:
- `results/stage_7/tables/sfc_analysis.csv`
- `results/stage_7/figures/` (all SFC figures)
- `results/stage_7/sfc_analysis_summary.txt`

## Configuration

All simulation parameters are configured in:

`config/analysis_config.yaml`

This file contains:
- Reynolds numbers for each condition and section
- Ncrit values per flight condition
- Angle of attack ranges
- Target Mach numbers
- Output directory paths
- Plotting settings

## Output Structure

All results are organized by stage in dedicated directories:

```
results/
├── stage_1/                # Step 2: Airfoil selection
│   ├── airfoil_selection/
│   │   └── *_polar.txt
│   └── selected_airfoil.dat
│
├── stage_2/                # Step 3: XFOIL simulations
│   └── final_analysis/
│       ├── takeoff/
│       │   ├── root/
│       │   │   ├── polar.csv
│       │   │   ├── cl_alpha.csv
│       │   │   └── *.png
│       │   ├── mid_span/
│       │   └── tip/
│       ├── climb/
│       ├── cruise/
│       └── descent/
│
├── stage_3/                # Step 4: Compressibility corrections
│   ├── takeoff/
│   │   ├── root/
│   │   │   ├── corrected_polar.csv
│   │   │   └── corrected_plots.png
│   │   ├── mid_span/
│   │   └── tip/
│   └── ...
│
├── stage_4/                # Step 6: Performance metrics & tables
│   └── tables/
│       ├── efficiency_by_condition.csv
│       ├── alpha_opt_by_condition.csv
│       ├── clcd_max_by_section.csv
│       ├── summary_table.csv
│       ├── vpf_optimal_pitch.csv
│       └── ...
│
├── stage_5/                # Step 7: Publication-quality figures
│   └── figures/
│       ├── cl_alpha_takeoff_root.png
│       ├── cd_alpha_takeoff_root.png
│       ├── efficiency_takeoff_root.png
│       ├── polar_takeoff_root.png
│       ├── alpha_opt_vs_condition.png
│       └── ...
│
├── stage_6/                # Step 8: VPF analysis
│   ├── figures/
│   ├── tables/
│   └── vpf_analysis_summary.txt
│
└── stage_7/                # Step 9: SFC analysis
    ├── figures/
    ├── tables/
    └── sfc_analysis_summary.txt
```

## Logging

The pipeline uses structured logging with clear stage separation:

```
2026-03-17 10:00:00 [INFO] Starting Complete Aerodynamic Analysis Pipeline
============================================================
STEP 1: Cleaning previous results
============================================================
2026-03-17 10:00:01 [INFO] Removing: results/figures
...
```

## Reproducibility

The entire analysis is reproducible:

1. **Configuration-driven**: All parameters in YAML
2. **Deterministic**: Same inputs → same outputs
3. **Clean execution**: Previous results automatically cleaned
4. **Version control**: Configuration and code can be versioned

## Optional: Jupyter Notebook

An exploratory analysis notebook is available:

`notebooks/analysis_results.ipynb`

This notebook demonstrates:
- Loading results
- Visualizing aerodynamic curves
- Exploring efficiency trends

## Troubleshooting

### Configuration not found

Ensure `config/analysis_config.yaml` exists and is properly formatted.

### XFOIL not found

Verify XFOIL path in `src/vfp_analysis/config.py`:
```python
XFOIL_EXECUTABLE = Path(r"C:\Users\Alvaro\Downloads\XFOIL6.99\xfoil.exe")
```

### Missing airfoil files

Ensure all `.dat` files referenced in `config.AIRFOILS` exist in `data/airfoils/`.

## Performance

Typical execution times:
- **Step 1**: < 1 second (cleanup)
- **Step 2**: ~2-3 minutes (4 airfoils selection)
- **Step 3**: ~10-15 minutes (12 XFOIL simulations)
- **Step 4**: ~10 seconds (compressibility correction)
- **Step 5**: < 1 second (metrics computation)
- **Step 6**: < 1 second (table export)
- **Step 7**: ~5 seconds (figure generation)
- **Step 8**: ~2 seconds (VPF analysis)
- **Step 9**: ~1 second (Cascade analysis)
- **Step 10**: ~1 second (SFC analysis)

**Total**: ~15-20 minutes

## Integration with LaTeX

All generated tables can be imported directly into LaTeX:

```latex
\usepackage{csvsimple}

\csvautotabular{results/stage_4/tables/summary_table.csv}
```

Figures can be included:

```latex
\includegraphics[width=0.8\textwidth]{results/stage_5/figures/efficiency_takeoff_root.png}
```

---

**Last updated**: 2026-03-17
