# PCC-Viewer/viewer_plots.py
"""
PCC-Viewer visualization functions.

Follows the reference MATLAB implementation described in:
  - ROBO_plotPCV.m  → plot_pcc_stereographic()
  - AUX_plot_dPCC.m → plot_dpcc_elevation()

Reference:
    Kröger, J. (2025): Systematische Untersuchung von GNSS-Antennenkalibrierungen
    und deren Einfluss auf geodätische Parameter. Dissertation, Leibniz Universität
    Hannover.
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.ticker import AutoMinorLocator


# =============================================================================
# Line colours
# =============================================================================

# Twelve colours chosen to stay apart on a white background; none is close
# enough to black to be confused with another series.
_BASE_LINE_COLORS = [
    '#2E86AB',  # blue
    '#C73E1D',  # red
    '#F18F01',  # orange
    '#44BBA4',  # teal
    '#A23B72',  # magenta
    '#6A4C93',  # violet
    '#8CB369',  # green
    '#B5651D',  # brown
    '#0B6E4F',  # dark green
    '#E94F37',  # coral
    '#3D5A80',  # slate
    '#D4A017',  # gold
]


def build_line_colors(n, supplied=None):
    """
    `n` colours, all different from each other.

    Cycling a fixed palette with `i % len(colors)` would repeat colours as soon
    as there are more signals than colours, which is common once IF-LC
    combinations are selected; a real pattern set can have thirteen entries.

    A caller may still pass its own palette; it is used first and extended, not
    replaced, so the colour schemes offered in the GUI keep their look.
    """
    out = list(supplied) if supplied else []
    for c in _BASE_LINE_COLORS:
        if len(out) >= n:
            break
        if c not in out:
            out.append(c)
    if len(out) < n:
        # Still short: sample a continuous map for whatever is left, skipping
        # the very light end where a line stops being visible.
        import matplotlib.pyplot as plt
        cmap = plt.get_cmap('gist_ncar')
        needed = n - len(out)
        for k in range(needed):
            colour = mcolors.to_hex(cmap(0.05 + 0.9 * (k / max(1, needed - 1))))
            while colour in out:                      # never repeat
                colour = mcolors.to_hex(
                    tuple(min(1.0, v * 0.92) for v in mcolors.to_rgb(colour)))
            out.append(colour)
    return out[:max(1, n)]


# =============================================================================
# Stereographic Projection — Port of ROBO_plotPCV.m
# =============================================================================

def plot_pcc_stereographic(pcv_grid: np.ndarray, pco_mm: np.ndarray,
                           dazi: float, dzen: float,
                           zen1: float = 0.0, zen2: float = 90.0,
                           signal_label: str = "PCC [mm]",
                           limits: tuple = None,
                           show_pcc: bool = True,
                           title: str = None,
                           pco_text: str = None,
                           ax=None):
    """
    Stereographic polar projection of PCC or PCV patterns.

    Follows the reference implementation (Kröger, 2025).

    The stereographic projection maps elevation → radius via:
        r = 2·tan(π/4 − el/2)
    This preserves angles (conformal) and is the standard for GNSS antenna patterns.

    Args:
        pcv_grid: 2D PCV array, shape (n_azi, n_zen). Values in mm.
                  n_azi = 360/dazi + 1 (0° to 360° inclusive)
                  n_zen = (zen2-zen1)/dzen + 1 (zenith angles)
        pco_mm: PCO vector [N, E, U] in mm. Used if show_pcc=True.
        dazi: Azimuth grid spacing in degrees.
        dzen: Zenith grid spacing in degrees.
        zen1: Start zenith angle (default 0°, i.e., zenith).
        zen2: End zenith angle (default 90°, i.e., horizon).
        signal_label: Label for colorbar (e.g., "G01 [mm]").
        limits: Optional (vmin, vmax) for color scale.
        show_pcc: If True, compute PCC = -PCO·e + PCV. If False, plot raw PCV or ΔPCC.
        title: Optional plot title.
        pco_text: Optional PCO annotation text to display in the figure (PCV/PCO are
                  a linked set and should not be analyzed in isolation).
        ax: Optional matplotlib axes. If None, creates a new figure.

    Returns:
        The matplotlib axes object.
    """
    # --- Build elevation and azimuth grids ---
    # MATLAB: EL = 90-zen2 : dzen : 90-zen1  (elevation, ascending)
    #
    # The GRID ITSELF is the ground truth for the axes, not the zen1/zen2/dzen
    # arguments. Many IGS antennas are azimuth-independent (a single NOAZI row)
    # and stop at zenith 80 deg, i.e. 17 values rather than 19. Building the
    # mesh from the arguments alone then produced a (2,19) mesh for a (1,17)
    # pattern and the plot died with "operands could not be broadcast together"
    # - 91 of the 402 antennas in igs20_2226.atx are like this.
    n_azi_actual, n_zen_actual = pcv_grid.shape

    # Zenith range implied by the data itself
    zen2_eff = zen1 + (n_zen_actual - 1) * dzen
    el_vec = np.arange(90.0 - zen2_eff, 90.0 - zen1 + dzen * 0.5, dzen)
    el_vec = el_vec[:n_zen_actual]

    if n_azi_actual == 1:
        # Azimuth-independent pattern: identical in every direction. Repeat the
        # single row around the circle so a surface can be drawn from it.
        # It needs REAL angular sampling: two entries (0 and 360 deg) describe
        # the same direction, so every quad would have zero width and the disc
        # would come out blank.
        az_vec = np.arange(0.0, 360.0 + 2.5, 5.0)
        pcv_grid = np.repeat(pcv_grid, len(az_vec), axis=0)
    else:
        az_vec = np.arange(0.0, 360.0 + dazi * 0.5, dazi)  # deg

    n_azi_expected = len(az_vec)
    n_zen_expected = len(el_vec)

    # Validate grid dimensions
    if pcv_grid.shape[0] != n_azi_expected or pcv_grid.shape[1] != n_zen_expected:
        # Try transpose
        if pcv_grid.shape[1] == n_azi_expected and pcv_grid.shape[0] == n_zen_expected:
            pcv_grid = pcv_grid.T
        else:
            # Trim or pad to fit
            pcv_grid = pcv_grid[:n_azi_expected, :n_zen_expected]

    # --- The elevation of each COLUMN of the grid -------------------------------
    # The column order matters: getting it wrong draws the disc inside out, with
    # low-elevation values at the zenith.
    #
    # ANTEX stores PCV by ZENITH angle ascending (ZEN1 -> ZEN2), so column 0 is
    # zenith 0, which is ELEVATION 90, and the columns run elevation DESCENDING.
    # `el_vec` above is built ascending to mirror the MATLAB source, so it does
    # NOT describe the columns. Reversing both the data (np.fliplr) and the axis
    # (el_vec[::-1]) would cancel out and draw a value at elevation e at the
    # radius of elevation 90 - e.
    #
    # There is one right answer and it is used for both jobs below: state the
    # elevation of each column once, and neither flip nor reverse anything.
    # Verified on LEIAR25.R4 chamber - robot, G01: dPCC is +1.95 mm at the zenith
    # and -1.44 mm at the horizon, so the centre of the disc must be red.
    el_vec_cols = 90.0 - (zen1 + np.arange(n_zen_actual) * dzen)

    # --- Compute PCC pattern if requested ---
    # MATLAB lines 76-88: pattern = -(PCO_N·EV1 + PCO_E·EV2 + PCO_U·EV3) + PCV
    # This has to use el_vec_cols too. With the ascending el_vec the PCO term
    # would be evaluated at elevation e while the PCV value it is added to
    # belongs to elevation 90 - e, mixing a correctly placed PCO bowl with an
    # inverted PCV pattern; that would still look plausible, because PCO Up
    # (about 155 mm) dwarfs PCV (a few mm).
    if show_pcc and pco_mm is not None:
        AZ_grid, EL_grid = np.meshgrid(az_vec, el_vec_cols, indexing='ij')
        EV_N = np.cos(np.radians(AZ_grid)) * np.cos(np.radians(EL_grid))
        EV_E = np.sin(np.radians(AZ_grid)) * np.cos(np.radians(EL_grid))
        EV_U = np.sin(np.radians(EL_grid))
        pattern = -(pco_mm[0] * EV_N + pco_mm[1] * EV_E + pco_mm[2] * EV_U) + pcv_grid
    else:
        pattern = pcv_grid.copy()

    el_vec_plot = el_vec_cols

    # --- Stereographic projection ---
    # MATLAB line 109: r = 2*tan(pi/4 - EL/2)
    AZ_rad = np.radians(az_vec)
    EL_rad = np.radians(el_vec_plot)
    AZ_grid, EL_grid = np.meshgrid(AZ_rad, EL_rad, indexing='ij')

    r = 2.0 * np.tan(np.pi / 4.0 - EL_grid / 2.0)
    X = r * np.sin(AZ_grid)
    Y = r * np.cos(AZ_grid)

    # --- Plot ---
    created_fig = False
    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 6.5))
        created_fig = True

    # Use pcolormesh (equivalent to MATLAB's surf + view(0,90) + shading interp)
    if limits:
        vmin, vmax = limits
    else:
        vmin, vmax = np.nanmin(pattern), np.nanmax(pattern)

    mesh = ax.pcolormesh(X, Y, pattern, cmap='jet', shading='gouraud',
                         vmin=vmin, vmax=vmax)

    ax.set_aspect('equal')
    ax.axis('off')

    # --- Overlay azimuth lines (MATLAB lines 149–172) ---
    az_labels = np.arange(0, 180, 30)
    r_outer = 2.0 * np.tan(np.pi / 4.0 - np.radians(90.0 - zen2) / 2.0)

    for az_deg in az_labels:
        az_rad = np.radians(az_deg)
        x1 = r_outer * np.sin(az_rad)
        y1 = r_outer * np.cos(az_rad)
        ax.plot([x1, -x1], [y1, -y1], 'k:', linewidth=1.0, zorder=5)

        # Labels
        offset = 0.08
        dx = offset * np.sin(az_rad)
        dy = offset * np.cos(az_rad)
        ax.text(x1 + dx, y1 + dy, f'{az_deg}°',
                fontsize=11, ha='center', va='center', zorder=6)
        if az_deg == 0:
            ax.text(-x1 - dx, -y1 - dy, f'{az_deg + 180}°',
                    fontsize=11, ha='center', va='top', zorder=6)
        else:
            ax.text(-x1 - dx, -y1 - dy, f'{az_deg + 180}°',
                    fontsize=11, ha='right', va='center', zorder=6)

    # --- Overlay elevation circles (MATLAB lines 173–189) ---
    el_circles = np.arange(90.0 - zen2, 90.0 - zen1, 15.0)
    circle_az = np.linspace(0, 2 * np.pi, 361)

    for el_deg in el_circles:
        r_circle = 2.0 * np.tan(np.pi / 4.0 - np.radians(el_deg) / 2.0)
        xc = r_circle * np.sin(circle_az)
        yc = r_circle * np.cos(circle_az)

        if el_deg == el_circles[0]:
            # Outer boundary — solid line
            ax.plot(xc, yc, 'k-', linewidth=1.5, zorder=5)
        else:
            ax.plot(xc, yc, 'k:', linewidth=1.0, zorder=5)

        # Elevation label on the right side
        ax.text(0.05, r_circle, f'{el_deg:.0f}°',
                fontsize=11, ha='left', va='bottom',
                color='black', zorder=6)

    # Zenith label
    ax.text(0.05, 0, '90°', fontsize=11, ha='left',
            va='bottom', color='black', zorder=6)

    # --- Colorbar ---
    cbar = plt.colorbar(mesh, ax=ax, shrink=0.75, pad=0.05)
    cbar.set_label(signal_label, fontsize=11)
    cbar.ax.tick_params(labelsize=9)

    if pco_text:
        # Place the PCO box centred BELOW the polar axes, not inside it — at the
        # old (0.02, 0.02) it overlapped the circle / angle labels on this polar
        # projection (the formatting of the displayed PCO could be
        # improved").
        ax.annotate(pco_text, xy=(0.5, -0.11), xycoords='axes fraction',
                    fontsize=9, fontfamily='monospace',
                    ha='center', va='top',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='lightyellow',
                              edgecolor='gray', alpha=0.9))

    if title:
        ax.set_title(title, fontsize=14, fontweight='bold', pad=15)

    if created_fig:
        plt.tight_layout()
        if pco_text:
            # Leave room for the PCO box now placed below the polar axes.
            plt.subplots_adjust(bottom=0.15)
        plt.show()

    return ax


# =============================================================================
# Elevation ΔPCC Plot — Port of AUX_plot_dPCC.m
# =============================================================================

def plot_dpcc_elevation(dpcc_patterns: list, signal_labels: list,
                        dazi: float = 5.0, dzen: float = 5.0,
                        colors: list = None,
                        title: str = None,
                        ax=None,
                        ylimits: tuple = None,
                        pco_text: str = None,
                        ylabel: str = None,
                        legend_title: str = None):
    """
    Elevation-dependent ΔPCC plot with mean (solid) and min/max (dashed) envelopes.

    Follows the reference implementation (Kröger, 2025).

    For each pattern, plots:
      - Mean across all azimuths at each elevation (solid, thick line)
      - Min across all azimuths (dashed, thin)
      - Max across all azimuths (dashed, thin)

    Args:
        dpcc_patterns: List of 2D arrays, each shape (n_azi, n_zen).
                       ΔPCC values in mm. Can be PCC₁−PCC₂ or raw PCV.
        signal_labels: List of labels for legend (e.g., ["G01", "E01"]).
        dazi: Azimuth grid spacing in degrees.
        dzen: Zenith grid spacing in degrees.
        colors: Optional list of color values. Uses 'meadow'-like palette if None.
        title: Optional plot title.
        ax: Optional matplotlib axes.
        ylimits: Optional (ymin, ymax) for the y-axis.
        pco_text: Optional PCO annotation text to display in the figure.
        ylabel: Optional custom y-axis label (default: 'ΔPCC [mm]').
        legend_title: Optional title shown above the legend entries
                      (e.g., "Frequency | PCO [mm]").

    Returns:
        The matplotlib axes object.
    """
    if not dpcc_patterns:
        return None

    created_fig = False
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 5.5))
        created_fig = True

    # One colour per pattern, all of them different.
    colors = build_line_colors(len(dpcc_patterns), colors)

    # Track the first valid el_vec for x-axis limits
    first_el_vec = None

    for i, pattern in enumerate(dpcc_patterns):
        color = colors[i % len(colors)]
        label = signal_labels[i] if i < len(signal_labels) else f'Pattern {i + 1}'

        # Compute el_vec per-pattern to handle different zenith grid sizes
        n_zen_i = pattern.shape[1]
        el_vec_i = np.linspace(90.0, 0.0, n_zen_i)
        if first_el_vec is None:
            first_el_vec = el_vec_i

        # Compute statistics across azimuths (axis=0)
        mean_vals = np.nanmean(pattern, axis=0)
        min_vals = np.nanmin(pattern, axis=0)
        max_vals = np.nanmax(pattern, axis=0)

        # Plot mean (solid, thick) — MATLAB LineWidth=4
        ax.plot(el_vec_i, mean_vals, '-', linewidth=3.0, color=color, label=label)
        # Plot min/max (dashed, thin) — MATLAB LineWidth=2
        ax.plot(el_vec_i, min_vals, '--', linewidth=1.5, color=color, alpha=0.7)
        ax.plot(el_vec_i, max_vals, '--', linewidth=1.5, color=color, alpha=0.7)

        # Fill between min and max for visual clarity
        ax.fill_between(el_vec_i, min_vals, max_vals, color=color, alpha=0.08)

    # --- Formatting (MATLAB lines 43-48) ---
    if first_el_vec is not None:
        ax.set_xlim(first_el_vec[-1], first_el_vec[0])  # 0 → 90
    ax.set_xlabel('Elevation angle [°]', fontsize=13)
    ax.set_ylabel(ylabel or 'ΔPCC [mm]', fontsize=13)
    ax.tick_params(axis='both', labelsize=11)
    ax.xaxis.set_minor_locator(AutoMinorLocator())
    ax.yaxis.set_minor_locator(AutoMinorLocator())
    ax.grid(True, which='major', linewidth=0.8, alpha=0.5)
    ax.grid(True, which='minor', linewidth=0.4, alpha=0.3)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_axisbelow(True)

    if ylimits:
        ax.set_ylim(ylimits)

    # Always show the legend, even for a single signal
    ax.legend(title=legend_title, fontsize=11, title_fontsize=10, loc='best', framealpha=0.9)

    # No separate PCO box is drawn: the legend already lists the PCO of every
    # plotted signal, while a single box could show only one signal's values.
    # `pco_text` stays in the signature for existing callers.

    if title:
        ax.set_title(title, fontsize=14, fontweight='bold')

    if created_fig:
        plt.tight_layout()
        plt.show()

    return ax


# =============================================================================
# Multi-panel Combined View
# =============================================================================

def plot_pcc_combined(stereo_grid: np.ndarray,
                      elev_patterns: list,
                      elev_labels: list,
                      dazi: float, dzen: float,
                      stereo_signal_label: str = "G01",
                      stereo_limits: tuple = None,
                      antenna_name: str = None,
                      ylabel: str = 'PCC [mm]'):
    """
    Combined 2-panel view: stereographic projection + elevation profile.

    Reworked:
      - the elevation panel overlays ALL selected signals (not just one);
      - the stereographic panel shows the first selected signal;
      - the y-axis label reflects the quantity shown (PCC or PCV), not ΔPCC;
      - PCO is not annotated — the full PCC already contains the PCO offset.

    Args:
        stereo_grid: Final grid (already full PCC or raw PCV) for the left panel.
        elev_patterns: List of final grids (one per selected signal) for the
                       elevation overlay.
        elev_labels: Legend labels matching ``elev_patterns``.
        dazi, dzen: Grid spacings in degrees (for the stereographic panel).
        stereo_signal_label: Label of the signal shown in the stereographic panel.
        stereo_limits: Optional (vmin, vmax) for stereographic colorbar.
        antenna_name: Optional antenna name for plot title.
        ylabel: Y-axis label for the elevation panel ('PCC [mm]' or 'PCV [mm]').
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 7),
                                    gridspec_kw={'width_ratios': [1, 1.2]})

    # Antenna name as a figure-level title — avoids clipping on narrow panels
    if antenna_name:
        fig.suptitle(antenna_name, fontsize=14, fontweight='bold', y=0.98)

    # Left: stereographic of the first signal. The grid is already final (PCC or
    # PCV), so plot it as-is (show_pcc=False) and do not annotate PCO.
    plot_pcc_stereographic(
        stereo_grid, None, dazi, dzen,
        signal_label=ylabel,
        limits=stereo_limits,
        show_pcc=False,
        title=f'{ylabel.split(" ")[0]} Pattern ({stereo_signal_label})',
        pco_text=None,
        ax=ax1
    )

    # Right: elevation profile overlaying every selected signal
    plot_dpcc_elevation(
        elev_patterns, elev_labels,
        dazi=dazi, dzen=dzen,
        title='Elevation Profile',
        ylabel=ylabel,
        legend_title='Frequency',
        ax=ax2
    )

    fig.subplots_adjust(left=0.06, right=0.96, bottom=0.08, top=0.90, wspace=0.35)
    plt.show()


# =============================================================================
# Helper: Compute ΔPCC grid from two ANTEX datasets
# =============================================================================

#: Alternative spellings a parser may use for a constellation, so a naming
#: mismatch cannot silently turn into "no data" (the viewer asked for
#: 'BeiDou' while the parser had stored everything under 'BDS').
_SYSTEM_ALIASES = {
    'BDS': ('BDS', 'BeiDou', 'Beidou', 'COMPASS'),
    'BeiDou': ('BDS', 'BeiDou', 'Beidou', 'COMPASS'),
    'GLONASS': ('GLONASS', 'Glonass', 'GLO'),
    'Galileo': ('Galileo', 'GALILEO', 'GAL'),
}


def _lookup_by_system(container: dict, antenna_key: str, system: str, freq_code: str):
    """
    Fetch container[antenna][system][freq], tolerating constellation spellings.

    Get_pcc_grid gained this earlier but compute_dpcc_grid
    kept its own plain dict lookup, so ΔPCC would have failed for BeiDou for
    exactly the reason the absolute plots once did. One helper now serves both.
    """
    by_antenna = (container or {}).get(antenna_key, {})
    for name in _SYSTEM_ALIASES.get(system, (system,)):
        value = by_antenna.get(name, {}).get(freq_code)
        if value is not None:
            return value
    return None


def compute_dpcc_grid(antex_data_1: dict, antex_data_2: dict,
                      antenna_key_1: str, antenna_key_2: str,
                      system: str, freq_code: str,
                      grid_step: float = 5.0) -> np.ndarray:
    """
    Computes the ΔPCC = PCC₁ - PCC₂ grid for a given signal.

    Args:
        antex_data_1, antex_data_2: Parsed ANTEX data dicts.
        antenna_key_1, antenna_key_2: Resolved antenna keys.
        system: GNSS system name (e.g., 'GPS').
        freq_code: Frequency code (e.g., 'G01').
        grid_step: Grid spacing in degrees.

    Returns:
        2D numpy array of ΔPCC values (n_azi x n_zen), in mm.
    """
    def _get_pcc_grid(antex_data, antenna_key, grid_step):
        """Get PCC grid = -PCO·e + PCV for one antenna."""
        pco = _lookup_by_system(antex_data['pco'], antenna_key, system, freq_code)
        pcv = _lookup_by_system(antex_data['pcv'], antenna_key, system, freq_code)

        if pco is None or pcv is None:
            return None

        n_azi, n_zen = pcv.shape

        # Build elevation/azimuth grids
        az_vec = np.linspace(0, 360, n_azi)
        el_vec = np.linspace(90, 0, n_zen)
        AZ, EL = np.meshgrid(az_vec, el_vec, indexing='ij')

        # Line-of-sight unit vectors
        EV_N = np.cos(np.radians(AZ)) * np.cos(np.radians(EL))
        EV_E = np.sin(np.radians(AZ)) * np.cos(np.radians(EL))
        EV_U = np.sin(np.radians(EL))

        # PCC = -PCO·e + PCV
        pcc = -(pco[0] * EV_N + pco[1] * EV_E + pco[2] * EV_U) + pcv
        return pcc

    pcc_1 = _get_pcc_grid(antex_data_1, antenna_key_1, grid_step)
    pcc_2 = _get_pcc_grid(antex_data_2, antenna_key_2, grid_step)

    if pcc_1 is None:
        raise ValueError(f"No PCV data for {antenna_key_1}/{system}/{freq_code} in File 1")
    if pcc_2 is None:
        raise ValueError(f"No PCV data for {antenna_key_2}/{system}/{freq_code} in File 2")

    return pcc_1 - pcc_2


def get_pcc_grid(antex_data: dict, antenna_key: str,
                 system: str, freq_code: str) -> tuple:
    """
    Extracts PCV grid and PCO vector for a single antenna/signal.

    Returns:
        Tuple of (pcv_grid, pco_mm, dazi, dzen) or (None, None, None, None).
    """
    pco = _lookup_by_system(antex_data['pco'], antenna_key, system, freq_code)
    pcv = _lookup_by_system(antex_data['pcv'], antenna_key, system, freq_code)

    if pco is None or pcv is None:
        return None, None, None, None

    # Get grid spacing from metadata
    meta = antex_data.get('metadata', {}).get(antenna_key, {})
    dzen = meta.get('dzen', 5.0)
    # Infer dazi from grid shape
    n_azi = pcv.shape[0]
    dazi = 360.0 / max(n_azi - 1, 1)

    return pcv, pco, dazi, dzen
