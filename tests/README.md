# Test Suite Documentation

## Overview

This test suite provides comprehensive unit tests for the VFP Analysis project using pytest.

## Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── test_reynolds.py         # Reynolds number calculation
├── test_prandtl_glauert.py  # Compressibility correction
├── test_efficiency.py       # Aerodynamic efficiency (CL/CD)
├── test_airfoil_reader.py   # Airfoil .dat file reading
└── test_airfoil_selection.py # Airfoil selection algorithm
```

## Running Tests

### Run All Tests

```bash
pytest
```

### Run Specific Test File

```bash
pytest tests/test_reynolds.py
```

### Run with Verbose Output

```bash
pytest -v
```

### Run with Coverage

```bash
pytest --cov=src/vfp_analysis --cov-report=html
```

## Test Files

### `test_reynolds.py`

Tests for Reynolds number calculation:
- Typical atmospheric values
- Small velocity cases
- Larger chord values
- Edge cases (zero/negative inputs)

### `test_prandtl_glauert.py`

Tests for Prandtl-Glauert compressibility correction:
- Correction increases with Mach number
- Mach = 0 returns original value
- Invalid Mach numbers (>= 1.0) raise errors
- Beta calculation correctness

### `test_efficiency.py`

Tests for aerodynamic efficiency calculation:
- Correct numerical results
- Small drag value handling
- Division by zero protection
- Parameterized test cases

### `test_airfoil_reader.py`

Tests for airfoil .dat file reading:
- Coordinates loaded correctly
- Number of points is reasonable
- X coordinates within [0, 1]
- Parser handles valid files without crashing

### `test_airfoil_selection.py`

Tests for airfoil selection algorithm:
- Selection based on max(CL/CD)
- Selection based on stall angle
- Selection based on average drag
- Deterministic behavior

## Fixtures

Shared fixtures are defined in `conftest.py`:
- `project_root`: Project root directory
- `data_dir`: Data directory path
- `sample_airfoil_dat`: Sample airfoil .dat file path
- `sample_airfoil`: Sample Airfoil instance
- `sample_simulation_condition`: Sample SimulationCondition
- `sample_polar_data`: Sample polar DataFrame
- `empty_polar_data`: Empty polar DataFrame

## Best Practices

- Each test verifies a single behavior
- Tests are deterministic and fast
- Descriptive test names
- Use fixtures to avoid code duplication
- Parameterized tests for multiple cases
- Edge cases are tested

## Continuous Integration

Tests can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run tests
  run: pytest
```
