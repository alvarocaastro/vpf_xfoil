"""
Tests for Reynolds number calculation.

Reynolds number formula: Re = (rho * V * c) / mu

Where:
- rho: air density [kg/m³]
- V: velocity [m/s]
- c: chord length [m]
- mu: dynamic viscosity [Pa·s]
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def calculate_reynolds(
    density: float, velocity: float, chord: float, viscosity: float
) -> float:
    """
    Calculate Reynolds number.

    Parameters
    ----------
    density : float
        Air density in kg/m³.
    velocity : float
        Velocity in m/s.
    chord : float
        Chord length in meters.
    viscosity : float
        Dynamic viscosity in Pa·s.

    Returns
    -------
    float
        Reynolds number (dimensionless).
    """
    if viscosity <= 0:
        raise ValueError("Viscosity must be positive")
    if density < 0:
        raise ValueError("Density cannot be negative")
    if velocity < 0:
        raise ValueError("Velocity cannot be negative")
    if chord <= 0:
        raise ValueError("Chord must be positive")

    return (density * velocity * chord) / viscosity


class TestReynoldsCalculation:
    """Test suite for Reynolds number calculation."""

    # Standard atmospheric conditions at sea level (15°C)
    RHO_STD = 1.225  # kg/m³
    MU_STD = 1.789e-5  # Pa·s

    def test_typical_atmospheric_values(self) -> None:
        """Test Reynolds calculation with typical atmospheric values."""
        velocity = 100.0  # m/s
        chord = 0.5  # m

        reynolds = calculate_reynolds(
            self.RHO_STD, velocity, chord, self.MU_STD
        )

        # Expected: (1.225 * 100 * 0.5) / 1.789e-5 ≈ 3.42e6
        expected = (self.RHO_STD * velocity * chord) / self.MU_STD
        assert reynolds == pytest.approx(expected, rel=1e-6)
        assert reynolds > 0

    def test_small_velocity(self) -> None:
        """Test Reynolds calculation with small velocity."""
        velocity = 10.0  # m/s
        chord = 0.5  # m

        reynolds = calculate_reynolds(
            self.RHO_STD, velocity, chord, self.MU_STD
        )

        # Should be 10x smaller than typical case
        assert reynolds > 0
        assert reynolds < 1e6

    def test_larger_chord_values(self) -> None:
        """Test Reynolds calculation with larger chord values."""
        velocity = 100.0  # m/s
        chord = 2.0  # m (larger chord)

        reynolds = calculate_reynolds(
            self.RHO_STD, velocity, chord, self.MU_STD
        )

        # Should be 4x larger than typical case (chord 0.5m)
        assert reynolds > 0
        assert reynolds > 1e6

    def test_result_is_positive(self) -> None:
        """Verify that Reynolds number is always positive for valid inputs."""
        test_cases = [
            (1.0, 10.0, 0.1, 1e-5),
            (1.225, 50.0, 0.3, 1.789e-5),
            (0.5, 200.0, 1.0, 2e-5),
        ]

        for density, velocity, chord, viscosity in test_cases:
            reynolds = calculate_reynolds(density, velocity, chord, viscosity)
            assert reynolds > 0, f"Reynolds should be positive for inputs: {test_cases}"

    @pytest.mark.parametrize(
        "density,velocity,chord,viscosity,expected_re",
        [
            (1.225, 100.0, 0.5, 1.789e-5, 3.42e6),
            (1.225, 50.0, 1.0, 1.789e-5, 3.42e6),  # Same Re, different V and c
            (1.0, 10.0, 0.1, 1e-5, 1e5),
        ],
    )
    def test_parameterized_cases(
        self,
        density: float,
        velocity: float,
        chord: float,
        viscosity: float,
        expected_re: float,
    ) -> None:
        """Test multiple Reynolds calculation cases using parametrization."""
        reynolds = calculate_reynolds(density, velocity, chord, viscosity)
        assert reynolds == pytest.approx(expected_re, rel=0.01)

    def test_zero_viscosity_raises_error(self) -> None:
        """Test that zero viscosity raises ValueError."""
        with pytest.raises(ValueError, match="Viscosity must be positive"):
            calculate_reynolds(1.225, 100.0, 0.5, 0.0)

    def test_negative_viscosity_raises_error(self) -> None:
        """Test that negative viscosity raises ValueError."""
        with pytest.raises(ValueError, match="Viscosity must be positive"):
            calculate_reynolds(1.225, 100.0, 0.5, -1e-5)

    def test_zero_chord_raises_error(self) -> None:
        """Test that zero chord raises ValueError."""
        with pytest.raises(ValueError, match="Chord must be positive"):
            calculate_reynolds(1.225, 100.0, 0.0, 1.789e-5)

    def test_negative_chord_raises_error(self) -> None:
        """Test that negative chord raises ValueError."""
        with pytest.raises(ValueError, match="Chord must be positive"):
            calculate_reynolds(1.225, 100.0, -0.5, 1.789e-5)

    def test_negative_velocity_raises_error(self) -> None:
        """Test that negative velocity raises ValueError."""
        with pytest.raises(ValueError, match="Velocity cannot be negative"):
            calculate_reynolds(1.225, -100.0, 0.5, 1.789e-5)

    def test_negative_density_raises_error(self) -> None:
        """Test that negative density raises ValueError."""
        with pytest.raises(ValueError, match="Density cannot be negative"):
            calculate_reynolds(-1.225, 100.0, 0.5, 1.789e-5)
