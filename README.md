# Variable Pitch Fan — Aerodynamic Analysis Pipeline

Python pipeline for the complete aerodynamic analysis of a variable-pitch fan (VPF).
Covers everything from NACA aerofoil selection to estimated specific fuel consumption (SFC) reduction, including XFOIL simulations, 3D compressibility corrections, blade kinematics with cascade effects, and stage loading.

---

## Reference engine

All geometric and operating parameters replicate a **GE9X (Boeing 777X)**: BPR≈10, 3.40 m fan, 16 wide-chord composite blades, design RPM 2200.

## Flight conditions and blade sections

| Condition | M_rel @ mid-span | Va [m/s] | Ncrit |
|-----------|------------------|----------|-------|
| Takeoff   | 0.85             | 180      | 4.0   |
| Climb     | 0.85             | 155      | 4.0   |
| Cruise    | 0.93             | 150      | 4.0   |
| Descent   | 0.80             | 125      | 4.0   |

Va is the axial velocity at the fan face (≠ aircraft flight speed). M_rel is evaluated at mid-span using the relative velocity W (Va + U), which is the physically relevant Mach number for 2D compressibility corrections.

| Section   | Radius [m] | U [m/s] @ 2200 rpm | c [m] | σ    |
|-----------|------------|--------------------|-------|------|
| Root      | 0.53       | 122.1              | 0.36  | 1.73 |
| Mid-span  | 1.00       | 230.4              | 0.46  | 1.17 |
| Tip       | 1.70       | 391.7              | 0.46  | 0.69 |

---

## Pipeline architecture

```
run_analysis.py
│
├── Stage 1 — Aerofoil selection
│   └── XFOIL @ Re_cruise, M_cruise → CL/CD ranking → NACA 65-410
│
├── Stage 2 — Final XFOIL simulations
│   └── 12 polars (4 conditions × 3 sections)
│       automatic retry (up to 3 attempts), convergence detection
│
├── Stage 3 — Compressibility corrections
│   ├── Prandtl–Glauert: CL_PG = CL / √(1 − M²)
│   ├── Karman–Tsien:    CL_KT = CL / [β + (M²/2β)·CL/2]
│   └── Korn (wave):     M_dd estimated → CD penalty for M > M_dd
│
├── Stage 4 — Performance metrics
│   └── CL/CD_max, α_opt, CL_max, stall margin, Δα VPF vs fixed pitch
│
├── Stage 5 — Pitch kinematics (3D fan analysis)
│   ├── [A] Cascade correction: Weinig (K_weinig) + Carter (δ_carter)
│   ├── [B] 3D rotational correction: Snel (ΔCL ∝ (c/r)²·CL_2D), Du-Selig comparative
│   ├── [C] Design twist + off-design trade-off with single actuator
│   ├── [D] Dual stage loading: ideal scenario (α_opt_3D) vs real scenario (α_actual)
│   └── Velocity triangles: Va → φ → β_mech, Δβ per condition
│
├── Stage 6 — Reverse thrust
│   ├── Negative pitch sweep: Δβ ∈ [−25°, −5°] at N1 = 65%
│   ├── Reverse thrust per section and total; stall margin criterion
│   └── VPF mechanism weight vs conventional cascade reverser
│
└── Stage 7 — SFC and mission analysis
    ├── ε(r, cond) = (CL/CD)_vpf / (CL/CD)_fixed_ref
    ├── Δη_fan = τ · (ε̄ − 1) · η_fan,base
    ├── SFC_new = SFC_base / (1 + Δη/η_base)
    └── Mission integration: fuel burn per phase, sensitivity to τ
```

---

## Directory structure

```
vpf/
├── config/
│   ├── analysis_config.yaml      # fan geometry, conditions, Re, Ncrit
│   └── engine_parameters.yaml    # η_fan base, SFC baseline, τ, mission, reverse thrust
├── data/
│   └── airfoils/                 # NACA aerofoil .dat files
├── results/
│   ├── stage1_airfoil_selection/
│   ├── stage2_xfoil_simulations/
│   ├── stage3_compressibility_correction/
│   ├── stage4_performance_metrics/
│   ├── stage5_pitch_kinematics/
│   │   ├── figures/              # 20 figures
│   │   └── tables/               # 10 CSV tables
│   ├── stage6_reverse_thrust/
│   │   ├── figures/              # 4 figures
│   │   └── tables/               # 4 CSV tables
│   └── stage7_sfc_analysis/
│       ├── figures/              # 7 figures
│       └── tables/               # 4 CSV tables
├── src/vfp_analysis/
│   ├── settings.py               # PhysicsConstants, XfoilSettings, PipelineSettings
│   ├── config_loader.py          # YAML reading → typed structures
│   ├── validation/
│   │   └── validators.py         # file/dir/polar/physical range checks
│   ├── pipeline/
│   │   └── contracts.py          # StageNResult with validate()
│   ├── adapters/xfoil/           # XfoilRunnerAdapter, parser, port
│   ├── postprocessing/
│   │   ├── aerodynamics_utils.py
│   │   ├── publication_figures.py
│   │   └── stage_summary_generator.py
│   ├── shared/
│   │   └── plot_style.py         # apply_style() — Paul Tol colours
│   ├── stage1_airfoil_selection/
│   ├── stage2_xfoil_simulations/
│   ├── stage3_compressibility_correction/
│   ├── stage4_performance_metrics/
│   ├── stage5_pitch_kinematics/
│   │   ├── application/
│   │   │   └── run_pitch_kinematics.py
│   │   └── core/services/
│   │       ├── cascade_correction_service.py
│   │       ├── rotational_correction_service.py   # Snel + Du-Selig
│   │       ├── blade_twist_service.py              # twist + off-design α
│   │       ├── stage_loading_service.py            # φ, ψ, W_spec (α-agnostic)
│   │       ├── optimal_incidence_service.py
│   │       ├── pitch_adjustment_service.py
│   │       └── kinematics_service.py
│   ├── stage6_reverse_thrust/
│   │   ├── application/run_reverse_thrust.py
│   │   └── core/services/
│   │       ├── reverse_kinematics_service.py
│   │       ├── reverse_thrust_service.py
│   │       └── mechanism_weight_service.py
│   └── stage7_sfc_analysis/
│       ├── application/run_sfc_analysis.py
│       └── core/services/
│           ├── propulsion_model_service.py
│           ├── sfc_analysis_service.py
│           ├── mission_analysis_service.py
│           └── summary_generator_service.py
├── tests/
└── run_analysis.py
```

---

## Requirements and installation

**Python 3.10+** and **XFOIL** installed and accessible on the `PATH`.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

If XFOIL is not on the `PATH`:

```powershell
# Windows PowerShell
$env:XFOIL_EXE = "C:\path\to\xfoil.exe"
```

```bash
# Linux/macOS
export XFOIL_EXE="/opt/xfoil/xfoil"
```

---

## Configuration

### `config/analysis_config.yaml`

Fan geometry (GE9X class), flight conditions, Re per (phase, section), Ncrit and XFOIL settings.

```yaml
fan_geometry:
  rpm: 2200
  radius:      { root: 0.53, mid_span: 1.00, tip: 1.70 }   # [m]
  axial_velocity:
    takeoff: 180.0
    climb:   155.0
    cruise:  150.0
    descent: 125.0

blade_geometry:
  num_blades: 16
  chord:      { root: 0.36, mid_span: 0.46, tip: 0.46 }   # [m]
  theta_camber_deg: 8.0       # NACA 65-410

target_mach:                   # M_rel at mid-span (W/a)
  takeoff: 0.85
  climb:   0.85
  cruise:  0.93
  descent: 0.80

ncrit:                         # Tu ~0.5–1% in fan → Ncrit ≈ 4
  takeoff: 4.0
  climb:   4.0
  cruise:  4.0
  descent: 4.0

reynolds:                      # derived from ρ·W·c/μ per ISA condition
  cruise:   { root: 1.8e6, mid_span: 3.2e6, tip: 5.0e6 }
  takeoff:  { root: 5.3e6, mid_span: 9.1e6, tip: 13.5e6 }
  climb:    { root: 3.4e6, mid_span: 6.0e6, tip: 9.1e6 }
  descent:  { root: 3.4e6, mid_span: 6.5e6, tip: 10.2e6 }

alpha:  { min: -5.0, max: 23.0, step: 0.15 }

airfoil_geometry:
  thickness_ratio: 0.10
  korn_kappa:      0.87        # NACA 6-series

xfoil:
  iter: 200
  timeout_final_s: 180.0
  max_retries: 3
```

### `config/engine_parameters.yaml`

```yaml
baseline_sfc:   0.50            # lb/(lbf·h) — GE9X
fan_efficiency: 0.90
bypass_ratio:  10.0
profile_efficiency_transfer: 0.50   # τ — fraction of 2D gain reaching the fan

sfc_multipliers:
  takeoff: 1.15
  climb:   1.05
  cruise:  1.00
  descent: 1.10

mission:
  phases:
    takeoff: { duration_min:   0.5, thrust_fraction: 1.00 }
    climb:   { duration_min:  20.0, thrust_fraction: 0.75 }
    cruise:  { duration_min: 480.0, thrust_fraction: 0.25 }
    descent: { duration_min:  25.0, thrust_fraction: 0.05 }
  design_thrust_kN: 105.0
  fuel_price_usd_per_kg: 0.90

reverse_thrust:
  n1_fraction: 0.65
  va_landing_m_s: 60.0
  delta_beta_min_deg: -25.0
  delta_beta_max_deg:  -5.0
  delta_beta_steps:    41
  target_thrust_fraction: 0.40
  engine_dry_weight_kg: 7930.0
  mechanism_weight_fraction:       0.04    # VPF actuator
  conventional_reverser_fraction:  0.10    # conventional cascade
  aircraft_L_D: 18.0
```

### `src/vfp_analysis/settings.py` — centralised physical constants

```python
from vfp_analysis.settings import get_settings

s = get_settings()
s.physics.CARTER_M_NACA6     # 0.23  — Carter cascade deviation coefficient (NACA 6-series)
s.physics.SNEL_A             # 3.0   — empirical rotational correction factor (Snel 1994)
s.physics.ALPHA_MIN_OPT_DEG  # 3.0   — minimum angle for optimum search
s.physics.CL_MIN_VIABLE      # 0.70  — minimum CL for viable fan blade operation
s.xfoil.MAX_RETRIES          # 3     — automatic retries per polar
s.xfoil.TIMEOUT_FINAL_S      # 180   — Stage 2 timeout [s]
```

---

## Running the pipeline

### Full pipeline

```bash
python run_analysis.py
```

A summary with key metrics for each stage and generated files is printed at the end.

### Individual stages

```bash
python -m vfp_analysis.stage5_pitch_kinematics.application.run_pitch_kinematics
python -m vfp_analysis.stage6_reverse_thrust.application.run_reverse_thrust
python -m vfp_analysis.stage7_sfc_analysis.application.run_sfc_analysis
```

### Tests

```bash
pytest
pytest tests/test_metrics.py -v
pytest -k "cascade" -v
```

---

## Technical detail per stage

### Stage 1 — Aerofoil selection

Runs XFOIL at cruise conditions (M=0.85, Re_cruise) for each candidate aerofoil defined in `analysis_config.yaml`. Selects the aerofoil with the highest CL/CD at the second peak (α ≥ `ALPHA_MIN_OPT_DEG`). Generates ranking and polar of the winner.

**Output:** `stage1_airfoil_selection/selection/` — polar of the selected aerofoil, ranking CSV.

---

### Stage 2 — Final XFOIL simulations

12 polars (4 conditions × 3 sections) using the selected aerofoil. Each polar is run with automatic retry:

```
for attempt in 0..MAX_RETRIES:
    run XFOIL → capture stdout
    check convergence (regex "Convergence failed")
    if success: break
    sleep(RETRY_WAIT_S)
```

If XFOIL fails after all attempts, a warning is logged and the pipeline continues with the available polars. The parser detects and records quality issues: `LOW_CL_MAX`, `NON_PHYSICAL_CD`, `HIGH_CD_MIN`, `NARROW_ALPHA_RANGE`, `NO_STALL_DETECTED`.

**Output:** `stage2_xfoil_simulations/polars/` — 12 files `polar.dat` + `polar.csv`.

---

### Stage 3 — Compressibility corrections

Applies three correction levels to the Stage 2 2D polars:

| Correction | Equation | Applies to |
|------------|----------|------------|
| Prandtl–Glauert | `CL_PG = CL / √(1−M²)` | CL, CD, CM (M < 0.7) |
| Karman–Tsien | `CL_KT = CL_PG / [β + (M²/2β)·CL_PG/2]` | CL (M up to ~0.8) |
| Korn (wave drag) | `M_dd ≈ κ/cos(Λ) − (t/c)/cos²(Λ) − CL/(10cos³(Λ))` | CD (M > M_dd) |

The Korn wave correction adds CD_wave proportional to `(M − M_dd)⁴` to capture the onset of transonic wave drag.

**Output:** `stage3_compressibility_correction/` — corrected polars with columns `cl_kt`, `cd_corrected`, `ld_kt`.

---

### Stage 4 — Performance metrics

Computes for each of the 12 cases:

- `CL/CD_max` (second peak, α ≥ α_min, CL ≥ CL_MIN_VIABLE)
- `α_opt` — angle at maximum efficiency
- `CL_max` — maximum lift
- `stall_margin` — `α_stall − α_opt`
- `cm_at_opt` — pitching moment at the optimal point
- `alpha_design`, `delta_alpha`, `eff_gain_pct` — VPF benefit vs fixed pitch (cruise reference)

**Output:** `stage4_performance_metrics/tables/metrics_summary.csv`

---

### Stage 5 — Pitch kinematics (3D fan analysis)

The most comprehensive module. Operates in four sub-analyses:

#### A — Cascade correction (Weinig + Carter)

The fan operates with blades in cascade, not as isolated aerofoils. Solidity σ = c/s (s = 2πr/Z) determines the magnitude of the effect.

```
s(r)        = 2πr / Z
σ(r)        = c(r) / s(r)

K_weinig(σ) = (π/2·σ) / arctan(π·σ/2)   — CL slope factor
CL_cascade  = CL_2D · K_weinig

δ_carter(r) = m · θ / √σ(r)   — outlet deviation [°]
  m = 0.23  (NACA 6-series, a/c = 0.5)   [Carter 1950, NACA TN-2273]
```

Effect on our geometry: root (σ ≈ 1.7) → K_weinig ≈ 0.76; tip (σ ≈ 0.35) → K_weinig ≈ 0.97.

#### B — 3D rotational corrections (Snel)

Rotation creates Coriolis forces and centrifugal gradients that increase CL and delay stall, with the effect proportional to (c/r)².

```
ΔCL_rot(r) = a · (c/r)² · CL_2D      a = 3.0  [Snel et al. 1994]
CL_3D      = CL_cascade + ΔCL_rot
CD_3D      ≈ CD_cascade               (drag correction < 2%, negligible)
```

Magnitudes: root ≈ +8% CL, mid ≈ +1.7%, tip ≈ +0.5%.

#### C — Design twist and off-design trade-off

With a single actuator rotating the entire blade, only one section can be at its individual α_opt in each condition. The analysis quantifies the penalty:

```
φ_flow(r)   = arctan(Va / U(r))
β_metal(r)  = α_opt_3D_cruise(r) + φ_flow(r)   — mechanical design angle
twist_total = β_metal(root) − β_metal(tip)       [°]

# Off-design:
α_actual(r, cond)       = β_metal(r) + Δβ_hub(cond) − φ_flow(r, cond)
Δα_compromise(r, cond)  = α_actual − α_opt_3D(r, cond)
loss_pct(r, cond)       = 1 − (CL/CD)[α_actual] / (CL/CD)_max_3D
```

#### D — Stage loading (Euler, φ, ψ) — ideal vs real scenario

```
φ(r)    = Va / U(r)                   — flow coefficient
V_θ(r)  = U − Va / tan(β_mech_3D)    — imparted tangential velocity
ψ(r)    = V_θ / U                     — work coefficient
W_spec  = U · V_θ   [J/kg]           — specific work (Euler equation)
```

The analysis publishes **two tables** to make the VPF trade-off explicit:

- `stage_loading.csv` — **ideal** scenario (free pitch per condition, α = α_opt_3D).
- `stage_loading_single_actuator.csv` — **real** scenario (one β_metal + one Δβ_hub per phase, α = α_actual).

Cruise and mid-span coincide in both (hub_section optimised, Δβ_hub=0 at reference). At root/tip off-cruise, the single actuator forces α above α_opt → higher ψ at the cost of L/D.

**Note on the Dixon & Hall design zone** (φ ∈ [0.35, 0.55], ψ ∈ [0.25, 0.50]): it is sized for a **fixed-pitch** fan delivering PR≈1.7 (ψ_tip≈0.37) requiring α ≈ 6–10° with L/D≈7. The VPF operates at α_opt ≈ 1–3° with L/D ≈ 11–19: it trades ψ (less turning per stage) for superior aerodynamic efficiency per section. VPF points falling outside the zone are not a failure — they are the manifestation of the value of variable pitch. The `in_design_zone` flag is informative, not prescriptive. The physical interpretation is detailed in block [E] of `pitch_kinematics_summary.txt`.

**Stage 5 outputs:**

| CSV table | Contents |
|-----------|----------|
| `cascade_corrections.csv` | σ, s, K_weinig, δ_carter, CL_2D vs CL_cascade |
| `rotational_corrections.csv` | c/r, ΔCL_snel, α_opt_2D vs α_opt_3D, CL/CD_2D vs CL/CD_3D |
| `rotational_corrections_du_selig.csv` | Du-Selig model comparative with Snel |
| `optimal_incidence.csv` | α_opt_3D per condition and section |
| `pitch_adjustment.csv` | Δα_3D, Δβ_mech_3D |
| `blade_twist_design.csv` | β_metal(r), φ_flow(r), twist_from_tip |
| `off_design_incidence.csv` | α_actual, Δα_compromise, efficiency_loss_pct |
| `kinematics_analysis.csv` | Velocity triangles Va/U/W/β per case |
| `stage_loading.csv` | φ, ψ, W_spec, in_design_zone — **ideal scenario** |
| `stage_loading_single_actuator.csv` | Same layout — **real scenario (single actuator)** |

---

### Stage 6 — Reverse thrust

The VPF achieves reverse thrust by rotating the blade pitch to negative angles **while keeping the fan rotation direction**: no blocker doors or nozzle cascades are needed as in a conventional reverser.

**Operating conditions during ground roll:**

- `N1_fraction = 0.65` (fan at 65% of design RPM)
- `Va_landing = 60 m/s` (averaged over the ground roll; reversers engaged ≈ 75 m/s)
- ρ = 1.225 kg/m³ (sea level)

**Pitch sweep and optimisation criterion:**

```
Δβ ∈ [−25°, −5°], 41 points
Thrust_rev(r, Δβ) = ρ · Va · Ω · r · c · Z · (CL sin β − CD cos β)
Target: |Thrust_rev| ≥ 0.40 · Thrust_takeoff_forward, stall_margin ≥ 0
```

The Stage 5 3D polars are re-evaluated at negative α via symmetric extrapolation (the NACA 65-410 is non-symmetric, but the CL(α) curve maintains linear slope up to reverse stall). The service finds the optimal Δβ that maximises reverse thrust while maintaining positive stall margin across all three sections.

**Mechanism weight comparison:**

```
W_VPF,actuator  = 0.04 · W_dry_engine              — ring + links + reinforced root
W_cascade_conv  = 0.10 · W_dry_engine              — cascades + doors + nacelle reinforcement
Δ fuel burn from weight saving ≈ Δw / (L/D) · mission_range
```

**Outputs:** `stage6_reverse_thrust/` — 4 tables (`reverse_thrust_sweep`, `reverse_thrust_optimal`, `reverse_kinematics`, `mechanism_weight`) and 4 figures (`thrust_vs_pitch_sweep`, `efficiency_and_stall_margin`, `spanwise_thrust_at_optimum`, `mechanism_weight_comparison`).

---

### Stage 7 — SFC and mission analysis

Efficiency transfer model from 2D aerofoil section to complete fan:

```
ε(r, cond)    = (CL/CD)_vpf(r, cond) / (CL/CD)_fixed_ref(r, cond)   — improvement ratio
ε̄(cond)       = radially-weighted mean of ε
Δη_fan(cond)  = τ · (ε̄ − 1) · η_fan,base             — damped 2D→3D gain
η_fan,new     = η_fan,base + Δη_fan
SFC_new       = SFC_base / (1 + Δη_fan / η_fan,base)
ΔSFC [%]      = (SFC_base − SFC_new) / SFC_base · 100
```

`τ` (profile_efficiency_transfer ≈ 0.5) damps the ideal 2D gain to reflect 3D losses (tip clearance, secondary flows, shocks) not captured in the isolated-section analysis.

**Fixed-pitch reference:** cruise optimal pitch is assumed (ε_cruise ≡ 1). At takeoff/climb/descent, ε reflects the genuine VPF gain from reconfiguring α per phase.

**Mission integration:** fuel burn and cost are aggregated per phase using `thrust_fraction` and `duration_min` from `mission.phases`, and sensitivity to τ ∈ [0.3, 0.7] is computed.

**Outputs:** `stage7_sfc_analysis/` — 4 tables (`sfc_analysis`, `sfc_section_breakdown`, `sfc_sensitivity`, `mission_fuel_burn`) and 7 figures (`sfc_combined`, `fan_efficiency_improvement`, `fixed_vs_vpf_efficiency`, `epsilon_spanwise`, `sfc_sensitivity_tau`, `efficiency_mechanism_breakdown`, `mission_fuel_burn`). Stage 7 **does not consume ψ** from Stage 5 — it uses ε (L/D ratios) and φ, so the low VPF ψ values do not propagate to the SFC.

---

## Module dependency rules

```
settings.py          ← all code (unique physical constants)
config_loader.py     ← run_analysis.py, stages, services
validation/          ← adapters, postprocessing, run_analysis.py
pipeline/contracts.py← run_analysis.py (inter-stage contract validation)
stage5/.../services/ ← run_pitch_kinematics.py (orchestrator)
postprocessing/      ← run_analysis.py (figures and summaries)
```

No stage imports directly from another stage. Communication is exclusively through files in `results/` and the `StageNResult` contracts.

---

## Pipeline outputs

| Stage | Tables | Figures | Text |
|-------|--------|---------|------|
| 1 | ranking.csv, best_airfoil.csv | polar_best.png | selection_summary.txt |
| 2 | polar.csv × 12 | efficiency, cl_alpha_stall, polar × 12 | — |
| 3 | corrected_polar.csv × 12 | comparison_2d_3d × 12 | — |
| 4 | metrics_summary.csv | metrics_heatmap, efficiency_gain | — |
| 5 | 10 CSV (see Stage 5 table) | 20 figures | pitch_kinematics_summary.txt, finalresults_stage5.txt |
| 6 | 4 CSV (reverse_thrust_*) | 4 figures | reverse_thrust_summary.txt |
| 7 | 4 CSV (sfc_*, mission_*) | 7 figures | sfc_analysis_summary.txt, finalresults_stage7.txt |

---

## Physical constants and references

| Symbol | Value | Description | Reference |
|--------|-------|-------------|-----------|
| m (Carter) | 0.23 | Cascade deviation coefficient (NACA 6-series, a/c=0.5) | Carter (1950), NACA TN-2273 |
| a (Snel) | 3.0 | Empirical rotational correction factor (attached flow) | Snel et al. (1994) |
| α_min_opt | 3.0° | Minimum angle for second CL/CD peak search | Calibrated with XFOIL NACA 6-series |
| CL_min_viable | 0.70 | Minimum CL for viable fan blade operation | Typical fan range: CL ∈ [0.7, 1.2] |
| CL_max_fan | 0.96 | Fan efficiency cap (physical upper bound) | Cumpsty (2004) |
| φ_design | [0.35, 0.55] | Flow coefficient in design zone | Dixon & Hall (2013), ch. 5 |
| ψ_design | [0.25, 0.50] | Work coefficient in design zone | Dixon & Hall (2013), ch. 5 |

**Main bibliography:**
- Dixon & Hall (2013): *Fluid Mechanics and Thermodynamics of Turbomachinery*, 7th ed.
- Cumpsty (2004): *Compressor Aerodynamics*
- Saravanamuttoo et al. (2017): *Gas Turbine Theory*, 6th ed.
- Carter (1950): *The Low Speed Performance of Related Aerofoils in Cascade*, NACA TN-2273
- Snel, Houwink & Bosschers (1994): *Sectional Prediction of Lift Coefficients on Rotating Wind Turbine Blades*
- Du & Selig (1998): *A 3-D Stall-Delay Model for Horizontal Axis Wind Turbine Performance Prediction*, AIAA 98-0021
- Drela (1989): XFOIL — MIT, http://web.mit.edu/drela/Public/web/xfoil/
- ESDU 05017: *Profile Losses and Deviation in Axial Compressor and Fan Blade Rows*
