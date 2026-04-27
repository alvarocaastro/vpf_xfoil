"""Tests for Viterna-Corrigan post-stall extrapolation in reverse thrust."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vpf_analysis.stage6_reverse_thrust.reverse_thrust_core import (
    _get_aero_coeffs,
    _viterna_extrapolate,
)


def _make_polar(alpha_min: float = -5.0, alpha_max: float = 17.0) -> pd.DataFrame:
    """Synthetic polar covering [alpha_min, alpha_max]."""
    alphas = np.linspace(alpha_min, alpha_max, 23)
    cl = 0.1 * alphas  # linear lift slope
    cd = 0.01 + 0.001 * alphas**2
    return pd.DataFrame({"alpha": alphas, "cl_kt": cl, "cd_corrected": cd})


class TestViternaExtrapolate:
    def test_at_alpha_minus90_cd_near_maximum(self) -> None:
        """At α = −90°, CD should equal cd_max (full drag plate)."""
        cl, cd = _viterna_extrapolate(
            alpha_deg=-90.0,
            cl_stall=-0.5,
            cd_stall=0.05,
            alpha_stall_deg=-5.0,
        )
        # At α = −90°: sin²(α) = 1, cos(α) = 0 → CD = B1 * 1 + B2 * 0 = cd_max
        cd_max = min(1.11 + 0.018 * (2.0 / 0.05), 2.0)
        assert cd == pytest.approx(cd_max, abs=1e-3)

    def test_at_alpha_minus45_physical_bounds(self) -> None:
        """At α = −45° (deep stall), CL and CD must be within physical bounds."""
        cl, cd = _viterna_extrapolate(
            alpha_deg=-45.0,
            cl_stall=-0.4,
            cd_stall=0.04,
            alpha_stall_deg=-5.0,
        )
        assert -2.0 <= cl <= 2.0
        assert 0.0 <= cd <= 2.0

    def test_at_alpha_minus90_cl_near_zero(self) -> None:
        """At α = −90° (flat plate perpendicular to flow), CL must be near 0.

        Viterna: CL = 0.5*A1*sin(2α) + A2*cos²(α)/sin(α).
        At α = −90°: sin(−180°) = 0, cos²(−90°) = 0 → CL = 0.
        """
        cl, _ = _viterna_extrapolate(
            alpha_deg=-90.0,
            cl_stall=-0.5,
            cd_stall=0.05,
            alpha_stall_deg=-5.0,
        )
        assert abs(cl) < 0.01


class TestGetAeroCoeffs:
    def test_inside_range_returns_interpolated_and_in_range_true(self) -> None:
        df = _make_polar()
        cl, cd, in_range = _get_aero_coeffs(df, alpha_deg=5.0)
        assert in_range is True
        assert cl == pytest.approx(0.5, abs=0.05)

    def test_outside_range_returns_in_range_false(self) -> None:
        df = _make_polar()
        _, _, in_range = _get_aero_coeffs(df, alpha_deg=-20.0)
        assert in_range is False

    def test_deep_stall_extrapolation_physical(self) -> None:
        """Viterna result at α = −20° must be physically bounded."""
        df = _make_polar()
        cl, cd, in_range = _get_aero_coeffs(df, alpha_deg=-20.0)
        assert in_range is False
        assert -2.0 <= cl <= 2.0
        assert 0.0 <= cd <= 2.0

    def test_boundary_alpha_exact_min_is_in_range(self) -> None:
        """Alpha exactly at polar minimum must use interpolation, not extrapolation."""
        df = _make_polar(alpha_min=-5.0)
        _, _, in_range = _get_aero_coeffs(df, alpha_deg=-5.0)
        assert in_range is True
