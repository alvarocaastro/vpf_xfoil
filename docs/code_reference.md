# Code Reference

## Entry Points

### `run_analysis.py`

Main command-line orchestrator.

Responsibilities:

- Adds `src/` to `sys.path`.
- Cleans stage result folders when running from the beginning.
- Runs airfoil selection, XFOIL simulations, compressibility correction, metrics, pitch kinematics, reverse thrust, and SFC.
- Supports `--from-stage` and `--to-stage`.
- Validates stage outputs using `StageNResult` contracts.

Important functions:

| Function | Purpose | Side Effects |
|---|---|---|
| `step_1_clean_results()` | Reset result directories. | Deletes/recreates stage result directories. |
| `step_2_airfoil_selection()` | Run Stage 1 result generation. | Writes Stage 1 files. |
| `step_3_xfoil_simulations()` | Run final XFOIL simulations and pitch-map plots. | Calls XFOIL and writes Stage 2 outputs. |
| `step_4_compressibility_correction()` | Apply PG and KT corrections. | Writes Stage 3 outputs. |
| `step_5_metrics_and_figures()` | Compute Stage 4 metrics and figures. | Writes Stage 4 outputs. |
| `step_6_pitch_kinematics()` | Run Stage 5. | Writes Stage 5 outputs. |
| `step_7_reverse_thrust()` | Run Stage 6. | Writes Stage 6 outputs. |
| `step_8_sfc_analysis()` | Run Stage 7. | Writes Stage 7 outputs. |

### `run_sensitivity.py`

Standalone sensitivity script.

Responsibilities:

- Loads Stage 3 corrected polars and Stage 4 `summary_table.csv`.
- Sweeps `TAU_VALUES` and `RPM_DELTA_PCT`.
- Recomputes fixed-pitch incidence and SFC reduction.
- Writes `results/sensitivity/sensitivity_table.csv` and `sensitivity_heatmap.png`.

Important functions:

| Function | Purpose |
|---|---|
| `_load_corrected_polar()` | Load one Stage 3 corrected polar. |
| `_lookup_ld()` | Interpolate `CL/CD` at a target alpha. |
| `_compute_sensitivity_row()` | Compute mean SFC reduction for one `(tau, rpm_delta)` pair. |
| `main()` | Execute sweep and write outputs. |

## Configuration and Settings

### `src/vpf_analysis/settings.py`

Responsibilities:

- Defines root paths: `ROOT_DIR`, `AIRFOIL_DATA_DIR`, `RESULTS_DIR`.
- Maps result stage numbers to folder names.
- Discovers XFOIL executable.
- Loads airfoil catalog from `config/airfoils.yaml`.
- Provides cached typed settings via `get_settings()`.

Important functions/classes:

| Item | Purpose |
|---|---|
| `get_stage_dir(stage_num)` | Returns canonical result directory for a stage. |
| `get_settings()` | Loads and caches `PipelineSettings`. |
| `clear_settings_cache()` | Invalidates settings cache for tests. |
| `AirfoilSpec` | Typed dictionary for airfoil catalog entries. |

### `src/vpf_analysis/config_loader.py`

Lightweight YAML accessors.

Important functions:

| Function | Returns |
|---|---|
| `get_reynolds_table()` | Nested Reynolds table. |
| `get_ncrit_table()` | Ncrit per condition. |
| `get_target_mach()` | Target Mach per condition. |
| `get_alpha_range()` | Main alpha sweep. |
| `get_selection_conditions()` | Raw Stage 1 selection conditions. |
| `get_fan_rpm()` | RPM schedule. |
| `get_blade_radii()` | Blade section radii. |
| `get_axial_velocities()` | Axial velocity per condition. |
| `get_blade_geometry()` | Blade count, solidity, camber. |
| `get_mission_profile()` | Mission phases and economic assumptions. |

### `src/vpf_analysis/config/domain.py`

Defines dataclasses for settings and constants.

Key classes:

- `PhysicsConstants`
- `XfoilSettings`
- `FanGeometry`
- `BladeGeometry`
- `AirfoilGeometry`
- `ResolvedSelectionCondition`
- `PipelineSettings`

## XFOIL Integration

### `src/vpf_analysis/xfoil_runner.py`

Responsibilities:

- Builds interactive XFOIL command scripts.
- Runs XFOIL as a subprocess.
- Handles retries and timeouts.
- Checks convergence messages.
- Optionally caches polar results in `results/.polar_cache/`.

Key items:

| Item | Purpose |
|---|---|
| `XfoilPolarRequest` | Input parameters for an XFOIL polar. |
| `XfoilPolarResult` | Success state, convergence rate, retry count, failed alphas. |
| `XfoilError` | Raised when XFOIL cannot complete. |
| `run_xfoil_polar()` | Main XFOIL execution function. |
| `quick_smoke_test()` | Minimal XFOIL check for an airfoil file. |

### `src/vpf_analysis/adapters/xfoil/`

| File | Purpose |
|---|---|
| `xfoil_runner_adapter.py` | Adapts domain-level simulation conditions to `run_xfoil_polar()`. |
| `xfoil_parser.py` | Parses XFOIL polar text into DataFrames. |

## Domain Objects and Contracts

### `src/vpf_analysis/core/domain/`

| File | Class | Purpose |
|---|---|---|
| `airfoil.py` | `Airfoil` | Airfoil name and `.dat` path. |
| `blade_section.py` | `BladeSection` | Blade section identifier and properties. |
| `simulation_condition.py` | `SimulationCondition` | Mach, Reynolds, alpha range, Ncrit for a simulation. |

### `src/vpf_analysis/pipeline/contracts.py`

Defines `Stage1Result` through `Stage7Result`. Each contract has a `validate()` method to check required result paths and basic consistency.

## Stage 1: Airfoil Selection

### `airfoil_selection_service.py`

Key class: `AirfoilSelectionService`

Main method:

| Method | Purpose | Inputs | Outputs |
|---|---|---|---|
| `run_selection()` | Run XFOIL for candidate airfoils and select the best. | Airfoil list, selection conditions, alpha range, Mach reference. | `AirfoilSelectionResult`, plus files in Stage 1 output folder. |

Side effects:

- Writes raw XFOIL polar text files.
- Writes `scores.csv`.
- Writes `selected_airfoil.dat`.
- Writes `polar_comparison.png`.

### `scoring.py`

Key functions:

| Function | Purpose |
|---|---|
| `score_airfoil()` | Computes `max_ld`, `alpha_opt`, stall margin, robustness, and raw score for one polar. |
| `normalise_scores()` | Min-max normalizes score components across candidates. |
| `aggregate_weighted_scores()` | Combines per-condition scores using mission weights. |

## Stage 2: XFOIL Simulations and Pitch Map

### `final_analysis_service.py`

Key class: `FinalAnalysisService`

Main method:

| Method | Purpose |
|---|---|
| `run()` | Runs final XFOIL simulations for the selected airfoil across conditions and sections. |

Side effects:

- Writes `polar.dat`, `polar.csv`, `efficiency_plot.png`, `cl_alpha_stall.png`, and `polar_plot.png`.
- Copies canonical polars to `results/stage2_xfoil_simulations/polars/`.

### `pitch_map.py`

Key functions:

| Function | Purpose |
|---|---|
| `compute_pitch_map()` | Converts `alpha_opt` to inflow angle `phi` and blade pitch angle `beta`. |
| `save_pitch_map_csv()` | Writes `blade_pitch_map.csv`. |
| `plot_pitch_map()` | Writes `blade_pitch_map.png`. |
| `plot_alpha_opt_evolution()` | Writes `alpha_opt_evolution.png`. |
| `plot_vpf_efficiency_by_section()` | Writes one VPF efficiency plot per section. |
| `plot_vpf_clcd_penalty()` | Writes fixed-pitch penalty plot. |

## Stage 3: Compressibility Correction

| File | Key Item | Purpose |
|---|---|---|
| `prandtl_glauert.py` | `PrandtlGlauertModel` | Applies PG correction. |
| `karman_tsien.py` | `KarmanTsienModel` | Applies KT correction and corrected efficiency. |
| `critical_mach.py` | `estimate_mdd()`, `estimate_mcr()`, `wave_drag_increment()` | Estimates drag rise and wave drag. |
| `correction_service.py` | `CompressibilityCorrectionService` | Orchestrates correction, CSV export, and plots. |
| `compressibility_case.py` | `CompressibilityCase` | Case metadata. |
| `correction_result.py` | `CorrectionResult` | Output metadata. |

## Stage 4: Performance Metrics

### `metrics.py`

Key class: `AerodynamicMetrics`

Key functions:

| Function | Purpose |
|---|---|
| `compute_metrics_from_polar()` | Computes optimum efficiency, lift, drag, stall margin, and moment for one polar. |
| `compute_all_metrics()` | Runs metrics over all flight-section cases. |
| `enrich_with_cruise_reference()` | Computes fixed-pitch reference incidence and VPF gain. |

### `plots.py`

Generates Stage 4 figures:

- `compressibility_comparison.png`
- `polar_efficiency_{flight}_{section}.png`
- `lift_drag_curves_{flight}.png`
- `efficiency_map_{section}.png`

### `table_generator.py`

Exports:

- `summary_table.csv`
- `clcd_max_by_section.csv`

## Stage 5: Pitch Kinematics

### `pitch_kinematics_core.py`

Contains the pure calculation logic for:

- Cascade corrections.
- Snel and Du-Selig rotational corrections.
- 3D polar maps.
- Optimal incidence.
- Pitch adjustments.
- Blade twist.
- Off-design incidence.
- Stage loading.
- Velocity-triangle kinematics.

Important dataclasses:

- `CascadeResult`
- `RotationalCorrectionResult`
- `DuSeligCorrectionResult`
- `TwistDesignResult`
- `OffDesignIncidenceResult`
- `StageLoadingResult`

### `application/run_pitch_kinematics.py`

Stage 5 orchestrator.

Side effects:

- Writes 10 CSV tables.
- Writes Stage 5 figures.
- Writes `pitch_kinematics_summary.txt`.
- Writes `finalresults_stage5.txt`.

### `adapters/filesystem/`

| File | Purpose |
|---|---|
| `data_loader.py` | Loads Stage 2 and Stage 3 polar files. |
| `results_writer.py` | Writes optimal incidence, pitch adjustment, kinematics, and summaries. |

## Stage 6: Reverse Thrust

### `application/run_reverse_thrust.py`

Current main Stage 6 workflow:

- Loads reverse-thrust parameters from `engine_parameters.yaml`.
- Computes VPF mechanism weight versus conventional reverser.
- Writes `mechanism_weight.csv`.
- Writes `mechanism_weight_comparison.png`.
- Writes `reverse_thrust_summary.txt`.

### `reverse_thrust_core.py`

Contains:

- Mechanism weight model used by the current main Stage 6.
- Reverse kinematics support.
- BEM sweep support.
- Viterna-Corrigan extrapolation support for deep stall.

Warning: full BEM-related paths are present but not the main orchestrated result path. They also reference `scipy` internally.

## Stage 7: SFC Analysis

### `sfc_core.py`

Key functions:

| Function | Purpose |
|---|---|
| `compute_bypass_sensitivity_factor()` | Computes `BPR/(1+BPR)`. |
| `compute_fan_efficiency_improvement()` | Profile-based fan efficiency gain. |
| `compute_fan_map_efficiency_gain()` | Fan-map mechanism from flow coefficient shift. |
| `compute_combined_fan_efficiency_improvement()` | Combines profile and map mechanisms with caps. |
| `compute_sfc_improvement()` | Converts fan efficiency change into new SFC. |
| `compute_sfc_analysis()` | Main condition and section SFC calculation. |
| `compute_sfc_sensitivity()` | Internal tau sweep. |
| `compute_mission_fuel_burn()` | Mission fuel, CO2, and cost savings. |
| `generate_sfc_summary()` | Text report for SFC outputs. |

### `application/run_sfc_analysis.py`

Stage 7 orchestrator.

Side effects:

- Writes SFC tables.
- Writes `sfc_improvement_by_condition.png`.
- Writes SFC summaries.
- Calls GE9X parametric analysis.

### `engine/`

| File | Purpose |
|---|---|
| `engine_data.py` | GE9X parameters and unit conversion helpers. |
| `turbofan_cycle.py` | Simplified two-stream turbofan SFC cycle model. |
| `sfc_model.py` | Standalone SFC improvement model used by tests and GE9X sweep. |
| `ge9x_analysis.py` | Parametric `CL/CD` sweep, GE9X figures, and LaTeX table. |

## Postprocessing and Validation

| Module | Purpose |
|---|---|
| `postprocessing/aerodynamics_utils.py` | Efficiency-column resolution, second-peak search, stall alpha, interpolation. |
| `postprocessing/cli_tables.py` | Rich CLI convergence and summary tables. |
| `postprocessing/latex_exporter.py` | Exports DataFrames to LaTeX. |
| `postprocessing/stage_summary_generator.py` | Writes `finalresults_stageX.txt`. |
| `validation/validators.py` | Validates files, directories, CSV columns, physical ranges, polar quality, and XFOIL convergence. |

## Tests

Detected tests include:

- Airfoil reader behavior.
- Airfoil selection scoring.
- Efficiency calculations.
- Peak-finding behavior.
- Pipeline contracts.
- Prandtl-Glauert correction.
- Reynolds calculation.
- SFC model.
- Viterna extrapolation.

