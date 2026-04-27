# Design Decisions

This document records technical decisions that are not immediately obvious from the code alone.

## 1. Solidity as the Primary Blade Geometry Parameter

Decision: `blade_geometry` in `analysis_config.yaml` uses `solidity` (`sigma`) rather than chord length as the main blade-geometry input.

Reason: in Stages 5 to 7, chord mainly appears through non-dimensional relationships:

| Relationship | Use |
|---|---|
| `sigma = c * Z / (2*pi*r)` | Weinig cascade factor and Carter deviation. |
| `c/r = sigma * 2*pi/Z` | Snel rotational correction. |

Consequence: for cascade and rotational corrections, the result depends on `sigma` and blade count `Z`, not directly on the absolute fan scale. When dimensional chord is required, it is recovered with:

```python
c = sigma * 2 * math.pi * r / Z
```

## 2. Reynolds Numbers Declared in YAML

Decision: Reynolds numbers are specified as a `{condition: {section: Re}}` lookup table.

Reason: Reynolds number depends on atmosphere, relative velocity, chord, RPM, and viscosity. Declaring it explicitly makes the derivation auditable and allows deliberate scenario overrides without adding a runtime atmosphere model.

Risk: if fan geometry changes, Reynolds values do not update automatically.

## 3. Canonical `ld_corrected` Column

Decision: Stage 3 writes `ld_corrected` as the canonical corrected-efficiency column.

Reason: downstream stages can locate the corrected lift-to-drag ratio without knowing which stage produced the polar. Column resolution is centralized in `postprocessing/aerodynamics_utils.py`.

## 4. Split Aerodynamic and Engine Configuration

Decision: `analysis_config.yaml` and `engine_parameters.yaml` are separate.

| File | Changes When |
|---|---|
| `analysis_config.yaml` | Fan geometry, aerodynamic conditions, XFOIL setup, or airfoils change. |
| `engine_parameters.yaml` | Engine assumptions, mission model, SFC assumptions, or reverse-thrust assumptions change. |

This reduces accidental coupling between early aerodynamic analysis and later mission/SFC assumptions.

## 5. Centralized Physical Constants

Decision: empirical coefficients such as Carter, Snel, design-zone limits, and SFC caps live in configuration dataclasses, especially `PhysicsConstants`.

Reason: this reduces duplication, prevents silent drift between modules, and makes tests easier to reason about.

## 6. File-Based Stage Communication

Decision: stages exchange information through CSV files and artifacts in `results/`.

Reason: every intermediate result is inspectable, and later stages can be rerun from disk. `pipeline/contracts.py` validates the minimum artifacts required before advancing.

## 7. Second-Peak Efficiency Logic

Decision: `alpha_opt` uses second-peak logic and minimum-CL filters.

Reason: XFOIL can produce low-incidence `CL/CD` peaks caused by laminar-bubble behavior or very small drag values. Such points are not necessarily viable fan-blade operating points.

## 8. Partial Transfer of 2D Gain to SFC

Decision: profile efficiency gains are damped with `profile_efficiency_transfer` (`tau`) and physical caps in Stage 7.

Reason: a 2D airfoil improvement does not transfer perfectly to a real 3D fan because of tip clearance, shocks, secondary flows, distortion, and blade interactions.

## 9. Reverse-Thrust Scope in the Main Flow

Decision: the Stage 6 path called by the main orchestrator computes mechanism weight and SFC impact versus a conventional reverser. BEM sweep and Viterna extrapolation support functions exist, but they are not the main `run_reverse_thrust.py` workflow.

Reason detected from the code: the summary text states that aerodynamic feasibility in reverse requires extended polars or experimental validation. Treat full reverse-thrust aerodynamic prediction as **pending confirmation**.

