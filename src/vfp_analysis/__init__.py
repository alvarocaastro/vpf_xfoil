"""
High-level package for Variable Pitch Fan airfoil analysis using XFOIL.

Modules
-------
- config: global constants, airfoil definitions and paths.
- xfoil_runner: thin subprocess-based wrapper around the XFOIL binary.
- stage1_airfoil_selection: candidate comparison and airfoil scoring.
- stage2_xfoil_simulations: XFOIL sweeps and polar organisation.
- stage3_compressibility_correction: Prandtl-Glauert correction pipeline.
- stage4_performance_metrics: metrics extraction and CSV export.
- stage5_publication_figures: thesis-ready figure generation.
- stage6_vpf_analysis: optimal incidence and aerodynamic pitch deltas.
- stage7_kinematics_analysis: velocity triangles and mechanical pitch.
- stage8_sfc_analysis: fan efficiency transfer and SFC estimation.
"""

from . import settings  # noqa: F401
