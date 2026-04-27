# Project Structure

## Relevant Tree

```text
vpf/
  README.md
  requirements.txt
  run_analysis.py
  run_sensitivity.py
  config/
    README.md
    airfoils.yaml
    analysis_config.yaml
    engine_parameters.yaml
  data/
    airfoils/
      naca_0012.dat
      naca_63-215.dat
      naca_65-210.dat
      naca_65-410.dat
  docs/
    README.md
    overview.md
    project_structure.md
    setup_and_execution.md
    technical_architecture.md
    data_documentation.md
    results.md
    code_reference.md
    maintenance.md
    glossary.md
    design_decisions.md
  references/
    *.pdf
    esquema.txt
  src/
    vpf_analysis/
      settings.py
      config_loader.py
      xfoil_runner.py
      config/domain.py
      core/domain/
      adapters/xfoil/
      pipeline/contracts.py
      postprocessing/
      shared/plot_style.py
      stage1_airfoil_selection/
      stage2_xfoil_simulations/
      stage3_compressibility_correction/
      stage4_performance_metrics/
      stage5_pitch_kinematics/
      stage6_reverse_thrust/
      stage7_sfc_analysis/
      validation/
  tests/
    test_*.py
  results/
    stage1_airfoil_selection/
    stage2_xfoil_simulations/
    stage3_compressibility_correction/
    stage4_performance_metrics/
    stage5_pitch_kinematics/
    stage6_reverse_thrust/
    stage7_sfc_analysis/
    sensitivity/
```

## Folder Responsibilities

| Folder | Responsibility |
|---|---|
| `config/` | Physical, aerodynamic, engine, mission, and airfoil configuration. |
| `data/airfoils/` | Airfoil coordinate files used by XFOIL. |
| `docs/` | Technical documentation in Markdown only. |
| `references/` | External reference documents moved outside `docs` so `docs` remains Markdown-only. |
| `src/vpf_analysis/` | Source code for the pipeline. |
| `tests/` | Unit and contract tests. |
| `results/` | Generated outputs. Git ignores the contents except `.gitkeep`. |

## Critical Execution Files

| File | Reason |
|---|---|
| `run_analysis.py` | Main pipeline orchestrator. |
| `run_sensitivity.py` | Additional sensitivity analysis using existing results. |
| `requirements.txt` | Declared Python dependencies. |
| `config/analysis_config.yaml` | Controls aerodynamic setup, geometry, Reynolds, Mach, Ncrit, and XFOIL. |
| `config/engine_parameters.yaml` | Controls engine, mission, SFC, and reverse-thrust parameters. |
| `config/airfoils.yaml` | Defines candidate airfoils and their `.dat` files. |
| `data/airfoils/*.dat` | Required geometry input for XFOIL. |
| `src/vpf_analysis/xfoil_runner.py` | External XFOIL subprocess integration. |
| `src/vpf_analysis/settings.py` | Paths, XFOIL discovery, and typed settings loading. |

## Important Auxiliary Files

| File or Module | Purpose |
|---|---|
| `config/README.md` | Explains the physical basis of configuration parameters. |
| `src/vpf_analysis/postprocessing/aerodynamics_utils.py` | Efficiency-column resolution, peak selection, stall detection, interpolation. |
| `src/vpf_analysis/postprocessing/stage_summary_generator.py` | Writes `finalresults_stageX.txt`. |
| `src/vpf_analysis/shared/plot_style.py` | Shared plotting style and color palettes. |
| `src/vpf_analysis/validation/validators.py` | File, CSV, polar, physical-range, and XFOIL convergence checks. |
| `tests/` | Regression protection for models and pipeline contracts. |

## Source Code by Result Stage

| Stage | Main Modules |
|---|---|
| Stage 1 | `stage1_airfoil_selection/airfoil_selection_service.py`, `scoring.py` |
| Stage 2 | `stage2_xfoil_simulations/final_analysis_service.py`, `pitch_map.py` |
| Stage 3 | `stage3_compressibility_correction/*` |
| Stage 4 | `stage4_performance_metrics/metrics.py`, `plots.py`, `table_generator.py` |
| Stage 5 | `stage5_pitch_kinematics/application/run_pitch_kinematics.py`, `pitch_kinematics_core.py` |
| Stage 6 | `stage6_reverse_thrust/application/run_reverse_thrust.py`, `reverse_thrust_core.py` |
| Stage 7 | `stage7_sfc_analysis/application/run_sfc_analysis.py`, `sfc_core.py`, `engine/*` |

## Current Generated Results

The current `results/` directory contains generated artifacts including 58 CSV files and 103 PNG figures. These are documented in `results.md`.

## Obsolete, Duplicate, or Review-Pending Items

| Item | Observation |
|---|---|
| `src/vpf_analysis/stage4_performance_metrics/narrative_figures.py` | The module states it is retained for import compatibility and that older narrative figures were removed. |
| Root `README.md` | Useful, but some output names in its summary do not exactly match the current generated result tree. Treat `docs/` as the current documentation source. |
| `config/README.md` | Useful configuration reference outside `docs`. It remains separate from the requested documentation set. |
| `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.venv/` | Local caches or environment artifacts. |
| `results/stage7_sfc_analysis/tables/ge9x_sfc_improvement.tex` | Generated LaTeX output in `results/`, not `docs`. |

