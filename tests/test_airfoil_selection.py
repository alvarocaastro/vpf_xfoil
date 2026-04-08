"""
Tests for airfoil selection logic.

Verifies that the scoring system uses the second efficiency peak and rewards
incidence stability around the operating point.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vfp_analysis.stage1_airfoil_selection.scoring import AirfoilScore, score_airfoil


class TestAirfoilSelection:
    """Test suite for airfoil selection algorithm."""

    def test_selection_uses_second_efficiency_peak(self) -> None:
        """Low-alpha artefacts must not dominate the score."""
        df = pd.DataFrame(
            {
                "airfoil": ["Airfoil A"] * 6,
                "alpha": [0.0, 2.0, 4.0, 6.0, 8.0, 10.0],
                "cl": [0.2, 0.4, 0.7, 0.9, 1.0, 0.95],
                "cd": [0.010, 0.012, 0.010, 0.0105, 0.0120, 0.0150],
                "ld": [25.0, 40.0, 70.0, 85.0, 83.0, 63.33],
            }
        )

        score = score_airfoil(df)

        assert score.alpha_opt == pytest.approx(6.0, abs=1e-6)
        assert score.max_ld == pytest.approx(85.0, abs=1e-6)

    def test_selection_rewards_stall_margin(self) -> None:
        """Later stall should improve the score when efficiency is similar."""
        df_a = pd.DataFrame(
            {
                "airfoil": ["Airfoil A"] * 6,
                "alpha": [0.0, 4.0, 6.0, 8.0, 10.0, 12.0],
                "cl": [0.2, 0.7, 0.95, 1.10, 1.20, 1.15],
                "cd": [0.02, 0.014, 0.012, 0.013, 0.016, 0.020],
                "ld": [10.0, 50.0, 79.17, 84.62, 75.0, 57.5],
            }
        )
        df_b = pd.DataFrame(
            {
                "airfoil": ["Airfoil B"] * 6,
                "alpha": [0.0, 4.0, 6.0, 8.0, 10.0, 12.0],
                "cl": [0.2, 0.7, 0.95, 1.05, 0.95, 0.85],
                "cd": [0.02, 0.014, 0.012, 0.0125, 0.016, 0.020],
                "ld": [10.0, 50.0, 79.17, 84.0, 59.38, 42.5],
            }
        )

        score_a = score_airfoil(df_a)
        score_b = score_airfoil(df_b)

        assert score_a.stall_alpha == pytest.approx(10.0, abs=1e-6)
        assert score_b.stall_alpha == pytest.approx(8.0, abs=1e-6)
        assert score_a.stability_margin > score_b.stability_margin
        assert score_a.total_score > score_b.total_score

    def test_selection_rewards_robust_operating_window(self) -> None:
        """A broader efficiency plateau should beat a sharp isolated spike."""
        df_plateau = pd.DataFrame(
            {
                "airfoil": ["Plateau"] * 6,
                "alpha": [0.0, 4.0, 5.0, 6.0, 7.0, 9.0],
                "cl": [0.2, 0.7, 0.85, 1.0, 1.1, 1.2],
                "cd": [0.02, 0.0135, 0.012, 0.012, 0.0128, 0.017],
                "ld": [10.0, 51.85, 70.83, 83.33, 85.94, 70.59],
            }
        )
        df_spike = pd.DataFrame(
            {
                "airfoil": ["Spike"] * 6,
                "alpha": [0.0, 4.0, 5.0, 6.0, 7.0, 9.0],
                "cl": [0.2, 0.7, 0.84, 1.0, 1.05, 1.15],
                "cd": [0.02, 0.0135, 0.0108, 0.0140, 0.0168, 0.021],
                "ld": [10.0, 51.85, 77.78, 71.43, 62.5, 54.76],
            }
        )

        score_plateau = score_airfoil(df_plateau)
        score_spike = score_airfoil(df_spike)

        assert score_plateau.robustness_ld > score_spike.robustness_ld
        assert score_plateau.total_score > score_spike.total_score

    def test_selection_is_deterministic(self) -> None:
        """Verify that selection logic is deterministic (same input = same output)."""
        df = pd.DataFrame(
            {
                "airfoil": ["Test Airfoil"] * 6,
                "alpha": [0.0, 4.0, 5.0, 6.0, 7.0, 9.0],
                "cl": [0.2, 0.7, 0.85, 1.0, 1.1, 1.0],
                "cd": [0.02, 0.0135, 0.012, 0.012, 0.0128, 0.017],
                "ld": [10.0, 51.85, 70.83, 83.33, 85.94, 58.82],
            }
        )

        score1 = score_airfoil(df)
        score2 = score_airfoil(df)
        score3 = score_airfoil(df)

        assert score1.total_score == score2.total_score == score3.total_score
        assert score1.max_ld == score2.max_ld == score3.max_ld
        assert score1.alpha_opt == score2.alpha_opt == score3.alpha_opt
        assert score1.stability_margin == score2.stability_margin == score3.stability_margin
        assert score1.robustness_ld == score2.robustness_ld == score3.robustness_ld

    def test_empty_dataframe_returns_nan_scores(self) -> None:
        """Test that empty DataFrame returns NaN scores."""
        empty_df = pd.DataFrame(columns=["airfoil", "alpha", "cl", "cd", "ld"])

        score = score_airfoil(empty_df)

        assert np.isnan(score.total_score)
        assert np.isnan(score.max_ld)
        assert np.isnan(score.alpha_opt)
        assert np.isnan(score.stall_alpha)
        assert np.isnan(score.stability_margin)
        assert np.isnan(score.robustness_ld)
        assert score.airfoil == ""

    def test_dataframe_with_invalid_ld_handled_correctly(self) -> None:
        """Test that DataFrame with invalid L/D values (inf, nan) is handled."""
        df = pd.DataFrame(
            {
                "airfoil": ["Test"] * 6,
                "alpha": [0.0, 4.0, 5.0, 6.0, 7.0, 9.0],
                "cl": [0.2, 0.7, 0.85, 1.0, 1.1, 1.0],
                "cd": [0.02, 0.0135, 0.0, 0.012, 0.0128, 0.017],
                "ld": [10.0, 51.85, np.inf, 83.33, 85.94, 58.82],
            }
        )

        score = score_airfoil(df)

        assert not np.isnan(score.total_score)
        assert score.max_ld > 0

    def test_best_airfoil_selected_from_multiple_candidates(self) -> None:
        """Test that a balanced high-efficiency profile can beat a symmetric profile."""
        airfoils_data = [
            {
                "name": "Fan Candidate",
                "df": pd.DataFrame(
                    {
                        "airfoil": ["Fan Candidate"] * 6,
                        "alpha": [0.0, 4.0, 5.0, 6.0, 7.0, 9.0],
                        "cl": [0.2, 0.7, 0.9, 1.05, 1.15, 1.20],
                        "cd": [0.02, 0.0135, 0.0113, 0.0107, 0.0116, 0.0175],
                        "ld": [10.0, 51.85, 79.65, 98.13, 99.14, 68.57],
                    }
                ),
            },
            {
                "name": "Symmetric Stable",
                "df": pd.DataFrame(
                    {
                        "airfoil": ["Symmetric Stable"] * 6,
                        "alpha": [0.0, 4.0, 6.0, 8.0, 10.0, 12.0],
                        "cl": [0.2, 0.7, 0.95, 1.08, 1.18, 1.20],
                        "cd": [0.02, 0.0135, 0.0118, 0.0117, 0.0138, 0.0175],
                        "ld": [10.0, 51.85, 80.51, 92.31, 85.51, 68.57],
                    }
                ),
            },
        ]

        scores = [score_airfoil(data["df"]) for data in airfoils_data]
        best_score = max(scores, key=lambda s: s.total_score)

        assert best_score.airfoil == "Fan Candidate"
        assert best_score.max_ld == pytest.approx(99.14, abs=1e-2)

    def test_score_airfoil_returns_correct_airfoil_name(self) -> None:
        """Test that score_airfoil correctly extracts and returns airfoil name."""
        df = pd.DataFrame(
            {
                "airfoil": ["NACA 65-410"] * 6,
                "alpha": [0.0, 4.0, 5.0, 6.0, 7.0, 9.0],
                "cl": [0.2, 0.7, 0.85, 1.0, 1.1, 1.0],
                "cd": [0.02, 0.0135, 0.012, 0.012, 0.0128, 0.017],
                "ld": [10.0, 51.85, 70.83, 83.33, 85.94, 58.82],
            }
        )

        score = score_airfoil(df)

        assert score.airfoil == "NACA 65-410"

    def test_score_components_are_correct(self) -> None:
        """Test that the score components are computed from the operating region."""
        df = pd.DataFrame(
            {
                "airfoil": ["Test"] * 6,
                "alpha": [0.0, 4.0, 5.0, 6.0, 7.0, 9.0],
                "cl": [0.2, 0.7, 0.85, 1.0, 1.1, 1.0],
                "cd": [0.02, 0.0135, 0.012, 0.012, 0.0128, 0.017],
                "ld": [10.0, 51.85, 70.83, 83.33, 85.94, 58.82],
            }
        )

        score = score_airfoil(df)

        assert score.max_ld == pytest.approx(85.94, abs=1e-2)
        assert score.alpha_opt == pytest.approx(7.0, abs=1e-6)
        assert score.stall_alpha == pytest.approx(7.0, abs=1e-6)
        assert score.stability_margin == pytest.approx(0.0, abs=1e-6)

        window = [83.33, 85.94]
        assert score.robustness_ld == pytest.approx(sum(window) / len(window), abs=1e-2)
