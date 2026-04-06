"""
High-level package for Variable Pitch Fan airfoil analysis using XFOIL.

Modules
-------
- config: global constants, airfoil definitions and paths.
- flight_conditions: definition of representative flight phases.
- xfoil_runner: thin subprocess-based wrapper around the XFOIL binary.
- analysis: orchestration of airfoil × condition sweeps and post-processing.
- export: export of polars and summary tables to CSV for LaTeX.
- plotting: generation of publication-quality figures.
- main: simple CLI entry point to run the complete pipeline.
"""

from . import config  # noqa: F401

