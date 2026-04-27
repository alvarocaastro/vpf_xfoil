"""
Velocity triangle analysis: converts alpha_opt (2D airfoil) to blade pitch angle beta.

For a fan blade section at radius r rotating at omega [rad/s] with axial velocity Va:

    phi = arctan(Va / U_r)   # flow angle (angle of incoming flow w.r.t. plane of rotation)
    beta = alpha_opt + phi   # required blade pitch angle to operate at alpha_opt

This is the core kinematic relationship that justifies Variable Pitch Fan (VPF):
as flight conditions change (Va, RPM), phi changes, so beta must change to keep
the airfoil at its optimal angle of attack.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import pandas as pd

from vpf_analysis.shared.plot_style import (
    COLORS,
    FLIGHT_LABELS,
    SECTION_LABELS,
    apply_style,
)


def compute_pitch_map(
    alpha_eff_map: Dict[Tuple[str, str], float],
    rpm: Dict[str, float],
    radii: Dict[str, float],
    axial_velocities: Dict[str, float],
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """
    Compute required blade pitch angle beta for each (flight, section) condition.

    Parameters
    ----------
    alpha_eff_map : dict mapping (flight_name, section_name) -> alpha_opt [deg]
    rpm : fan rotational speed [RPM] per flight condition
    radii : dict section_name -> radius [m]
    axial_velocities : dict flight_name -> axial velocity Va [m/s]

    Returns
    -------
    df : DataFrame with columns [flight, section, re, alpha_opt, phi_deg, beta_deg]
    delta_beta : dict section_name -> pitch range across flight conditions [deg]
    """
    rows: List[dict] = []
    for (flight, section), alpha_opt in alpha_eff_map.items():
        if math.isnan(alpha_opt):
            continue
        r = radii.get(section)
        va = axial_velocities.get(flight)
        if r is None or va is None:
            continue
        omega = 2.0 * math.pi * rpm.get(flight, next(iter(rpm.values()))) / 60.0
        u = omega * r                            # blade speed [m/s]
        phi_rad = math.atan2(va, u)              # flow angle [rad]
        phi_deg = math.degrees(phi_rad)          # flow angle [deg]
        beta_deg = alpha_opt + phi_deg           # required pitch [deg]
        rows.append(
            {
                "flight": flight,
                "section": section,
                "alpha_opt": round(alpha_opt, 3),
                "phi_deg": round(phi_deg, 3),
                "beta_deg": round(beta_deg, 3),
            }
        )

    df = pd.DataFrame(rows)

    # Compute pitch range (delta_beta) per section
    delta_beta: Dict[str, float] = {}
    if not df.empty:
        for section, grp in df.groupby("section"):
            delta_beta[str(section)] = round(
                float(grp["beta_deg"].max() - grp["beta_deg"].min()), 3
            )

    return df, delta_beta


def save_pitch_map_csv(df: pd.DataFrame, out_dir: Path) -> Path:
    """Save pitch map DataFrame to CSV."""
    out_path = out_dir / "blade_pitch_map.csv"
    df.to_csv(out_path, index=False, float_format="%.3f")
    return out_path


def plot_pitch_map(df: pd.DataFrame, delta_beta: Dict[str, float], out_dir: Path) -> None:
    """Grouped bar chart: required blade pitch angle β per (flight, section)."""
    if df.empty:
        return

    flight_order   = ["takeoff", "climb", "cruise", "descent"]
    section_order  = ["root", "mid_span", "tip"]
    flights_present  = [f for f in flight_order if f in df["flight"].values]
    sections_present = [s for s in section_order if s in df["section"].values]
    n_sections = len(sections_present)
    bar_width  = 0.25
    x = list(range(len(flights_present)))

    with apply_style():
        fig, ax = plt.subplots(figsize=(7.0, 5.0))

        for i, section in enumerate(sections_present):
            sub = df[df["section"] == section].set_index("flight")
            beta_vals = [sub.loc[f, "beta_deg"] if f in sub.index else float("nan") for f in flights_present]
            offset = (i - n_sections / 2.0 + 0.5) * bar_width
            bars = ax.bar(
                [xi + offset for xi in x],
                beta_vals,
                width=bar_width,
                label=f"{SECTION_LABELS[section]}  (Δβ = {delta_beta.get(section, 0):.1f}°)",
                color=COLORS[section],
                edgecolor="white",
                linewidth=0.6,
            )
            for bar, val in zip(bars, beta_vals):
                if not math.isnan(val):
                    ax.text(
                        bar.get_x() + bar.get_width() / 2.0,
                        bar.get_height() + 0.3,
                        f"{val:.1f}°",
                        ha="center", va="bottom", fontsize=7.5,
                    )

        ax.set_xticks(x)
        ax.set_xticklabels([FLIGHT_LABELS[f] for f in flights_present])
        ax.set_ylabel(r"Required blade pitch angle $\beta$ [°]")
        ax.set_title(r"Required blade pitch angle $\beta$ by flight phase")
        ax.legend(
            title="Section",
            bbox_to_anchor=(1.02, 1), loc="upper left",
            borderaxespad=0,
        )

        if delta_beta:
            delta_mech = max(delta_beta.values())
            section_max = max(delta_beta, key=delta_beta.__getitem__)
            ax.text(
                0.02, 0.97,
                f"VPF mechanism range: $\\Delta\\beta_{{\\max}}$ = {delta_mech:.1f}°  "
                f"({SECTION_LABELS[section_max]})",
                transform=ax.transAxes,
                va="top", ha="left",
                fontsize=9,
                bbox=dict(boxstyle="round,pad=0.35", facecolor="white",
                          edgecolor="gray", alpha=0.85),
            )

        for i, section in enumerate(sections_present):
            sub = df[df["section"] == section].set_index("flight")
            beta_vals = [
                sub.loc[f, "beta_deg"] if f in sub.index else float("nan")
                for f in flights_present
            ]
            valid = [v for v in beta_vals if not math.isnan(v)]
            if len(valid) < 2:
                continue
            b_min, b_max = min(valid), max(valid)
            offset = (i - n_sections / 2.0 + 0.5) * bar_width
            x_brace = max(x) + offset + bar_width * 0.6
            ax.annotate(
                "",
                xy=(x_brace, b_min), xytext=(x_brace, b_max),
                arrowprops=dict(
                    arrowstyle="<->", color=COLORS[section],
                    lw=1.4,
                ),
            )
            ax.text(
                x_brace + 0.08, (b_min + b_max) / 2.0,
                f"{delta_beta.get(section, 0):.1f}°",
                va="center", ha="left", fontsize=7.5, color=COLORS[section],
            )

        fig.tight_layout()
        fig.savefig(out_dir / "blade_pitch_map.png")
        plt.close(fig)


def plot_alpha_opt_evolution(
    alpha_eff_map: Dict[Tuple[str, str], float],
    configs: list,
    out_dir: Path,
) -> None:
    """
    Plot alpha_opt vs flight condition (categorical) for each blade section.

    X axis = flight phase ordered from takeoff to descent.
    One line per section (root, mid_span, tip).
    Shows how the optimal operating angle shifts across flight phases —
    the direct motivation for variable pitch.
    """
    flight_order  = ["takeoff", "climb", "cruise", "descent"]
    section_order = ["root", "mid_span", "tip"]
    markers = {"root": "o", "mid_span": "s", "tip": "^"}
    x = list(range(len(flight_order)))

    with apply_style():
        fig, ax = plt.subplots(figsize=(6.5, 4.5))
        any_plotted = False

        for section in section_order:
            alpha_vals = [alpha_eff_map.get((f, section), float("nan")) for f in flight_order]
            if all(math.isnan(v) for v in alpha_vals):
                continue
            ax.plot(
                x, alpha_vals,
                marker=markers[section],
                color=COLORS[section],
                label=SECTION_LABELS[section],
            )
            for xi, val in zip(x, alpha_vals):
                if not math.isnan(val):
                    ax.annotate(
                        f"{val:.1f}°",
                        xy=(xi, val), xytext=(0, 9),
                        textcoords="offset points",
                        ha="center", fontsize=8, color=COLORS[section],
                    )
            any_plotted = True

        if not any_plotted:
            plt.close(fig)
            return

        ax.set_xticks(x)
        ax.set_xticklabels([FLIGHT_LABELS[f] for f in flight_order])
        ax.set_ylabel(r"$\alpha_{opt}$ [°]")
        ax.set_title(r"$\alpha_{opt}$ evolution by flight phase")
        ax.legend(
            title="Section",
            bbox_to_anchor=(1.02, 1), loc="upper left",
            borderaxespad=0,
        )
        ax.set_ylim(bottom=ax.get_ylim()[0] - 0.4)
        fig.tight_layout()
        fig.savefig(out_dir / "alpha_opt_evolution.png")
        plt.close(fig)


def _interpolate_ld(df: pd.DataFrame, alpha_target: float) -> float:
    """Interpolate CL/CD from polar dataframe at a given alpha value."""
    df_clean = df.replace([float("inf"), float("-inf")], float("nan")).dropna(subset=["ld"])
    if df_clean.empty:
        return float("nan")
    # Find nearest two points and interpolate
    diff = (df_clean["alpha"] - alpha_target).abs()
    idx = diff.nsmallest(2).index
    sub = df_clean.loc[idx].sort_values("alpha")
    if len(sub) < 2:
        return float(sub["ld"].iloc[0])
    a0, a1 = float(sub["alpha"].iloc[0]), float(sub["alpha"].iloc[1])
    l0, l1 = float(sub["ld"].iloc[0]), float(sub["ld"].iloc[1])
    if abs(a1 - a0) < 1e-9:
        return l0
    t = (alpha_target - a0) / (a1 - a0)
    return l0 + t * (l1 - l0)


def plot_vpf_efficiency_by_section(
    polar_dfs: dict,
    alpha_eff_map: Dict[Tuple[str, str], float],
    out_dir: Path,
) -> None:
    """
    For each blade section, plot CL/CD vs alpha overlaying all flight conditions.

    Marks:
    - Each condition's own alpha_opt (filled dot) — VPF operating point
    - The cruise alpha_opt as a vertical dashed line — fixed-pitch reference

    This directly visualises the VPF argument: fixed cruise pitch leaves
    every non-cruise condition operating away from its efficiency peak.

    Parameters
    ----------
    polar_dfs : dict mapping (flight, section) -> DataFrame (columns: alpha, cl, cd, ld)
    alpha_eff_map : dict mapping (flight, section) -> alpha_opt
    out_dir : output directory
    """
    flight_order  = ["takeoff", "climb", "cruise", "descent"]
    section_order = ["root", "mid_span", "tip"]

    with apply_style():
        for section in section_order:
            cruise_alpha = alpha_eff_map.get(("cruise", section), float("nan"))
            fig, ax = plt.subplots(figsize=(7.5, 5.0))

            for flight in flight_order:
                df = polar_dfs.get((flight, section))
                alpha_opt = alpha_eff_map.get((flight, section), float("nan"))
                if df is None or df.empty:
                    continue
                color = COLORS[flight]
                ax.plot(df["alpha"], df["ld"], color=color, label=FLIGHT_LABELS[flight])
                if not math.isnan(alpha_opt):
                    ld_opt = _interpolate_ld(df, alpha_opt)
                    ax.scatter(alpha_opt, ld_opt, color=color, s=70, zorder=5,
                               edgecolors="white", linewidths=1.2)

            if not math.isnan(cruise_alpha):
                ax.axvline(
                    cruise_alpha, color=COLORS["cruise"],
                    linestyle="--", linewidth=1.6, alpha=0.85,
                    label=f"Fixed cruise pitch  (α = {cruise_alpha:.1f}°)",
                )

            ax.set_xlabel(r"$\alpha$ [°]")
            ax.set_ylabel(r"$C_L / C_D$")
            ax.set_title(
                f"$C_L/C_D$ vs $\\alpha$ — {SECTION_LABELS[section]} section"
            )
            ax.set_xlim(-2, 18)
            # Legend outside, to the right of the plot
            ax.legend(
                title="Flight condition",
                bbox_to_anchor=(1.02, 1), loc="upper left",
                borderaxespad=0,
            )
            fig.tight_layout()
            fig.savefig(out_dir / f"vpf_efficiency_{section}.png")
            plt.close(fig)


def plot_vpf_clcd_penalty(
    polar_dfs: dict,
    alpha_eff_map: Dict[Tuple[str, str], float],
    out_dir: Path,
) -> None:
    """
    Two-panel figure showing the VPF efficiency argument.

    Top panel — absolute CL/CD per (flight, section): solid bar = VPF optimal,
    hatched bar = fixed cruise pitch.  Bars are side-by-side, not stacked.

    Bottom panel — % efficiency retained with fixed pitch (100% = no loss).
    """
    flight_order  = ["takeoff", "climb", "cruise", "descent"]
    section_order = ["root", "mid_span", "tip"]

    n_sections = len(section_order)
    bar_width  = 0.22
    group_width = n_sections * bar_width * 2 + 0.15
    x_centers  = [i * group_width for i in range(len(flight_order))]

    # Pre-compute CL/CD values
    opt_table:   Dict[Tuple[str, str], float] = {}
    fixed_table: Dict[Tuple[str, str], float] = {}
    for section in section_order:
        cruise_alpha = alpha_eff_map.get(("cruise", section), float("nan"))
        for flight in flight_order:
            df        = polar_dfs.get((flight, section))
            alpha_opt = alpha_eff_map.get((flight, section), float("nan"))
            if df is None or df.empty:
                opt_table[(flight, section)]   = float("nan")
                fixed_table[(flight, section)] = float("nan")
                continue
            opt_table[(flight, section)]   = _interpolate_ld(df, alpha_opt) if not math.isnan(alpha_opt) else float("nan")
            fixed_table[(flight, section)] = _interpolate_ld(df, cruise_alpha) if not math.isnan(cruise_alpha) else float("nan")

    with apply_style():
        fig, (ax_top, ax_bot) = plt.subplots(
            2, 1, figsize=(9.5, 8.0),
            gridspec_kw={"height_ratios": [3, 2]},
        )

        # ── TOP: absolute CL/CD ─────────────────────────────────────────────
        for si, section in enumerate(section_order):
            color = COLORS[section]
            for fi, flight in enumerate(flight_order):
                xc    = x_centers[fi]
                x_opt = xc + (si - n_sections / 2.0 + 0.5) * bar_width * 2 - bar_width * 0.5
                x_fix = x_opt + bar_width
                vo = opt_table[(flight, section)]
                vf = fixed_table[(flight, section)]
                ax_top.bar(x_opt, vo, width=bar_width, color=color, alpha=0.88,
                           label=f"{SECTION_LABELS[section]} — VPF" if fi == 0 else "_nolegend_")
                ax_top.bar(x_fix, vf, width=bar_width, color=color, alpha=0.28,
                           hatch="////", edgecolor=color, linewidth=0.8,
                           label=f"{SECTION_LABELS[section]} — fixed pitch" if fi == 0 else "_nolegend_")

        ax_top.set_xticks(x_centers)
        ax_top.set_xticklabels([FLIGHT_LABELS[f] for f in flight_order])
        ax_top.set_ylabel(r"$C_L/C_D$ at operating point")
        ax_top.set_title(r"$C_L/C_D$ at operating point: VPF vs fixed cruise pitch")
        ax_top.legend(
            bbox_to_anchor=(1.02, 1), loc="upper left",
            borderaxespad=0, ncol=1,
        )

        # ── BOTTOM: % efficiency retained ───────────────────────────────────
        bar_w2 = 0.20
        for si, section in enumerate(section_order):
            color    = COLORS[section]
            pct_vals = []
            for flight in flight_order:
                vo = opt_table[(flight, section)]
                vf = fixed_table[(flight, section)]
                pct_vals.append(vf / vo * 100.0 if not (math.isnan(vo) or math.isnan(vf) or vo <= 0) else float("nan"))

            xpos = [xc + (si - n_sections / 2.0 + 0.5) * bar_w2 * 1.15 for xc in x_centers]
            bars = ax_bot.bar(xpos, pct_vals, width=bar_w2, color=color,
                              alpha=0.88, label=SECTION_LABELS[section])
            for bar, pct in zip(bars, pct_vals):
                if not math.isnan(pct):
                    ax_bot.text(bar.get_x() + bar.get_width() / 2.0, pct + 0.4,
                                f"{pct:.1f}%", ha="center", va="bottom", fontsize=7.5)

        ax_bot.axhline(100, color="black", linewidth=1.2, linestyle="--", alpha=0.5,
                       label="100 % = no loss")
        ax_bot.set_xticks(x_centers)
        ax_bot.set_xticklabels([FLIGHT_LABELS[f] for f in flight_order])
        ax_bot.set_ylabel("Retained efficiency [%]")
        ax_bot.set_title("Retained efficiency with fixed cruise pitch [%]")
        ax_bot.set_ylim(0, 115)
        ax_bot.legend(
            bbox_to_anchor=(1.02, 1), loc="upper left",
            borderaxespad=0,
        )

        fig.tight_layout(pad=2.0)
        fig.savefig(out_dir / "vpf_clcd_penalty.png")
        plt.close(fig)
