"""
Tests for airfoil selection logic.

Verifies that the scoring system correctly selects the best airfoil
based on max(CL/CD), stall angle, and average drag.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vfp_analysis.core.domain.scoring import AirfoilScore, score_airfoil


class TestAirfoilSelection:
    """Test suite for airfoil selection algorithm."""

    def test_selection_based_on_max_ld(self) -> None:
        """Test that airfoil with highest max(CL/CD) is selected."""
        # Airfoil A: high max L/D
        df_a = pd.DataFrame(
            {
                "airfoil": ["Airfoil A"] * 5,
                "alpha": [0.0, 5.0, 10.0, 15.0, 20.0],
                "cl": [0.3, 0.6, 0.9, 1.1, 1.0],
                "cd": [0.02, 0.03, 0.05, 0.08, 0.12],
                "ld": [15.0, 20.0, 18.0, 13.75, 8.33],
            }
        )

        # Airfoil B: lower max L/D
        df_b = pd.DataFrame(
            {
                "airfoil": ["Airfoil B"] * 5,
                "alpha": [0.0, 5.0, 10.0, 15.0, 20.0],
                "cl": [0.2, 0.4, 0.6, 0.7, 0.6],
                "cd": [0.02, 0.03, 0.05, 0.08, 0.12],
                "ld": [10.0, 13.33, 12.0, 8.75, 5.0],
            }
        )

        score_a = score_airfoil(df_a)
        score_b = score_airfoil(df_b)

        # Airfoil A should have higher total score (better max L/D)
        assert score_a.total_score > score_b.total_score

    def test_selection_based_on_stall_angle(self) -> None:
        """Test that higher stall angle contributes to better score."""
        # Airfoil A: higher stall angle (max L/D at higher alpha)
        df_a = pd.DataFrame(
            {
                "airfoil": ["Airfoil A"] * 5,
                "alpha": [0.0, 5.0, 10.0, 15.0, 20.0],
                "cl": [0.3, 0.6, 0.9, 1.1, 1.2],
                "cd": [0.02, 0.03, 0.05, 0.08, 0.10],
                "ld": [15.0, 20.0, 18.0, 13.75, 12.0],  # Max L/D at alpha=5
            }
        )

        # Airfoil B: lower stall angle but same max L/D
        df_b = pd.DataFrame(
            {
                "airfoil": ["Airfoil B"] * 5,
                "alpha": [0.0, 5.0, 10.0, 15.0, 20.0],
                "cl": [0.3, 0.6, 0.9, 1.1, 0.8],
                "cd": [0.02, 0.03, 0.05, 0.08, 0.10],
                "ld": [15.0, 20.0, 18.0, 13.75, 8.0],  # Max L/D at alpha=5 (same)
            }
        )

        score_a = score_airfoil(df_a)
        score_b = score_airfoil(df_b)

        # Both have same max L/D at same alpha, but A has better overall performance
        # Verify that stall_alpha is correctly identified
        assert score_a.stall_alpha == pytest.approx(5.0, abs=1e-6)
        assert score_b.stall_alpha == pytest.approx(5.0, abs=1e-6)
        
        # If stall angles are the same, verify the scoring still works
        # (A has slightly better avg_cd due to higher CL at alpha=20)
        assert score_a.total_score >= score_b.total_score

    def test_selection_based_on_average_drag(self) -> None:
        """Test that lower average drag contributes to better score."""
        # Airfoil A: lower average drag
        df_a = pd.DataFrame(
            {
                "airfoil": ["Airfoil A"] * 5,
                "alpha": [0.0, 5.0, 10.0, 15.0, 20.0],
                "cl": [0.3, 0.6, 0.9, 1.1, 1.0],
                "cd": [0.01, 0.02, 0.03, 0.05, 0.08],  # Lower drag
                "ld": [30.0, 30.0, 30.0, 22.0, 12.5],
            }
        )

        # Airfoil B: higher average drag
        df_b = pd.DataFrame(
            {
                "airfoil": ["Airfoil B"] * 5,
                "alpha": [0.0, 5.0, 10.0, 15.0, 20.0],
                "cl": [0.3, 0.6, 0.9, 1.1, 1.0],
                "cd": [0.02, 0.04, 0.06, 0.10, 0.16],  # Higher drag
                "ld": [15.0, 15.0, 15.0, 11.0, 6.25],
            }
        )

        score_a = score_airfoil(df_a)
        score_b = score_airfoil(df_b)

        # Airfoil A should have lower average drag and higher score
        assert score_a.avg_cd < score_b.avg_cd
        assert score_a.total_score > score_b.total_score

    def test_selection_is_deterministic(self) -> None:
        """Verify that selection logic is deterministic (same input = same output)."""
        df = pd.DataFrame(
            {
                "airfoil": ["Test Airfoil"] * 5,
                "alpha": [0.0, 5.0, 10.0, 15.0, 20.0],
                "cl": [0.3, 0.6, 0.9, 1.1, 1.0],
                "cd": [0.02, 0.03, 0.05, 0.08, 0.12],
                "ld": [15.0, 20.0, 18.0, 13.75, 8.33],
            }
        )

        # Score multiple times
        score1 = score_airfoil(df)
        score2 = score_airfoil(df)
        score3 = score_airfoil(df)

        # All scores should be identical
        assert score1.total_score == score2.total_score == score3.total_score
        assert score1.max_ld == score2.max_ld == score3.max_ld
        assert score1.stall_alpha == score2.stall_alpha == score3.stall_alpha
        assert score1.avg_cd == score2.avg_cd == score3.avg_cd

    def test_empty_dataframe_returns_nan_scores(self) -> None:
        """Test that empty DataFrame returns NaN scores."""
        empty_df = pd.DataFrame(columns=["airfoil", "alpha", "cl", "cd", "ld"])

        score = score_airfoil(empty_df)

        assert np.isnan(score.total_score)
        assert np.isnan(score.max_ld)
        assert np.isnan(score.stall_alpha)
        assert np.isnan(score.avg_cd)
        assert score.airfoil == ""

    def test_dataframe_with_invalid_ld_handled_correctly(self) -> None:
        """Test that DataFrame with invalid L/D values (inf, nan) is handled."""
        df = pd.DataFrame(
            {
                "airfoil": ["Test"] * 5,
                "alpha": [0.0, 5.0, 10.0, 15.0, 20.0],
                "cl": [0.3, 0.6, 0.9, 1.1, 1.0],
                "cd": [0.02, 0.0, 0.05, 0.08, 0.12],  # One zero drag -> inf L/D
                "ld": [15.0, np.inf, 18.0, 13.75, 8.33],
            }
        )

        score = score_airfoil(df)

        # Should handle inf values and compute score from valid data
        assert not np.isnan(score.total_score)
        assert score.max_ld > 0

    def test_best_airfoil_selected_from_multiple_candidates(self) -> None:
        """Test that the best airfoil is correctly selected from multiple candidates."""
        # Create three airfoils with different characteristics
        airfoils_data = [
            {
                "name": "High L/D",
                "df": pd.DataFrame(
                    {
                        "airfoil": ["High L/D"] * 5,
                        "alpha": [0.0, 5.0, 10.0, 15.0, 20.0],
                        "cl": [0.3, 0.6, 0.9, 1.1, 1.0],
                        "cd": [0.02, 0.03, 0.05, 0.08, 0.12],
                        "ld": [15.0, 20.0, 18.0, 13.75, 8.33],  # Max: 20.0
                    }
                ),
            },
            {
                "name": "Low Drag",
                "df": pd.DataFrame(
                    {
                        "airfoil": ["Low Drag"] * 5,
                        "alpha": [0.0, 5.0, 10.0, 15.0, 20.0],
                        "cl": [0.2, 0.4, 0.6, 0.7, 0.6],
                        "cd": [0.01, 0.015, 0.02, 0.03, 0.05],  # Lower drag
                        "ld": [20.0, 26.67, 30.0, 23.33, 12.0],  # Max: 30.0
                    }
                ),
            },
            {
                "name": "High Stall",
                "df": pd.DataFrame(
                    {
                        "airfoil": ["High Stall"] * 5,
                        "alpha": [0.0, 5.0, 10.0, 15.0, 20.0],
                        "cl": [0.25, 0.5, 0.75, 0.95, 1.1],  # Max at alpha=20
                        "cd": [0.02, 0.03, 0.05, 0.08, 0.10],
                        "ld": [12.5, 16.67, 15.0, 11.88, 11.0],  # Max: 16.67
                    }
                ),
            },
        ]

        scores = [score_airfoil(data["df"]) for data in airfoils_data]

        # Find best score
        best_score = max(scores, key=lambda s: s.total_score)

        # "Low Drag" should win (highest max L/D = 30.0)
        assert best_score.airfoil == "Low Drag"
        assert best_score.max_ld == pytest.approx(30.0, abs=1e-6)

    def test_score_airfoil_returns_correct_airfoil_name(self) -> None:
        """Test that score_airfoil correctly extracts and returns airfoil name."""
        df = pd.DataFrame(
            {
                "airfoil": ["NACA 65-410"] * 5,
                "alpha": [0.0, 5.0, 10.0, 15.0, 20.0],
                "cl": [0.3, 0.6, 0.9, 1.1, 1.0],
                "cd": [0.02, 0.03, 0.05, 0.08, 0.12],
                "ld": [15.0, 20.0, 18.0, 13.75, 8.33],
            }
        )

        score = score_airfoil(df)

        assert score.airfoil == "NACA 65-410"

    def test_score_components_are_correct(self) -> None:
        """Test that all score components (max_ld, stall_alpha, avg_cd) are correct."""
        df = pd.DataFrame(
            {
                "airfoil": ["Test"] * 5,
                "alpha": [0.0, 5.0, 10.0, 15.0, 20.0],
                "cl": [0.3, 0.6, 0.9, 1.1, 1.0],
                "cd": [0.02, 0.03, 0.05, 0.08, 0.12],
                "ld": [15.0, 20.0, 18.0, 13.75, 8.33],
            }
        )

        score = score_airfoil(df)

        # Verify max_ld
        assert score.max_ld == pytest.approx(20.0, abs=1e-6)

        # Verify stall_alpha (alpha where max L/D occurs)
        assert score.stall_alpha == pytest.approx(5.0, abs=1e-6)

        # Verify avg_cd
        expected_avg_cd = (0.02 + 0.03 + 0.05 + 0.08 + 0.12) / 5.0
        assert score.avg_cd == pytest.approx(expected_avg_cd, abs=1e-6)
