# VPF Technical Documentation

## Project Name

**VPF - Variable Pitch Fan Aerodynamic Analysis Pipeline**

## Executive Summary

This repository contains a Python-based technical pipeline for the aerodynamic and propulsion analysis of a variable-pitch fan, using a GE9X-class reference engine. The workflow covers airfoil selection, XFOIL polar generation, compressibility correction, aerodynamic performance metrics, 3D pitch kinematics, a theoretical reverse-thrust mechanism assessment, and specific fuel consumption (SFC) impact estimation.

The project produces reproducible tables, figures, and text summaries under `results/`. This documentation explains how the project is organized, how to run it, what data it uses, what each module does, and how to interpret the generated outputs.

## Project Objective

The goal is to quantify whether a variable-pitch fan can keep blade sections closer to their optimal angle of attack across different flight conditions, and to estimate how that aerodynamic improvement propagates into fan efficiency, SFC, and mission fuel savings.

## Problem Addressed

A fixed-pitch fan is designed around a reference operating point, typically cruise. When axial velocity, fan RPM, and flight condition change, the incoming flow angle changes and the blade no longer operates at its most efficient incidence. This project quantifies that off-design penalty and compares it with a variable-pitch fan concept.

## Workflow Overview

1. Select the best airfoil candidate with XFOIL and a mission-weighted score.
2. Generate final XFOIL polars for four flight conditions and three blade sections.
3. Apply compressibility corrections using Prandtl-Glauert, Karman-Tsien, and wave-drag logic.
4. Compute aerodynamic metrics such as `CL/CD_max`, `alpha_opt`, stall margin, and fixed-pitch penalty.
5. Analyze pitch kinematics, cascade effects, rotational corrections, blade twist, and stage loading.
6. Estimate the weight impact of a VPF reverse-thrust mechanism versus a conventional cascade reverser.
7. Estimate SFC reduction, mission fuel savings, and sensitivity to uncertain transfer parameters.

## Documentation Index

| Document | Purpose |
|---|---|
| `overview.md` | Functional explanation of the project from input to output. |
| `project_structure.md` | Repository structure, relevant folders, and important files. |
| `setup_and_execution.md` | Installation, configuration, execution commands, and common issues. |
| `technical_architecture.md` | Technical architecture, modules, data flow, and dependencies. |
| `data_documentation.md` | Input data, intermediate data, output data, formats, and assumptions. |
| `results.md` | Detailed documentation of generated results, tables, and figures. |
| `code_reference.md` | Reference for scripts, modules, functions, classes, and side effects. |
| `maintenance.md` | Maintenance guidance, extension points, risks, and future improvements. |
| `glossary.md` | Domain terms, variables, metrics, and abbreviations. |
| `design_decisions.md` | Non-obvious technical decisions and rationale. |

## Recommended Reading Order

For a new maintainer:

1. `overview.md`
2. `setup_and_execution.md`
3. `project_structure.md`
4. `technical_architecture.md`
5. `data_documentation.md`
6. `results.md`
7. `code_reference.md`
8. `maintenance.md`
9. `glossary.md`

For output interpretation, start with `results.md`.

## Scope Notes

This documentation is based on the code, configuration files, tests, and generated outputs currently present in the repository. Any ambiguous or incomplete item is marked as **pending confirmation** rather than inferred beyond the local evidence. Source code was not modified while creating this documentation.

