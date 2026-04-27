# Glossary

## Project Terms

| Term | Meaning |
|---|---|
| VPF | Variable Pitch Fan. A fan whose blade pitch can be adjusted during operation. |
| Fixed pitch | A fan blade setting that does not change across operating conditions. |
| Stage | A numbered pipeline result phase under `results/stage*_...`. |
| XFOIL | External airfoil analysis program used to generate 2D viscous polars. |
| Polar | Aerodynamic table or curve relating angle of attack, lift, drag, and moment. |
| Airfoil | 2D blade-section profile, such as NACA 65-410. |
| Blade section | Representative radial station: root, mid-span, or tip. |

## Aerodynamic Variables

| Symbol or Name | Meaning |
|---|---|
| `alpha` | Angle of attack in degrees. |
| `alpha_opt` | Angle of attack at selected optimum efficiency. |
| `alpha_design` | Fixed-pitch reference incidence, usually based on cruise. |
| `delta_alpha` | Difference between VPF optimum and fixed-pitch incidence. |
| `CL` or `cl` | Lift coefficient. |
| `CD` or `cd` | Drag coefficient. |
| `CM` or `cm` | Pitching-moment coefficient. |
| `CL/CD`, `ld` | Lift-to-drag ratio, used as aerodynamic efficiency. |
| `ld_corrected` | Canonical corrected lift-to-drag ratio after Stage 3. |
| `cl_pg` | Lift coefficient after Prandtl-Glauert correction. |
| `cl_kt` | Lift coefficient after Karman-Tsien correction. |
| `cd_corrected` | Drag coefficient after correction and wave-drag contribution. |
| `cd_wave_extrapolated` | Wave-drag increment or adjusted drag term from Stage 3. |
| `stall_alpha` | Detected stall-onset angle or angle of maximum lift, depending on context. |
| `stall_margin` | Difference between stall angle and operating optimum. |

## Fan and Blade Variables

| Symbol or Name | Meaning |
|---|---|
| `r` | Blade radius at a section. |
| `c` | Blade chord. |
| `Z` | Number of fan blades. |
| `sigma` | Solidity, `c * Z / (2*pi*r)`. |
| `U` | Tangential blade speed. |
| `Va` | Axial velocity at the fan face. |
| `W_rel` | Relative velocity seen by the blade section. |
| `phi` | Inflow angle from velocity triangle. |
| `beta` | Mechanical or metal pitch angle. |
| `beta_metal` | Blade metal angle at design condition. |
| `delta_beta` | Pitch adjustment. |
| `theta_camber_deg` | Camber angle used in Carter deviation. |
| `c_over_r` | Chord-to-radius ratio used in rotational corrections. |

## Compressibility and Flow Terms

| Term | Meaning |
|---|---|
| Mach | Flow speed divided by local speed of sound. |
| `reference_mach` | Low/reference Mach used for XFOIL baseline. |
| `target_mach` | Mach used for compressibility correction. |
| Prandtl-Glauert | Linear compressibility correction. |
| Karman-Tsien | Nonlinear subsonic compressibility correction. |
| Korn relation | Engineering estimate for drag-divergence Mach. |
| `M_cr` | Critical Mach number estimate. |
| `M_dd` | Drag-divergence Mach estimate. |
| Wave drag | Drag rise associated with compressibility effects near transonic conditions. |

## 3D and Cascade Terms

| Term | Meaning |
|---|---|
| Cascade | Interaction of blade sections in a row of blades rather than isolated airfoils. |
| Weinig factor | Empirical cascade correction factor. |
| Carter deviation | Empirical flow deviation relation for cascades. |
| Snel correction | Empirical 3D rotational lift correction. |
| Du-Selig correction | Alternative empirical 3D rotational correction. |
| `cl_cascade` | Lift after cascade correction. |
| `ld_cascade` | Lift-to-drag after cascade correction. |
| `cl_3d` | Lift after Snel 3D correction. |
| `ld_3d` | Lift-to-drag after Snel 3D correction. |
| `lambda_r` | Local speed ratio used in Du-Selig correction. |

## Stage Loading Terms

| Symbol or Name | Meaning |
|---|---|
| `phi_coeff` | Flow coefficient, typically `Va/U`. |
| `psi_loading` | Work/loading coefficient. |
| `V_theta` | Tangential velocity change component. |
| `W_specific_kJ_kg` | Specific work from Euler turbomachinery relation. |
| Design zone | Reference region for fixed-pitch fan loading, used diagnostically. |

## Propulsion and SFC Terms

| Term | Meaning |
|---|---|
| SFC | Specific Fuel Consumption. |
| `baseline_sfc` | Reference engine SFC. |
| `SFC_new` | Estimated SFC after VPF efficiency effects. |
| `SFC_reduction_percent` | Percentage reduction relative to baseline. |
| `fan_efficiency` | Baseline fan efficiency. |
| `eta_fan_new` | Estimated fan efficiency after VPF. |
| BPR | Bypass ratio. |
| `k_sensitivity` | Bypass sensitivity factor, `BPR/(1+BPR)`. |
| `tau` | Profile efficiency transfer coefficient from 2D gains to fan efficiency. |
| `epsilon` | Ratio `(CL/CD)_vpf / (CL/CD)_fixed`. |
| `epsilon_eff` | Capped effective epsilon used for SFC calculation. |
| `delta_eta_profile` | Fan efficiency gain from profile mechanism. |
| `delta_eta_map` | Fan efficiency gain from fan-map mechanism. |
| `delta_eta_total` | Combined section-level efficiency gain. |

## Mission and Economic Terms

| Term | Meaning |
|---|---|
| Mission phase | Takeoff, climb, cruise, or descent segment. |
| `duration_min` | Mission phase duration in minutes. |
| `thrust_fraction` | Fraction of design thrust used in a phase. |
| `fuel_saving_kg` | Estimated mass of fuel saved. |
| `co2_saving_kg` | Fuel saving converted using a CO2 factor. |
| `cost_saving_usd` | Fuel saving multiplied by configured fuel price. |

## Reverse-Thrust Terms

| Term | Meaning |
|---|---|
| Reverse thrust | Braking thrust generated during landing rollout. |
| Cascade reverser | Conventional thrust reverser with blocker doors and cascade ducts. |
| VPF mechanism | Pitch-change hardware for variable-pitch fan blades. |
| `mechanism_weight_kg` | Estimated VPF mechanism weight for both engines. |
| `conventional_reverser_weight_kg` | Estimated conventional reverser weight for both engines. |
| `sfc_cruise_penalty_pct` | Cruise SFC penalty due to added mechanism weight. |
| `sfc_benefit_vs_conventional_pct` | SFC benefit relative to conventional reverser weight. |
| Viterna-Corrigan | Post-stall extrapolation model present in reverse-thrust support code. |

