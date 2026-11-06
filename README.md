# PCC-Viewer

Look at antenna phase centre patterns, and at the difference between two.

> **Version 1.1.1, released 1 November 2026.** Download the Windows package
> from [Releases](https://github.com/J-kroeger/pcc-viewer/releases/latest), unzip it and start
> `PCC-Viewer.exe`. No installation and no Python required. The full source code is in
> this repository.

## What it does

Opens one ANTEX file and plots its phase centre corrections, or opens two and
plots the difference between them.

Patterns are drawn as stereographic projections over the sky and as elevation
profiles, per signal, with the phase centre offsets shown alongside so the
offset and the variation can be read together.

## Why it exists

There is no universally accepted ground truth for antenna calibrations. The same
antenna calibrated in an anechoic chamber and on a field robot gives different
values, and so does the same antenna calibrated in different years. Before
asking what those differences do to a coordinate, it helps to see them.

For a worked example, the difference between a chamber and a robot calibration
of the same LEIAR25.R4 is about **+1.95 mm at the zenith** and **-1.44 mm at the
horizon** on GPS L1.

## Features

- Single-file mode for absolute PCC and PCV
- Two-file mode for the difference, ΔPCC, between calibrations
- Stereographic sky plots and elevation profiles
- Toggle between PCC and PCV
- Per-signal selection, including ionosphere-free linear combinations
- Phase centre offsets reported with the pattern, not separately


## Running from source

The program is written in Python and was built with Python 3.12.

```
python -m pip install -r requirements.txt
python pcc_viewer.py
```

On Windows, `launch_gui.bat` does the same when no packaged executable is next to it.
The full user guide is in [`readme.txt`](readme.txt).

Example ANTEX files are in `data/antex/`.
The `src/` folder holds the ANTEX reader shared with [PCC-Explorer](https://github.com/J-kroeger/pcc-explorer).

## Part of PCC-Suite

This program is one of seven released together as
[PCC-Suite](https://github.com/J-kroeger/pcc-suite), a collection of open-source programs for GNSS antenna
calibration values from the Institut für Erdmessung (IfE), Leibniz Universität
Hannover. Each is a standalone Windows executable, released and versioned
separately, so you can take only the one you need. No installation, no Python
required.

Archived releases and DOIs are gathered in the Zenodo community
[Open Source Software Packages for GNSS Data Processing](https://zenodo.org/communities/gnss-open-source-solutions).

## Licence

GNU General Public License v3.0 or later. Free to use, share and modify. See
[LICENSE](LICENSE).

## Citation

The method behind the suite and its validation against real PPP solutions are
described in:

> Kröger, J., Kersten, T. & Schön, S. (2026). PCC-Explorer: an open-source
> software tool to assess the impact of GNSS antenna phase center corrections on
> geodetic parameters. *GPS Solutions* **30**, 93. [https://doi.org/10.1007/s10291-026-02056-2](https://doi.org/10.1007/s10291-026-02056-2)

## Stay informed

Release announcements, and warnings when an external data source moves, go to
the institute software mailing list:

```
ife-software@lists.uni-hannover.de
```

Subscribe at <https://lists.uni-hannover.de/sympa/subscribe/ife-software>, or send
the line `subscribe ife-software` and, on the next line, `QUIT` to
<sympa@lists.uni-hannover.de>. The program offers to subscribe you on first
start. You can decline, and you can ask not to be reminded again.

## Contact

**Dr.-Ing. Johannes Kröger**
Institut für Erdmessung (IfE), Leibniz Universität Hannover
Schneiderberg 50, D-30167 Hannover

Email: [kroeger@ife.uni-hannover.de](mailto:kroeger@ife.uni-hannover.de)
Web: [www.ife.uni-hannover.de](https://www.ife.uni-hannover.de)
