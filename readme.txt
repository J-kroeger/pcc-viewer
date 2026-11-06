================================================================================
                              PCC-Viewer
================================================================================

Version: 1.1.1
Release date: 2026-11-01

An open-source tool for visualizing GNSS antenna Phase Center Corrections (PCC)
using stereographic projections and elevation profiles.

Part of the PCC software suite developed at the Institut für Erdmessung (IfE),
Leibniz Universität Hannover.

================================================================================
  CITATION
================================================================================

If you use this software, please cite:

  Kröger, J., Kersten, T. & Schön, S. PCC-Explorer: An open-source software
  tool to assess the impact of GNSS antenna phase center corrections on
  geodetic parameters. GPS Solut 30, 93 (2026).
  https://doi.org/10.1007/s10291-026-02056-2

A DOI for this program itself is planned with the v2.0 release of the suite;
until then please cite the paper above.

================================================================================
  QUICK START
================================================================================

  pip install -r requirements.txt
  python pcc_viewer.py

Or use the provided launcher scripts:
  - Windows:     launch_gui.bat
  - Linux/macOS: launch_gui.sh

================================================================================
  FEATURES
================================================================================

Visualization Modes
-------------------
  * Single File (Absolute PCC):
    Load one ANTEX file and visualize the absolute Phase Center Corrections
    for any antenna and signal in the file.

  * Two Files (Delta PCC):
    Load two ANTEX files (e.g., chamber vs. robot calibrations) and visualize
    the differences in PCC between them.

Plot Types
----------
  * Stereographic Projection:
    Top-down polar projection of the antenna PCC pattern over the whole sky,
    showing azimuth and zenith dependence.

  * Elevation Profile:
    Cross-section showing PCC as a function of elevation angle, with mean
    (solid line) and min/max (dashed envelope) across all azimuths.

  * All Signals Grid:
    Side-by-side stereographic plots for all available signals, useful for
    quick multi-frequency comparison.

Options
-------
  * Show PCC: Toggle between PCV-only and full PCC (PCO + PCV)
  * Custom colorbar limits: Set min/max values for the color scale
  * Single or all-signals view
  * Iono-free (IF-LC) combinations are offered alongside the raw signals

Shared calibrations
-------------------
Signals that share one calibration - a Galileo signal copied from its GPS
carrier, for example - are drawn once, in one colour, with a single legend
entry naming the whole group (G01 = C01 = E01 = J01 = S01). A note above the
plot lists the same groups, so the legend and the text always agree.

================================================================================
  DEPENDENCIES
================================================================================

  * Python 3.8+
  * numpy
  * matplotlib
  * ttkbootstrap (optional, for themed GUI)
  * PCC-Explorer's data_io module (for ANTEX parsing)

Note: PCC-Viewer expects the ImpactOfDeltaPCC/ folder to be a sibling
directory for importing the ANTEX parser.

================================================================================
  FILE STRUCTURE
================================================================================

  PCC-Viewer/
  +-- pcc_viewer.py             Main GUI application
  +-- viewer_plots.py           Stereographic + elevation plot functions
  +-- test_viewer.py            Headless test with real ANTEX data
  +-- requirements.txt          Python dependencies
  +-- launch_gui.bat            Windows launcher
  +-- launch_gui.sh             Linux/macOS launcher
  +-- readme.txt                This file
  +-- LICENSE.txt                Short copyright notice

================================================================================
  CONTACT
================================================================================

  Dr.-Ing. Johannes Kröger -- kroeger@ife.uni-hannover.de

================================================================================
  LICENSE
================================================================================

This project is licensed under the GNU General Public License v3.0 or later.
See LICENSE.txt

================================================================================
  STAY INFORMED
================================================================================

  The Institut für Erdmessung runs a moderated mailing list for its GNSS
  software. It announces new releases and warns you about changes that can
  break your work, for example when a server for satellite orbit products
  moves to a new address. Every program in the suite offers this once when it
  first starts, and the Contact dialog can open it again at any time.

  Subscribe (web form):
    https://lists.uni-hannover.de/sympa/subscribe/ife-software

  Subscribe by e-mail:
    send the two lines     subscribe ife-software
                           QUIT
    to                     sympa@lists.uni-hannover.de

  The word QUIT tells the list server to stop reading, so a signature added
  by your mail program does no harm.

  List address: ife-software@lists.uni-hannover.de

  The list server answers with a mail that asks you to confirm. The
  subscription becomes active once you confirm it. Subscribing is voluntary
  and you can leave the list at any time.
