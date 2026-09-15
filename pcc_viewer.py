# PCC-Viewer/pcc_viewer.py
"""
PCC-Viewer -- Standalone GNSS Antenna Phase Center Correction Visualization Tool

Provides stereographic projections and elevation-dependent plots of PCC/PCV
patterns from ANTEX files. Supports both absolute (single file) and
differential (DPCC) views.

Developed for IfE (Institut fuer Erdmessung), Leibniz Universitaet Hannover.

Usage:
    python pcc_viewer.py                   # Launch GUI
    python pcc_viewer.py --file1 a.atx     # Pre-load file

Requires: numpy, matplotlib, ttkbootstrap
"""

import sys
import os
import tkinter as tk
from tkinter import filedialog, messagebox
import numpy as np

# --- Bootstrap path for importing PCC-Explorer's data_io ---
# The ANTEX reader is taken from ./src, or from a PCC-Explorer checkout placed
# next to this folder as ImpactOfDeltaPCC/.
_viewer_dir = os.path.dirname(os.path.abspath(__file__))
_hiwi_dir = os.path.dirname(_viewer_dir)
_pcc_explorer_dir = os.path.join(_hiwi_dir, 'ImpactOfDeltaPCC')

# For PyInstaller exe: also check inside _MEIPASS and exe directory
try:
    _exe_dir = os.path.dirname(sys.executable)
except Exception:
    _exe_dir = _viewer_dir

# Try multiple paths for the src module
for _try_path in [_pcc_explorer_dir, _viewer_dir, _exe_dir]:
    if _try_path not in sys.path:
        sys.path.insert(0, _try_path)
try:
    _meipass = getattr(sys, '_MEIPASS', None)
    if _meipass and _meipass not in sys.path:
        sys.path.insert(0, _meipass)
except Exception:
    pass

try:
    from src.data_io import read_antex_file
    print("[PCC-Viewer] Using PCC-Explorer's ANTEX parser")
except ImportError:
    print("[PCC-Viewer] WARNING: Could not import PCC-Explorer's data_io.")
    print("             Make sure ImpactOfDeltaPCC/ is a sibling folder.")
    read_antex_file = None

# Resolve default ANTEX data directory (works for dev + exe)
def _find_antex_dir():
    """Find the data/antex/ directory, checking exe-local and sibling paths."""
    candidates = [
        os.path.join(_exe_dir, 'data', 'antex'),       # dist/PCC-Viewer/data/antex/
        os.path.join(_viewer_dir, 'data', 'antex'),     # dev: PCC-Viewer/data/antex/
        os.path.join(_pcc_explorer_dir, 'data', 'antex'),  # sibling: ImpactOfDeltaPCC/data/antex/
    ]
    for c in candidates:
        if os.path.isdir(c):
            return c
    return None

_default_antex_dir = _find_antex_dir()

from viewer_plots import (
    plot_pcc_stereographic, plot_dpcc_elevation,
    plot_pcc_combined, compute_dpcc_grid, get_pcc_grid
)

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from PIL import Image, ImageTk, ImageEnhance

# Shared opt-in dialog for the IfE software mailing list. Never let a missing
# copy stop the program from starting; the canonical file is in shared/.
try:
    import mailing_list
except Exception:
    mailing_list = None

# Version and release date, from this tool's own tool_version.py. The same pair
# sits in the README tag that the PCC-Suite launcher reads, so the launcher no
# longer has to guess a release from a file timestamp.
try:
    import tool_version
    import version_info
    VERSION_TEXT = version_info.about_line(tool_version)
except Exception:
    VERSION_TEXT = "Version: unknown"


# --- PATH HELPER FOR EXE ---
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


class CreateToolTip:
    """Create a tooltip for a given widget."""
    def __init__(self, widget, text='widget info'):
        self.waittime = 500
        self.wraplength = 300
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave)
        self.id = None
        self.tw = None

    def enter(self, event=None):
        self.unschedule()
        self.id = self.widget.after(self.waittime, self.showtip)

    def leave(self, event=None):
        self.unschedule()
        if self.tw:
            self.tw.destroy()
            self.tw = None

    def unschedule(self):
        _id = self.id
        self.id = None
        if _id:
            self.widget.after_cancel(_id)

    def showtip(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.tw, text=self.text, justify='left',
                         background="#ffffe0", relief='solid', borderwidth=1,
                         wraplength=self.wraplength)
        label.pack(ipadx=1)


# =============================================================================
# Signal System Mapping
# =============================================================================

SYSTEM_MAP = {
    'G': 'GPS', 'R': 'GLONASS', 'E': 'Galileo',
    # The ANTEX parser stores BeiDou under 'BDS', so the map must use that key;
    # 'BeiDou' would make every BeiDou lookup return nothing. get_pcc_grid also
    # accepts the aliases.
    'C': 'BDS', 'J': 'QZSS', 'S': 'SBAS'
}

# --- GNSS carrier frequencies (Hz) for IF-LC computation ---
FREQ_MAP = {
    'G01': 1575.42e6, 'G02': 1227.60e6, 'G05': 1176.45e6,
    'R01': 1602.0e6,  'R02': 1246.0e6,
    'E01': 1575.42e6, 'E05': 1176.45e6, 'E06': 1278.75e6,
    'E07': 1207.14e6, 'E08': 1191.795e6,
    'C01': 1575.42e6, 'C02': 1561.098e6, 'C05': 1176.45e6,
    'C06': 1268.52e6, 'C07': 1207.14e6,
}

# Standard IF-LC pairs: (sig1, sig2, display_label)
IFLC_PAIRS = [
    ('G01', 'G02', 'IF:G01/G02'),
    ('G01', 'G05', 'IF:G01/G05'),
    ('E01', 'E05', 'IF:E01/E05'),
    ('R01', 'R02', 'IF:R01/R02'),
]

def iono_free_coeffs(sig1_code, sig2_code):
    """Compute ionosphere-free LC coefficients alpha, beta."""
    f1 = FREQ_MAP.get(sig1_code)
    f2 = FREQ_MAP.get(sig2_code)
    if not f1 or not f2:
        raise ValueError(f"Frequency not defined for {sig1_code} or {sig2_code}")
    gamma = (f1 / f2) ** 2
    alpha = gamma / (gamma - 1)
    beta = -1.0 / (gamma - 1)
    return alpha, beta

SYSTEM_NAMES = {v: k for k, v in SYSTEM_MAP.items()}


def _merge_identical_patterns(patterns: list, labels: list):
    """
    Collapse signals whose pattern is numerically identical into one curve.

    An ANTEX often has no independent calibration for a signal that
    shares a carrier with GPS, so Galileo E01 carries a copy of GPS G01. Drawing
    both put two curves on exactly the same pixels; the legend then advertised
    G01 while only E01 was visible, because the later line covered the earlier
    one. That can be read as a missing frequency.

    The comparison is the same np.array_equal test _detect_copied_calibrations
    already uses, so what is merged here is precisely what the "Copied
    calibration" note explains.

    Labels are joined on their name part, keeping the first PCO bracket:
        'G01 [N=…, E=…, U=…]' + 'E01 [N=…]'  ->  'G01 ≡ E01 [N=…]'

    Returns (patterns, labels, merged) where `merged` lists the groups that were
    collapsed, for the status line.
    """
    kept_patterns, kept_names, kept_suffix, merged = [], [], [], []

    for pattern, label in zip(patterns, labels):
        name, sep, rest = label.partition(' [')
        suffix = (sep + rest) if sep else ''
        for i, existing in enumerate(kept_patterns):
            if existing.shape == pattern.shape and np.array_equal(existing, pattern):
                kept_names[i].append(name)
                break
        else:
            kept_patterns.append(pattern)
            kept_names.append([name])
            kept_suffix.append(suffix)

    out_labels = []
    for names, suffix in zip(kept_names, kept_suffix):
        # Same ordering rule as the "Shared calibration" note: GPS first, so the
        # legend entry and the note read as the same string instead of as two
        # different-looking claims about one group.
        names.sort(key=lambda s: (not s.startswith('G'), s))
        if len(names) > 1:
            merged.append(' ≡ '.join(names))
        out_labels.append(' ≡ '.join(names) + suffix)

    return kept_patterns, out_labels, merged


def _extract_signals(antex_data: dict, antenna_key: str) -> list:
    """Extract list of available signal codes from ANTEX data for an antenna."""
    pco_data = antex_data.get('pco', {}).get(antenna_key, {})
    signals = []
    for system_name, freq_dict in pco_data.items():
        if isinstance(freq_dict, dict):
            for freq_code in sorted(freq_dict.keys()):
                signals.append(freq_code)
    return sorted(signals)


# =============================================================================
# Main Application
# =============================================================================

def _show_ife_contact(parent):
    """
    IfE contact dialog with clickable e-mail and web links.

    Same content and layout as PCC-Explorer's, so every tool in the suite
    presents its contact details identically.
    """
    import webbrowser

    dialog = tk.Toplevel(parent)
    dialog.title("Contact Information")
    dialog.geometry("460x300")
    dialog.resizable(False, False)
    dialog.transient(parent)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding=20)
    frame.pack(fill="both", expand=True)

    ttk.Label(frame, text="Institut für Erdmessung (IfE)",
              font=("Helvetica", 12, "bold")).pack(anchor="w")
    ttk.Label(frame, text="Leibniz Universität Hannover").pack(anchor="w")
    ttk.Label(frame, text="Schneiderberg 50").pack(anchor="w")
    ttk.Label(frame, text="D-30167 Hannover").pack(anchor="w", pady=(0, 15))

    ttk.Label(frame, text="Contact: Dr.-Ing. Johannes Kröger",
              font=("Helvetica", 10, "bold")).pack(anchor="w")

    email_frame = ttk.Frame(frame)
    email_frame.pack(anchor="w", pady=2)
    ttk.Label(email_frame, text="Email: ").pack(side="left")
    email_link = ttk.Label(email_frame, text="kroeger@ife.uni-hannover.de",
                           foreground="#4da6ff", cursor="hand2")
    email_link.pack(side="left")
    email_link.bind("<Button-1>",
                    lambda e: webbrowser.open("mailto:kroeger@ife.uni-hannover.de"))

    web_frame = ttk.Frame(frame)
    web_frame.pack(anchor="w", pady=2)
    ttk.Label(web_frame, text="Web: ").pack(side="left")
    web_link = ttk.Label(web_frame, text="www.ife.uni-hannover.de",
                         foreground="#4da6ff", cursor="hand2")
    web_link.pack(side="left")
    web_link.bind("<Button-1>",
                  lambda e: webbrowser.open("https://www.ife.uni-hannover.de"))

    def _open_mailing_list():
        # Close first. Two stacked modal dialogs each take the grab, and the
        # inner one releasing it would leave this window unresponsive.
        dialog.destroy()
        try:
            parent._show_mailing_list()
        except Exception:
            pass

    buttons = ttk.Frame(frame)
    buttons.pack(pady=(20, 0))
    ttk.Button(buttons, text="Mailing list", command=_open_mailing_list,
               bootstyle="outline-info").pack(side="left", padx=4)
    ttk.Button(buttons, text="Close", command=dialog.destroy,
               bootstyle="secondary").pack(side="left", padx=4)

    # Size to the content, with 460x300 as the minimum: a fixed size would cut
    # the buttons off on systems with larger fonts or display scaling.
    dialog.update_idletasks()
    dialog.geometry("%dx%d" % (max(460, dialog.winfo_reqwidth()),
                               max(300, dialog.winfo_reqheight())))


class PCCViewerApp(ttk.Window):
    """PCC-Viewer GUI Application."""

    def __init__(self):
        super().__init__(themename='darkly')

        self.title("PCC-Viewer")
        self.geometry("750x800")
        self.minsize(650, 700)

        # State
        self.antex_data_1 = None
        self.antex_data_2 = None
        self.file1_path = tk.StringVar()
        self.file2_path = tk.StringVar()
        self.antenna_var_1 = tk.StringVar()
        self.antenna_var_2 = tk.StringVar()
        self.signal_var = tk.StringVar()
        self.signal_checkbuttons = {}   # {signal_code: tk.BooleanVar}
        self.signal_checks_frame = None
        self.mode_var = tk.StringVar(value='single')  # 'single' or 'delta'
        self.show_pcc_var = tk.BooleanVar(value=True)
        self.clim_mode_var = tk.StringVar(value='Auto')
        self.clim_min_var = tk.StringVar(value='-10')
        self.clim_max_var = tk.StringVar(value='10')

        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self._create_widgets()
        self._fit_top_bar()

    def _fit_top_bar(self):
        """
        Widen the window if the header row does not fit in it.

        The window size is set in pixels while the fonts follow the system
        text scaling, so with larger system text the header row can run off the
        edge and truncate its buttons. Measuring what the row needs is the only
        thing that holds on any display.
        """
        try:
            bar = getattr(self, "_top_bar", None)
            if bar is None:
                return
            self.update_idletasks()
            need = bar.winfo_reqwidth() + 8
            if need <= self.winfo_width():
                return
            height = self.winfo_height()
            self.geometry("%dx%d" % (need, height))
            min_w, min_h = self.minsize()
            if need > min_w:
                self.minsize(need, min_h)
        except Exception as exc:
            print("[WARNING] Could not fit the header row: %s" % exc)

    def _on_closing(self):
        self.destroy()

    def _create_widgets(self):
        """Build the GUI layout."""
        # === TOP BAR (matching PCC-Explorer / RINEX-Masker) ===
        top_bar = ttk.Frame(self, padding=10)
        top_bar.pack(fill='x')
        # Kept so the window can be widened if this row does not fit.
        self._top_bar = top_bar

        # Left: IfE logo + title
        left_frame = ttk.Frame(top_bar)
        left_frame.pack(side='left')

        self.logo_img = None
        ife_logo_path = resource_path(os.path.join('assets', 'ife_logo.png'))
        if os.path.exists(ife_logo_path):
            try:
                pil_image = Image.open(ife_logo_path)
                aspect = pil_image.width / pil_image.height
                h = 45
                resized = pil_image.resize((int(h * aspect), h), Image.Resampling.LANCZOS)
                self.logo_img = ImageTk.PhotoImage(resized)
                ttk.Label(left_frame, image=self.logo_img).pack(side='left', padx=(0, 12))
            except Exception:
                pass

        text_frame = ttk.Frame(left_frame)
        text_frame.pack(side='left')
        ttk.Label(text_frame, text="PCC-Viewer", font=('Helvetica', 18, 'bold')).pack(anchor='w')
        ttk.Label(text_frame, text="Institut f\u00fcr Erdmessung (IfE)", font=('Helvetica', 10), bootstyle='light').pack(anchor='w')

        # Right: LUH logo
        self.luh_logo_img = None
        luh_logo_path = resource_path(os.path.join('assets', 'luh_logo.png'))
        if os.path.exists(luh_logo_path):
            try:
                pil_luh = Image.open(luh_logo_path)
                h = 50
                aspect = pil_luh.width / pil_luh.height
                resized_luh = pil_luh.resize((int(h * aspect), h), Image.Resampling.LANCZOS)
                enhancer = ImageEnhance.Sharpness(resized_luh)
                final_luh = enhancer.enhance(1.5)
                self.luh_logo_img = ImageTk.PhotoImage(final_luh)
                luh_frame = ttk.Frame(top_bar)
                luh_frame.pack(side='right', padx=(10, 0))
                ttk.Label(luh_frame, image=self.luh_logo_img).pack(side='right')
            except Exception:
                pass

        # Middle-Right: Info buttons
        info_btn_frame = ttk.Frame(top_bar)
        info_btn_frame.pack(side='right', padx=15)
        ttk.Button(info_btn_frame, text='Contact', command=self._show_contact, bootstyle='outline-info').pack(side='left', padx=3)
        ttk.Button(info_btn_frame, text='Information', command=self._show_about, bootstyle='outline-secondary').pack(side='left', padx=3)

        ttk.Separator(self, orient='horizontal').pack(fill='x', pady=(0, 5))

        # Main content frame
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill='both', expand=True)

        # ─── Mode Selection ───
        mode_frame = ttk.LabelFrame(main_frame, text="Analysis Mode", padding=10)
        mode_frame.pack(fill='x', pady=5)

        mode_row = ttk.Frame(mode_frame)
        mode_row.pack(fill='x')
        ttk.Radiobutton(mode_row, text="Single File (Absolute PCC/PCV)",
                        variable=self.mode_var, value='single',
                        command=self._on_mode_change).pack(side='left', padx=10)
        ttk.Radiobutton(mode_row, text="Two Files (ΔPCC Comparison)",
                        variable=self.mode_var, value='delta',
                        command=self._on_mode_change).pack(side='left', padx=10)

        # ─── File Selection ───
        file_frame = ttk.LabelFrame(main_frame, text="ANTEX Files", padding=10)
        file_frame.pack(fill='x', pady=5)

        # File 1
        f1_row = ttk.Frame(file_frame)
        f1_row.pack(fill='x', pady=3)
        ttk.Label(f1_row, text="File 1:", width=8).pack(side='left')
        ttk.Entry(f1_row, textvariable=self.file1_path, width=50).pack(side='left', fill='x', expand=True, padx=5)
        ttk.Button(f1_row, text="Browse", command=lambda: self._browse_file(1)).pack(side='left')

        # File 2
        self.f2_row = ttk.Frame(file_frame)
        self.f2_row.pack(fill='x', pady=3)
        ttk.Label(self.f2_row, text="File 2:", width=8).pack(side='left')
        ttk.Entry(self.f2_row, textvariable=self.file2_path, width=50).pack(side='left', fill='x', expand=True, padx=5)
        ttk.Button(self.f2_row, text="Browse", command=lambda: self._browse_file(2)).pack(side='left')

        # ─── Antenna Selection ───
        ant_frame = ttk.LabelFrame(main_frame, text="Antenna Selection", padding=10)
        ant_frame.pack(fill='x', pady=5)

        a1_row = ttk.Frame(ant_frame)
        a1_row.pack(fill='x', pady=3)
        ttk.Label(a1_row, text="File 1:", width=8).pack(side='left')
        self.antenna_combo_1 = ttk.Combobox(a1_row, textvariable=self.antenna_var_1,
                                             state='readonly', width=45)
        self.antenna_combo_1.pack(side='left', fill='x', expand=True, padx=5)
        self.antenna_combo_1.bind('<<ComboboxSelected>>', self._on_antenna_selected)

        self.a2_row = ttk.Frame(ant_frame)
        self.a2_row.pack(fill='x', pady=3)
        ttk.Label(self.a2_row, text="File 2:", width=8).pack(side='left')
        self.antenna_combo_2 = ttk.Combobox(self.a2_row, textvariable=self.antenna_var_2,
                                             state='readonly', width=45)
        self.antenna_combo_2.pack(side='left', fill='x', expand=True, padx=5)

        # ─── Signal Selection (Checkbox UI) ───
        sig_frame = ttk.LabelFrame(main_frame, text="Signal / Frequency Selection", padding=10)
        sig_frame.pack(fill='x', pady=5)

        # Top row: Select All / Deselect All buttons + info
        sig_top_row = ttk.Frame(sig_frame)
        sig_top_row.pack(fill='x', pady=(0, 5))
        ttk.Button(sig_top_row, text="Select All", command=self._select_all_signals,
                   bootstyle='outline-success', width=12).pack(side='left', padx=(0, 5))
        ttk.Button(sig_top_row, text="Deselect All", command=self._deselect_all_signals,
                   bootstyle='outline-danger', width=12).pack(side='left', padx=5)
        self.signal_info = ttk.Label(sig_top_row, text="", font=('Helvetica', 9))
        self.signal_info.pack(side='left', padx=10)

        # Scrollable checkbox area
        sig_canvas_frame = ttk.Frame(sig_frame)
        sig_canvas_frame.pack(fill='x')
        self.sig_canvas = tk.Canvas(sig_canvas_frame, height=100, highlightthickness=0)
        sig_scrollbar = ttk.Scrollbar(sig_canvas_frame, orient='vertical', command=self.sig_canvas.yview)
        self.signal_checks_frame = ttk.Frame(self.sig_canvas)
        self.signal_checks_frame.bind('<Configure>',
            lambda e: self.sig_canvas.configure(scrollregion=self.sig_canvas.bbox('all')))
        self.sig_canvas.create_window((0, 0), window=self.signal_checks_frame, anchor='nw')
        self.sig_canvas.configure(yscrollcommand=sig_scrollbar.set)
        self.sig_canvas.pack(side='left', fill='x', expand=True)
        sig_scrollbar.pack(side='right', fill='y')

        # Note shown when a constellation's calibration is a copy of GPS (i.e. the
        # ANTEX has no independent calibration for that signal). Keeps identical
        # Galileo/GPS patterns from looking like a bug.
        self.calib_note = ttk.Label(sig_frame, text="", font=('Helvetica', 8),
                                    bootstyle='warning', wraplength=760, justify='left')
        self.calib_note.pack(fill='x', pady=(4, 0))

        # Also keep a hidden combobox for single-signal backward compat
        self.signal_combo = ttk.Combobox(sig_frame, textvariable=self.signal_var,
                                          state='readonly', width=20)
        # Don't pack it — it's only used internally

        # ─── Plot Options ───
        opt_frame = ttk.LabelFrame(main_frame, text="Plot Options", padding=10)
        opt_frame.pack(fill='x', pady=5)

        opt_row1 = ttk.Frame(opt_frame)
        opt_row1.pack(fill='x', pady=2)
        self.pcc_pcv_btn = ttk.Checkbutton(opt_row1, text="Show PCC",
                        variable=self.show_pcc_var, bootstyle='success-round-toggle',
                        command=self._update_pcc_toggle_label)
        self.pcc_pcv_btn.pack(side='left', padx=10)
        # A companion label makes the "other side" of the toggle explicit
        # Show which quantity is active and what toggling gives.
        self.pcc_pcv_state_label = ttk.Label(opt_row1, text="", font=('Helvetica', 9))
        self.pcc_pcv_state_label.pack(side='left', padx=(0, 10))
        CreateToolTip(self.pcc_pcv_btn,
                      'Toggle ON = PCC (= \u2212PCO\u00b7e + PCV)\n'
                      'Toggle OFF = raw PCV\n\n'
                      'Tip: PCC is usually dominated by the vertical PCO, which is\n'
                      'much larger than the pattern itself, so different frequencies\n'
                      'can look near-identical. How large it is depends on the\n'
                      'antenna. Switch to PCV to see the per-frequency differences.')
        self._update_pcc_toggle_label()

        opt_row2 = ttk.Frame(opt_frame)
        opt_row2.pack(fill='x', pady=2)
        ttk.Label(opt_row2, text="Limits:").pack(side='left', padx=10)
        ttk.Radiobutton(opt_row2, text="Auto", variable=self.clim_mode_var,
                        value='Auto').pack(side='left', padx=5)
        ttk.Radiobutton(opt_row2, text="Custom", variable=self.clim_mode_var,
                        value='Custom').pack(side='left', padx=5)
        ttk.Label(opt_row2, text="Min:").pack(side='left', padx=(15, 2))
        ttk.Entry(opt_row2, textvariable=self.clim_min_var, width=8).pack(side='left')
        ttk.Label(opt_row2, text="Max:").pack(side='left', padx=(10, 2))
        ttk.Entry(opt_row2, textvariable=self.clim_max_var, width=8).pack(side='left')

        # ─── Action Buttons ───
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=15)

        self.btn_stereo = ttk.Button(
            btn_frame, text="Stereographic Plot",
            command=self._plot_stereographic,
            bootstyle='success')
        self.btn_stereo.pack(side='left', padx=5, expand=True, fill='x')

        self.btn_elevation = ttk.Button(
            btn_frame, text="Elevation Plot",
            command=self._plot_elevation,
            bootstyle='info')
        self.btn_elevation.pack(side='left', padx=5, expand=True, fill='x')

        self.btn_combined = ttk.Button(
            btn_frame, text="Combined View",
            command=self._plot_combined,
            bootstyle='warning')
        self.btn_combined.pack(side='left', padx=5, expand=True, fill='x')

        # Close All Figures button
        btn_frame2 = ttk.Frame(main_frame)
        btn_frame2.pack(fill='x', pady=5)
        ttk.Button(btn_frame2, text="Close All Figures",
                   command=self._close_all_figures,
                   bootstyle='danger-outline').pack(side='right', padx=5)

        # ─── Status Bar ───
        self.status_var = tk.StringVar(value="Ready — Load an ANTEX file to begin")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var,
                               font=('Helvetica', 9), relief='sunken', padding=5)
        status_bar.pack(fill='x', pady=(10, 0))

        # Apply initial mode state
        self._on_mode_change()

    # ─── Event Handlers ──────────────────────────────────────────────────

    def _on_mode_change(self):
        """Show/hide File 2 row based on mode."""
        if self.mode_var.get() == 'single':
            self.f2_row.pack_forget()
            self.a2_row.pack_forget()
        else:
            self.f2_row.pack(fill='x', pady=3)
            self.a2_row.pack(fill='x', pady=3)

    def _select_all_signals(self):
        """Check all signal checkboxes."""
        for var in self.signal_checkbuttons.values():
            var.set(True)

    def _deselect_all_signals(self):
        """Uncheck all signal checkboxes."""
        for var in self.signal_checkbuttons.values():
            var.set(False)

    def _get_selected_signals(self):
        """Return list of currently checked signals."""
        return [sig for sig, var in self.signal_checkbuttons.items() if var.get()]

    def _browse_file(self, file_num: int):
        """Open file dialog for ANTEX file selection."""
        # Try exe-local data/antex first, then PCC-Explorer sibling
        initial_dir = _default_antex_dir or _hiwi_dir

        filepath = filedialog.askopenfilename(
            title=f"Select ANTEX File {file_num}",
            initialdir=initial_dir,
            filetypes=[("ANTEX files", "*.atx *.ATX *.atx2"), ("All files", "*.*")]
        )
        if not filepath:
            return

        if file_num == 1:
            self.file1_path.set(filepath)
        else:
            self.file2_path.set(filepath)

        self._load_antex_file(file_num, filepath)

    def _load_antex_file(self, file_num: int, filepath: str):
        """Parse ANTEX file and populate antenna dropdown."""
        if read_antex_file is None:
            messagebox.showerror("Import Error",
                                 "Cannot find PCC-Explorer's ANTEX parser.\n"
                                 "Make sure ImpactOfDeltaPCC/ is a sibling folder.")
            return

        try:
            self.status_var.set(f"Loading {os.path.basename(filepath)}...")
            self.update_idletasks()

            antex_data = read_antex_file(filepath)

            if not antex_data or not antex_data.get('pco'):
                messagebox.showerror("Parse Error", f"No antenna data found in:\n{filepath}")
                return

            antenna_keys = sorted(antex_data.get('metadata', {}).keys())

            if file_num == 1:
                self.antex_data_1 = antex_data
                self.antenna_combo_1['values'] = antenna_keys
                if antenna_keys:
                    self.antenna_var_1.set(antenna_keys[0])
                    self._on_antenna_selected()
            else:
                self.antex_data_2 = antex_data
                self.antenna_combo_2['values'] = antenna_keys
                if antenna_keys:
                    # Try to match File 1 antenna in File 2
                    ant1 = self.antenna_var_1.get()
                    if ant1 in antenna_keys:
                        self.antenna_var_2.set(ant1)
                    else:
                        self.antenna_var_2.set(antenna_keys[0])
                # Rebuild the signal list now that File 2 is known.
                # Without this the checkboxes keep File 1's signals, so a
                # calibration that has Galileo offers E01 even when File 2 has
                # only GPS and GLONASS — and any ΔPCC of it can only fail. In
                # ΔPCC mode _populate_signals intersects the two files, which is
                # what the user should be offered.
                if self.antex_data_1 and self.antenna_var_1.get():
                    self._on_antenna_selected()

            version = antex_data.get('antex_version', '1.4')
            n_ant = len(antenna_keys)
            self.status_var.set(
                f"File {file_num}: {os.path.basename(filepath)} — "
                f"ANTEX v{version}, {n_ant} antenna(s)")

        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load file:\n{e}")
            self.status_var.set("Error loading file")

    def _on_antenna_selected(self, event=None):
        """Update signal checkbox list when antenna is selected."""
        if not self.antex_data_1:
            return

        ant_key = self.antenna_var_1.get()
        if not ant_key:
            return

        signals = _extract_signals(self.antex_data_1, ant_key)

        # If delta mode with File 2 loaded, intersect signals
        if self.mode_var.get() == 'delta' and self.antex_data_2:
            ant_key_2 = self.antenna_var_2.get()
            if ant_key_2:
                signals_2 = _extract_signals(self.antex_data_2, ant_key_2)
                signals = sorted(set(signals) & set(signals_2))
                self.signal_info.config(text=f"{len(signals)} common signals between files")
            else:
                self.signal_info.config(text=f"{len(signals)} signals from File 1")
        else:
            self.signal_info.config(text=f"{len(signals)} signals from File 1")

        # Keep combobox in sync for single-signal plots
        self.signal_combo['values'] = signals
        if signals:
            self.signal_var.set(signals[0])

        # Rebuild checkbox UI
        for widget in self.signal_checks_frame.winfo_children():
            widget.destroy()
        self.signal_checkbuttons.clear()

        # Group signals by system
        systems = {}
        for sig in signals:
            sys_char = sig[0].upper() if sig else '?'
            sys_name = SYSTEM_MAP.get(sys_char, sys_char)
            systems.setdefault(sys_name, []).append(sig)

        col = 0
        for sys_name in sorted(systems.keys()):
            # System header
            ttk.Label(self.signal_checks_frame, text=f"  {sys_name}",
                      font=('Helvetica', 9, 'bold')).grid(
                          row=0, column=col, padx=(8, 2), pady=(0, 2), sticky='w')
            for row_idx, sig in enumerate(systems[sys_name], start=1):
                var = tk.BooleanVar(value=True)  # Default: all selected
                self.signal_checkbuttons[sig] = var
                ttk.Checkbutton(self.signal_checks_frame, text=sig,
                                variable=var).grid(
                                    row=row_idx, column=col, padx=(8, 2), sticky='w')
            col += 1

        # --- Add IF-LC checkboxes if both constituent signals are available ---
        iflc_available = []
        for sig1, sig2, label in IFLC_PAIRS:
            if sig1 in signals and sig2 in signals:
                iflc_available.append((sig1, sig2, label))

        if iflc_available:
            ttk.Label(self.signal_checks_frame, text="  IF-LC",
                      font=('Helvetica', 9, 'bold')).grid(
                          row=0, column=col, padx=(8, 2), pady=(0, 2), sticky='w')
            for row_idx, (sig1, sig2, label) in enumerate(iflc_available, start=1):
                var = tk.BooleanVar(value=False)  # Default: unchecked
                iflc_code = f'IF_{sig1}_{sig2}'
                self.signal_checkbuttons[iflc_code] = var
                ttk.Checkbutton(self.signal_checks_frame, text=label,
                                variable=var).grid(
                                    row=row_idx, column=col, padx=(8, 2), sticky='w')
            col += 1

        # Flag any non-GPS signals that are byte-identical copies of a GPS signal
        self._update_calibration_note(self.antex_data_1, ant_key)

    def _update_calibration_note(self, antex_data, ant_key):
        """
        Explain every set of signals that share one calibration in this file.

        The elevation plot merges *any* identical curves, so the note lists every
        group, not only non-GPS ≡ GPS pairs. An antenna like JAVRINGANT_G5T JAVC
        has groups such as "R01 ≡ R04", "C07 ≡ E07" and "E06 ≡ J06"; a legend that
        shows a merge the note cannot account for is exactly the confusion this
        note exists to prevent, so both come from the same grouping.
        """
        if not hasattr(self, 'calib_note'):
            return
        groups = self._detect_copied_calibrations(antex_data, ant_key)
        if groups:
            txt = ", ".join("≡".join(g) for g in groups)
            self.calib_note.config(
                text=("ℹ Shared calibration: " + txt +
                      " — these signals have no independent calibration in this "
                      "file (they share a carrier frequency, or one pattern was "
                      "used for several signals), so their curves coincide and "
                      "each set is drawn once (expected, not an error)."))
        else:
            self.calib_note.config(text="")

    def _detect_copied_calibrations(self, antex_data, ant_key):
        """
        Groups of signals whose PCO *and* PCV are byte-identical for this antenna.

        Returns [(sig, sig, ...), ...] — GPS first inside a group where present,
        since "E01 ≡ G01" reads as "Galileo copied from GPS", which is the usual
        cause. Groups of two or more only; a signal with its own calibration is
        not reported.

        Signals are compared across all constellations, not only against GPS, so
        sharing *between* other constellations (R01 ≡ R04 on GLONASS FDMA channels,
        C07 ≡ E07, E06 ≡ J06) is reported too, matching what the elevation plot
        merges.
        """
        pco_by = (antex_data or {}).get('pco', {}).get(ant_key, {})
        pcv_by = (antex_data or {}).get('pcv', {}).get(ant_key, {})

        entries = []
        for system, freqs in pcv_by.items():
            for freq, pcv in freqs.items():
                pco = pco_by.get(system, {}).get(freq)
                if pco is None or pcv is None:
                    continue
                entries.append((freq, np.asarray(pco), np.asarray(pcv)))
        entries.sort(key=lambda e: e[0])

        groups, used = [], set()
        for i, (name, pco, pcv) in enumerate(entries):
            if name in used:
                continue
            group = [name]
            for other, opco, opcv in entries[i + 1:]:
                if other in used:
                    continue
                if (pco.shape == opco.shape and pcv.shape == opcv.shape
                        and np.array_equal(pco, opco) and np.array_equal(pcv, opcv)):
                    group.append(other)
                    used.add(other)
            if len(group) > 1:
                used.add(name)
                group.sort(key=lambda s: (not s.startswith('G'), s))
                groups.append(tuple(group))
        return groups

    # ─── Plotting Actions ────────────────────────────────────────────────

    def _get_color_limits(self):
        """Get color limits based on user setting."""
        if self.clim_mode_var.get() == 'Custom':
            try:
                return (float(self.clim_min_var.get()), float(self.clim_max_var.get()))
            except ValueError:
                return None
        return None

    def _compute_iflc_grid(self, ant_key, sig1, sig2, apply_pcc=True, antex_data=None):
        """
        Compute ionosphere-free linear combination PCC/PCV grid.

        PCC_IF = alpha * PCC_f1 + beta * PCC_f2

        Returns: (iflc_grid, iflc_pco, dazi, dzen)
        """
        sys1 = SYSTEM_MAP.get(sig1[0].upper())
        sys2 = SYSTEM_MAP.get(sig2[0].upper())

        # antex_data defaults to File 1. ΔPCC mode passes File 2 as well, so an
        # IF-LC combination can be differenced between the two calibrations
        # instead of being silently dropped.
        data = self.antex_data_1 if antex_data is None else antex_data

        pcv1, pco1, dazi, dzen = get_pcc_grid(data, ant_key, sys1, sig1)
        pcv2, pco2, _, _ = get_pcc_grid(data, ant_key, sys2, sig2)

        if pcv1 is None or pcv2 is None:
            raise ValueError(f"Missing PCV data for {sig1} or {sig2}")

        alpha, beta = iono_free_coeffs(sig1, sig2)

        # Handle different grid sizes by resampling pcv2 to pcv1's shape
        if pcv1.shape != pcv2.shape:
            from scipy.interpolate import RegularGridInterpolator
            n_azi2, n_zen2 = pcv2.shape
            az2 = np.linspace(0, 360, n_azi2)
            zen2 = np.linspace(0, 90, n_zen2)
            n_azi1, n_zen1 = pcv1.shape
            az1 = np.linspace(0, 360, n_azi1)
            zen1 = np.linspace(0, 90, n_zen1)
            interp = RegularGridInterpolator((az2, zen2), pcv2,
                                             method='linear', bounds_error=False, fill_value=0.0)
            AZ, ZEN = np.meshgrid(az1, zen1, indexing='ij')
            pcv2 = interp(np.array([AZ.ravel(), ZEN.ravel()]).T).reshape(pcv1.shape)

        if apply_pcc and pco1 is not None and pco2 is not None:
            # Compute full PCC for each, then combine
            n_azi, n_zen = pcv1.shape
            az_vec = np.linspace(0, 360, n_azi)
            el_vec = np.linspace(90, 0, n_zen)
            AZ, EL = np.meshgrid(az_vec, el_vec, indexing='ij')
            EV_N = np.cos(np.radians(AZ)) * np.cos(np.radians(EL))
            EV_E = np.sin(np.radians(AZ)) * np.cos(np.radians(EL))
            EV_U = np.sin(np.radians(EL))

            pcc1 = -(pco1[0]*EV_N + pco1[1]*EV_E + pco1[2]*EV_U) + pcv1
            pcc2 = -(pco2[0]*EV_N + pco2[1]*EV_E + pco2[2]*EV_U) + pcv2
            iflc_grid = alpha * pcc1 + beta * pcc2
        else:
            # Raw PCV combination
            iflc_grid = alpha * pcv1 + beta * pcv2

        # Compute IF-LC PCO
        iflc_pco = None
        if pco1 is not None and pco2 is not None:
            iflc_pco = alpha * np.array(pco1) + beta * np.array(pco2)

        return iflc_grid, iflc_pco, dazi, dzen

    def _get_current_data(self):
        """
        Get the current PCV/PCO data based on selections.

        Returns:
            Tuple of (pcv_grid, pco_mm, dazi, dzen, antenna_name, signal) or raises ValueError.
        """
        if not self.antex_data_1:
            raise ValueError("No ANTEX file loaded. Please load File 1.")

        ant_key = self.antenna_var_1.get()

        # Always prefer the first checked signal over the hidden combobox
        selected = self._get_selected_signals()
        if selected:
            signal = selected[0]
            self.signal_var.set(signal)
        else:
            signal = self.signal_var.get()

        if not ant_key:
            raise ValueError("No antenna selected.")
        if not signal:
            raise ValueError("No signal selected. Use the checkboxes to select at least one signal.")

        # Determine system from signal code
        sys_char = signal[0].upper() if signal else None
        system = SYSTEM_MAP.get(sys_char)
        if not system:
            raise ValueError(f"Unknown system for signal '{signal}'")

        pcv, pco, dazi, dzen = get_pcc_grid(self.antex_data_1, ant_key, system, signal)
        if pcv is None:
            raise ValueError(f"No PCV data for {ant_key}/{system}/{signal}")

        # Get antenna display name and serial
        meta = self.antex_data_1.get('metadata', {}).get(ant_key, {})
        ant_name = meta.get('type', ant_key).strip()
        ant_serial = meta.get('serial', '').strip()

        return pcv, pco, dazi, dzen, ant_name, signal, ant_serial

    def _make_title(self, ant_name, ant_serial, suffix=''):
        """Build a figure title with antenna name and serial number."""
        title = ant_name
        if ant_serial and ant_serial.upper() != 'TYPEMEAN':
            title += f' (S/N: {ant_serial})'
        if suffix:
            title += f' \u2014 {suffix}'
        return title

    def _update_pcc_toggle_label(self):
        """Keep the PCC/PCV toggle text in sync with its state.

        Note: it can look as though the software saved some old
        data, but when i used the option 'Show PCV', still PCC ... were shown."
        Nothing was cached. The caption named the CURRENT STATE while looking
        like a button that names an ACTION: when it read "Show PCV" the toggle
        was already off and PCV was on screen, so anyone who wanted PCV clicked
        it and got PCC. The caption now names the quantity on screen, and the
        wording next to it says what clicking will do.
        """
        if self.show_pcc_var.get():
            self.pcc_pcv_btn.configure(text="PCC")
            self.pcc_pcv_state_label.configure(
                text="(showing PCC, click the toggle to switch to PCV)")
        else:
            self.pcc_pcv_btn.configure(text="PCV")
            self.pcc_pcv_state_label.configure(
                text="(showing PCV, click the toggle to switch to PCC)")

    def _format_pco_text(self, pco):
        """Format PCO vector as annotation text."""
        if pco is None:
            return None
        return f'PCO [mm]: N={pco[0]:.2f}  E={pco[1]:.2f}  U={pco[2]:.2f}'

    def _format_pco_brackets(self, pco):
        """Format PCO vector compactly for legend entries, e.g. '[N=1.20, E=-0.80, U=95.40]'."""
        if pco is None:
            return ''
        return f' [N={pco[0]:.2f}, E={pco[1]:.2f}, U={pco[2]:.2f}]'

    def _plot_stereographic(self):
        """Plot stereographic projection — single signal or multi-signal grid."""
        try:
            if self.mode_var.get() == 'delta':
                self._plot_delta_stereographic()
                return

            if not self.antex_data_1:
                raise ValueError("No ANTEX file loaded.")

            ant_key = self.antenna_var_1.get()
            if not ant_key:
                raise ValueError("No antenna selected.")

            signals = self._get_selected_signals()
            if not signals:
                raise ValueError("No signals selected.")

            meta = self.antex_data_1.get('metadata', {}).get(ant_key, {})
            ant_name = meta.get('type', ant_key).strip()
            ant_serial = meta.get('serial', '').strip()
            limits = self._get_color_limits()

            if len(signals) == 1:
                sig = signals[0]

                # Handle IF-LC for single stereographic
                if sig.startswith('IF_'):
                    parts = sig.split('_')
                    if len(parts) == 3:
                        s1, s2 = parts[1], parts[2]
                        iflc_grid, iflc_pco, dazi, dzen = self._compute_iflc_grid(
                            ant_key, s1, s2,
                            apply_pcc=self.show_pcc_var.get())
                        self.status_var.set(f"Plotting IF-LC stereographic...")
                        self.update_idletasks()
                        plot_pcc_stereographic(
                            iflc_grid, None, dazi, dzen,
                            signal_label='IF-LC [mm]',
                            limits=limits,
                            show_pcc=False,
                            title=self._make_title(ant_name, ant_serial, f'IF:{s1}/{s2}'),
                            pco_text=self._format_pco_text(iflc_pco) if iflc_pco is not None else None
                        )
                        self.status_var.set(f"IF-LC stereographic shown")
                else:
                    self.signal_var.set(sig)
                    pcv, pco, dazi, dzen, _, _, _ = self._get_current_data()

                    pco_text = None
                    if not self.show_pcc_var.get() and pco is not None:
                        pco_text = self._format_pco_text(pco)

                    self.status_var.set(f"Plotting stereographic: {ant_name} / {sig}...")
                    self.update_idletasks()

                    plot_pcc_stereographic(
                        pcv, pco, dazi, dzen,
                        signal_label='PCC [mm]' if self.show_pcc_var.get() else 'PCV [mm]',
                        limits=limits,
                        show_pcc=self.show_pcc_var.get(),
                        title=self._make_title(ant_name, ant_serial, sig),
                        pco_text=pco_text
                    )
                    self.status_var.set(f"Stereographic plot shown: {ant_name} / {sig}")
            else:
                # Multi-signal grid
                self._plot_all_signals_stereo(signals, ant_key, ant_name, ant_serial, limits)

        except Exception as e:
            messagebox.showerror("Plot Error", str(e))
            self.status_var.set("Error")

    def _delta_signal_label(self, sig):
        """Human-readable label for a signal or IF-LC code in ΔPCC mode."""
        if sig.startswith('IF_'):
            parts = sig.split('_')
            if len(parts) == 3:
                return f'IF:{parts[1]}/{parts[2]}'
        return sig

    def _compute_delta_grid(self, sig, ant_key_1, ant_key_2, apply_pcc=None):
        """
        ΔPCC (or ΔPCV) grid for one selected entry, plain signal or IF-LC.

        Returns (delta_grid, dazi, dzen). Raises ValueError with a readable
        message if the signal is missing from either file.

        With 'Show PCV' enabled this returns the ΔPCV grid, otherwise the full
        ΔPCC grid, so every ΔPCC view follows the toggle. `apply_pcc` defaults to
        the toggle's own state.
        """
        if apply_pcc is None:
            apply_pcc = self.show_pcc_var.get()

        if sig.startswith('IF_'):
            parts = sig.split('_')
            if len(parts) != 3:
                raise ValueError(f"Unrecognised IF-LC code: {sig}")
            s1, s2 = parts[1], parts[2]
            grid1, _, dazi, dzen = self._compute_iflc_grid(
                ant_key_1, s1, s2, apply_pcc=apply_pcc, antex_data=self.antex_data_1)
            grid2, _, _, _ = self._compute_iflc_grid(
                ant_key_2, s1, s2, apply_pcc=apply_pcc, antex_data=self.antex_data_2)
            if grid1.shape != grid2.shape:
                raise ValueError(
                    f"{self._delta_signal_label(sig)}: the two files use different "
                    f"grid spacings ({grid1.shape} vs {grid2.shape})."
                )
            return grid1 - grid2, dazi, dzen

        system = SYSTEM_MAP.get(sig[0].upper())
        if not system:
            raise ValueError(f"Unknown constellation for signal '{sig}'.")

        if apply_pcc:
            delta = compute_dpcc_grid(self.antex_data_1, self.antex_data_2,
                                      ant_key_1, ant_key_2, system, sig)
            _, _, dazi, dzen = get_pcc_grid(self.antex_data_1, ant_key_1, system, sig)
            return delta, dazi, dzen

        # ΔPCV: the pattern difference alone, with no PCO projection.
        pcv1, _, dazi, dzen = get_pcc_grid(self.antex_data_1, ant_key_1, system, sig)
        pcv2, _, _, _ = get_pcc_grid(self.antex_data_2, ant_key_2, system, sig)
        if pcv1 is None or pcv2 is None:
            raise ValueError(
                f"{self._delta_signal_label(sig)}: no PCV data in "
                f"{'File 1' if pcv1 is None else 'File 2'}.")
        if pcv1.shape != pcv2.shape:
            raise ValueError(
                f"{self._delta_signal_label(sig)}: the two files use different "
                f"grid spacings ({pcv1.shape} vs {pcv2.shape})."
            )
        return pcv1 - pcv2, dazi, dzen

    def _delta_quantity(self):
        """'ΔPCC' or 'ΔPCV', whichever the PCC/PCV toggle is currently on."""
        return 'ΔPCC' if self.show_pcc_var.get() else 'ΔPCV'

    def _delta_selected_signals(self):
        """
        The signals a ΔPCC plot should draw.

        The ticked checkboxes decide. The hidden legacy combobox
        (`self.signal_var`) is only a fallback: _populate_signals seeds it with
        signals[0] of a SORTED list, which for a file holding E01 and G01 is
        'E01', not a signal the user chose.
        """
        signals = self._get_selected_signals()
        if not signals:
            fallback = self.signal_var.get()
            if not fallback:
                raise ValueError("No signals selected. Tick at least one signal.")
            signals = [fallback]
        return signals

    def _plot_delta_stereographic(self):
        """Plot stereographic ΔPCC between two files, for every selected signal."""
        if not self.antex_data_2:
            messagebox.showerror("Error", "File 2 not loaded for ΔPCC mode.")
            return

        ant_key_1 = self.antenna_var_1.get()
        ant_key_2 = self.antenna_var_2.get()

        try:
            signals = self._delta_selected_signals()

            meta1 = self.antex_data_1.get('metadata', {}).get(ant_key_1, {})
            meta2 = self.antex_data_2.get('metadata', {}).get(ant_key_2, {})
            name1 = meta1.get('type', ant_key_1).strip()
            name2 = meta2.get('type', ant_key_2).strip()
            limits = self._get_color_limits()

            if len(signals) == 1:
                sig = signals[0]
                dpcc, dazi, dzen = self._compute_delta_grid(sig, ant_key_1, ant_key_2)
                label = self._delta_signal_label(sig)
                qty = self._delta_quantity()
                plot_pcc_stereographic(
                    dpcc, None, dazi, dzen,
                    signal_label=f'{qty} {label} [mm]',
                    limits=limits,
                    show_pcc=False,
                    title=f'{qty}: {name1} − {name2} ({label})'
                )
                self.status_var.set(f"{qty} stereographic shown: {label}")
            else:
                self._plot_all_delta_stereo(signals, ant_key_1, ant_key_2,
                                            name1, name2, limits)

        except Exception as e:
            messagebox.showerror("Plot Error", str(e))

    def _plot_all_delta_stereo(self, signals, ant_key_1, ant_key_2,
                               name1, name2, limits):
        """ΔPCC stereographic grid — one panel per selected signal."""
        import matplotlib.pyplot as plt

        qty = self._delta_quantity()
        self.status_var.set(f"Plotting {len(signals)} {qty} views...")
        self.update_idletasks()

        grids, skipped = {}, []
        for sig in signals:
            try:
                grids[sig] = self._compute_delta_grid(sig, ant_key_1, ant_key_2)
            except Exception as e:
                skipped.append(f"{self._delta_signal_label(sig)}: {e}")

        if not grids:
            raise ValueError("None of the selected signals could be compared:\n\n"
                             + "\n".join(skipped))

        # A shared colour scale, so the panels can be compared with each other.
        if limits is None:
            all_vals = np.concatenate([g[0][np.isfinite(g[0])].ravel() for g in grids.values()])
            if all_vals.size:
                vmax = float(np.nanmax(np.abs(all_vals)))
                limits = (-vmax, vmax)

        n = len(signals)
        cols = min(3, n)
        rows = (n + cols - 1) // cols
        fig, axes = plt.subplots(rows, cols, figsize=(7 * cols, 5.5 * rows))
        axes = np.atleast_1d(np.array(axes)).flatten()

        for i, sig in enumerate(signals):
            label = self._delta_signal_label(sig)
            if sig not in grids:
                axes[i].set_title(f'{label} — No Data')
                axes[i].axis('off')
                continue
            dpcc, dazi, dzen = grids[sig]
            plot_pcc_stereographic(
                dpcc, None, dazi, dzen,
                signal_label=f'{qty} [mm]',
                limits=limits,
                show_pcc=False,
                title=label,
                ax=axes[i]
            )

        for j in range(n, len(axes)):
            axes[j].axis('off')

        fig.suptitle(f'{qty}: {name1} − {name2}', fontsize=14, fontweight='bold')
        fig.subplots_adjust(top=0.90, bottom=0.14, wspace=0.45, hspace=0.35)
        plt.show()

        msg = f"{qty} stereographic shown for {len(grids)} signal(s)"
        if skipped:
            msg += f" — skipped {len(skipped)}"
            messagebox.showwarning(
                "Some signals skipped",
                "These selected signals could not be compared:\n\n" + "\n".join(skipped))
        self.status_var.set(msg)

    def _plot_elevation(self):
        """Plot elevation profile — single signal or multi-signal overlay."""
        try:
            if self.mode_var.get() == 'delta':
                self._plot_delta_elevation()
                return

            if not self.antex_data_1:
                raise ValueError("No ANTEX file loaded.")

            ant_key = self.antenna_var_1.get()
            if not ant_key:
                raise ValueError("No antenna selected.")

            signals = self._get_selected_signals()
            if not signals:
                raise ValueError("No signals selected.")

            meta = self.antex_data_1.get('metadata', {}).get(ant_key, {})
            ant_name = meta.get('type', ant_key).strip()
            ant_serial = meta.get('serial', '').strip()
            limits = self._get_color_limits()

            self.status_var.set(f"Plotting elevation: {ant_name} / {len(signals)} signal(s)...")
            self.update_idletasks()

            # Collect patterns for all selected signals
            patterns = []
            labels = []
            first_pco = None

            for sig in signals:
                # Handle IF-LC signals
                if sig.startswith('IF_'):
                    parts = sig.split('_')
                    if len(parts) == 3:
                        s1, s2 = parts[1], parts[2]
                        try:
                            iflc_grid, iflc_pco, dazi, dzen = self._compute_iflc_grid(
                                ant_key, s1, s2,
                                apply_pcc=self.show_pcc_var.get())
                            if first_pco is None:
                                first_pco = iflc_pco
                            patterns.append(iflc_grid)
                            # No alpha in the legend for absolute PCC.
                            # The coefficient describes the combination, not the
                            # pattern being drawn, and it only crowds the entry.
                            labels.append(f'IF:{s1}/{s2}{self._format_pco_brackets(iflc_pco)}')
                        except Exception as e:
                            print(f"IF-LC skip {sig}: {e}")
                    continue

                sys_char = sig[0].upper()
                system = SYSTEM_MAP.get(sys_char)
                if not system:
                    continue

                pcv, pco, dazi, dzen = get_pcc_grid(self.antex_data_1, ant_key, system, sig)
                if pcv is None:
                    continue

                if first_pco is None:
                    first_pco = pco

                n_azi, n_zen = pcv.shape
                az_vec = np.linspace(0, 360, n_azi)
                el_vec = np.linspace(90, 0, n_zen)
                AZ, EL = np.meshgrid(az_vec, el_vec, indexing='ij')

                if self.show_pcc_var.get() and pco is not None:
                    EV_N = np.cos(np.radians(AZ)) * np.cos(np.radians(EL))
                    EV_E = np.sin(np.radians(AZ)) * np.cos(np.radians(EL))
                    EV_U = np.sin(np.radians(EL))
                    pattern = -(pco[0] * EV_N + pco[1] * EV_E + pco[2] * EV_U) + pcv
                else:
                    pattern = pcv.copy()

                patterns.append(pattern)
                labels.append(f'{sig}{self._format_pco_brackets(pco)}')

            if not patterns:
                raise ValueError("No valid patterns found.")

            # Signals that share a carrier with GPS carry a copy of the
            # GPS pattern, so G01 and E01 land on the same pixels and the legend
            # names a line nobody can see. Merge them into one entry.
            patterns, labels, merged = _merge_identical_patterns(patterns, labels)

            # Build title and determine y-label
            ylabel = 'PCC [mm]' if self.show_pcc_var.get() else 'PCV [mm]'
            pco_text = None
            if not self.show_pcc_var.get() and first_pco is not None:
                pco_text = self._format_pco_text(first_pco)

            suffix = 'Elevation Profile'
            if len(signals) == 1:
                suffix = f'Elevation Profile ({signals[0]})'

            plot_dpcc_elevation(
                patterns, labels,
                title=self._make_title(ant_name, ant_serial, suffix),
                ylimits=limits,
                pco_text=pco_text,
                ylabel=ylabel,
                legend_title='Frequency | PCO [mm]'
            )

            status = f"Elevation plot shown ({len(patterns)} curve(s))"
            if merged:
                status += f" — identical patterns merged: {'; '.join(merged)}"
            self.status_var.set(status)

        except Exception as e:
            messagebox.showerror("Plot Error", str(e))
            self.status_var.set("Error")

    def _plot_delta_elevation(self):
        """Plot elevation ΔPCC between two files."""
        if not self.antex_data_2:
            messagebox.showerror("Error", "File 2 not loaded for ΔPCC mode.")
            return

        ant_key_1 = self.antenna_var_1.get()
        ant_key_2 = self.antenna_var_2.get()

        try:
            signals = self._delta_selected_signals()

            meta1 = self.antex_data_1.get('metadata', {}).get(ant_key_1, {})
            meta2 = self.antex_data_2.get('metadata', {}).get(ant_key_2, {})
            name1 = meta1.get('type', ant_key_1).strip()
            name2 = meta2.get('type', ant_key_2).strip()

            patterns, labels, skipped = [], [], []
            dazi = dzen = None
            for sig in signals:
                try:
                    dpcc, d_azi, d_zen = self._compute_delta_grid(sig, ant_key_1, ant_key_2)
                except Exception as e:
                    skipped.append(f"{self._delta_signal_label(sig)}: {e}")
                    continue
                patterns.append(dpcc)
                labels.append(self._delta_signal_label(sig))
                if dazi is None:
                    dazi, dzen = d_azi, d_zen

            if not patterns:
                raise ValueError("None of the selected signals could be compared:\n\n"
                                 + "\n".join(skipped))

            # Identical ΔPCC patterns (a copied calibration such as
            # E01 ≡ G01 differences to exactly the same curve) are merged, so a
            # legend entry cannot name a line that is hidden underneath another.
            patterns, labels, merged = _merge_identical_patterns(patterns, labels)

            qty = self._delta_quantity()
            title = f'{qty}: {name1} − {name2}'
            if len(labels) == 1:
                title += f' ({labels[0]})'

            # Pass the y-label explicitly: plot_dpcc_elevation defaults it to
            # 'ΔPCC [mm]', which would mislabel a ΔPCV plot.
            plot_dpcc_elevation(patterns, labels, dazi=dazi, dzen=dzen, title=title,
                                ylabel=f'{qty} [mm]')

            msg = f"{qty} elevation shown: {', '.join(labels)}"
            if skipped:
                msg += f" — skipped {len(skipped)}"
                messagebox.showwarning(
                    "Some signals skipped",
                    "These selected signals could not be compared:\n\n" + "\n".join(skipped))
            self.status_var.set(msg)

        except Exception as e:
            messagebox.showerror("Plot Error", str(e))

    def _plot_delta_combined(self):
        """Combined stereographic + elevation view for ΔPCC / ΔPCV mode.

        _plot_combined dispatches here when mode_var is 'delta', the same
        three-way pattern as the stereographic and elevation views, so in ΔPCC
        mode the combined view shows the difference rather than File 1's
        absolute PCC.
        """
        if not self.antex_data_2:
            messagebox.showerror("Error", "File 2 not loaded for ΔPCC mode.")
            return

        ant_key_1 = self.antenna_var_1.get()
        ant_key_2 = self.antenna_var_2.get()

        try:
            signals = self._delta_selected_signals()
            qty = self._delta_quantity()

            meta1 = self.antex_data_1.get('metadata', {}).get(ant_key_1, {})
            meta2 = self.antex_data_2.get('metadata', {}).get(ant_key_2, {})
            name1 = meta1.get('type', ant_key_1).strip()
            name2 = meta2.get('type', ant_key_2).strip()
            limits = self._get_color_limits()

            self.status_var.set(
                f"Plotting combined {qty}: {len(signals)} signal(s)...")
            self.update_idletasks()

            patterns, labels, skipped = [], [], []
            dazi = dzen = None
            for sig in signals:
                try:
                    grid, d_azi, d_zen = self._compute_delta_grid(
                        sig, ant_key_1, ant_key_2)
                except Exception as e:
                    skipped.append(f"{self._delta_signal_label(sig)}: {e}")
                    continue
                patterns.append(grid)
                labels.append(self._delta_signal_label(sig))
                if dazi is None:
                    dazi, dzen = d_azi, d_zen

            if not patterns:
                raise ValueError("None of the selected signals could be compared:\n\n"
                                 + "\n".join(skipped))

            plot_pcc_combined(
                patterns[0], patterns, labels,
                dazi, dzen,
                stereo_signal_label=self._stereo_panel_label(labels),
                stereo_limits=limits,
                antenna_name=f'{qty}: {name1} − {name2}',
                ylabel=f'{qty} [mm]',
            )

            msg = f"Combined {qty} shown: {', '.join(labels)}"
            if skipped:
                msg += f"  ({len(skipped)} skipped)"
            self.status_var.set(msg)

        except Exception as e:
            messagebox.showerror("Plot Error", str(e))
            self.status_var.set("Error")

    def _stereo_panel_label(self, labels):
        """Colourbar label for the combined view's stereographic panel.

        It is worth mentioning somewhere that only
        first frequency is shown in combined view for the stereographic
        projection." The elevation panel overlays every selected signal, the
        disc can only show one, and nothing on the figure said so.
        """
        if len(labels) > 1:
            # No brackets here: plot_pcc_combined already wraps this in
            # "ΔPCV Pattern (...)", so a bracketed suffix would nest brackets.
            return f'{labels[0]} [mm], first of {len(labels)} selected'
        return f'{labels[0]} [mm]'

    def _plot_combined(self):
        """Plot combined stereographic + elevation view.

        Behaviour:
          - the elevation panel overlays ALL selected signals;
          - the stereographic panel shows the first selected signal;
          - the right-hand y-axis label reflects PCC/PCV;
          - PCO is not annotated (the full PCC already contains it).
        """
        try:
            if self.mode_var.get() == 'delta':
                self._plot_delta_combined()
                return

            if not self.antex_data_1:
                raise ValueError("No ANTEX file loaded.")

            ant_key = self.antenna_var_1.get()
            if not ant_key:
                raise ValueError("No antenna selected.")

            signals = self._get_selected_signals()
            if not signals:
                raise ValueError("No signals selected.")

            meta = self.antex_data_1.get('metadata', {}).get(ant_key, {})
            ant_name = meta.get('type', ant_key).strip()
            ant_serial = meta.get('serial', '').strip()
            limits = self._get_color_limits()
            show_pcc = self.show_pcc_var.get()

            self.status_var.set(
                f"Plotting combined: {ant_name} / {len(signals)} signal(s)...")
            self.update_idletasks()

            # Build a pattern (full PCC or raw PCV, per the toggle) for every
            # selected signal. The first valid one also feeds the stereographic
            # panel; the elevation panel overlays all of them.
            patterns = []
            labels = []
            first_dazi = first_dzen = None

            for sig in signals:
                if sig.startswith('IF_'):
                    parts = sig.split('_')
                    if len(parts) != 3:
                        continue
                    s1, s2 = parts[1], parts[2]
                    try:
                        grid, _iflc_pco, dazi, dzen = self._compute_iflc_grid(
                            ant_key, s1, s2, apply_pcc=show_pcc)
                    except Exception as e:
                        print(f"IF-LC skip {sig}: {e}")
                        continue
                    patterns.append(grid)
                    labels.append(f'IF:{s1}/{s2}')
                    if first_dazi is None:
                        first_dazi, first_dzen = dazi, dzen
                    continue

                sys_char = sig[0].upper()
                system = SYSTEM_MAP.get(sys_char)
                if not system:
                    continue

                pcv, pco, dazi, dzen = get_pcc_grid(
                    self.antex_data_1, ant_key, system, sig)
                if pcv is None:
                    continue

                if show_pcc and pco is not None:
                    n_azi, n_zen = pcv.shape
                    az_vec = np.linspace(0, 360, n_azi)
                    el_vec = np.linspace(90, 0, n_zen)
                    AZ, EL = np.meshgrid(az_vec, el_vec, indexing='ij')
                    EV_N = np.cos(np.radians(AZ)) * np.cos(np.radians(EL))
                    EV_E = np.sin(np.radians(AZ)) * np.cos(np.radians(EL))
                    EV_U = np.sin(np.radians(EL))
                    pattern = -(pco[0] * EV_N + pco[1] * EV_E + pco[2] * EV_U) + pcv
                else:
                    pattern = pcv.copy()

                patterns.append(pattern)
                labels.append(sig)
                if first_dazi is None:
                    first_dazi, first_dzen = dazi, dzen

            if not patterns:
                raise ValueError("No valid patterns found for the selected signals.")

            ylabel = 'PCC [mm]' if show_pcc else 'PCV [mm]'
            plot_pcc_combined(
                patterns[0], patterns, labels,
                first_dazi, first_dzen,
                stereo_signal_label=self._stereo_panel_label(labels),
                stereo_limits=limits,
                antenna_name=self._make_title(ant_name, ant_serial),
                ylabel=ylabel,
            )

            self.status_var.set(
                f"Combined plot shown: {ant_name} / {len(patterns)} signal(s)")

        except Exception as e:
            messagebox.showerror("Plot Error", str(e))
            self.status_var.set("Error")

    def _plot_all_signals_stereo(self, signals, ant_key, ant_name, ant_serial, limits):
        """Plot stereographic projections for selected signals in a subplot grid."""
        import matplotlib.pyplot as plt

        self.status_var.set(f"Plotting {len(signals)} stereographic views...")
        self.update_idletasks()

        n = len(signals)
        cols = min(3, n)
        rows = (n + cols - 1) // cols

        fig, axes = plt.subplots(rows, cols, figsize=(7 * cols, 5.5 * rows))
        if n == 1:
            axes = np.array([axes])
        axes = axes.flatten()

        # First pass: gather grids, then derive a shared "auto same" color scale
        # so all subplots can be visually compared on equal footing (same
        # min/max limits across all selected frequencies).
        grids = {}
        all_vmin = []
        all_vmax = []

        for sig in signals:
            # IF-LC codes are not system codes: 'IF_G01_G02'[0] is 'I', so the
            # plain lookup below skipped them and the panel read "No Data" even
            # though the elevation plot drew the very same combination.
            if sig.startswith('IF_'):
                parts = sig.split('_')
                if len(parts) != 3:
                    continue
                try:
                    # apply_pcc=False returns the combined PCV together with the
                    # combined PCO, so the shared PCC projection below is applied
                    # exactly once - as it is for an ordinary signal.
                    pcv, pco, dazi, dzen = self._compute_iflc_grid(
                        ant_key, parts[1], parts[2], apply_pcc=False)
                except Exception as e:
                    print(f"IF-LC skip {sig}: {e}")
                    continue
            else:
                sys_char = sig[0].upper()
                system = SYSTEM_MAP.get(sys_char)
                if not system:
                    continue
                pcv, pco, dazi, dzen = get_pcc_grid(self.antex_data_1, ant_key, system, sig)

            if pcv is None:
                continue
            grids[sig] = (pcv, pco, dazi, dzen)

            if self.show_pcc_var.get() and pco is not None:
                n_azi, n_zen = pcv.shape
                az_vec = np.linspace(0, 360, n_azi)
                el_vec = np.linspace(90, 0, n_zen)
                AZ, EL = np.meshgrid(az_vec, el_vec, indexing='ij')
                EV_N = np.cos(np.radians(AZ)) * np.cos(np.radians(EL))
                EV_E = np.sin(np.radians(AZ)) * np.cos(np.radians(EL))
                EV_U = np.sin(np.radians(EL))
                pattern = -(pco[0] * EV_N + pco[1] * EV_E + pco[2] * EV_U) + pcv
            else:
                pattern = pcv
            all_vmin.append(np.nanmin(pattern))
            all_vmax.append(np.nanmax(pattern))

        # In Auto mode, share one color scale across all subplots ("auto same")
        shared_limits = limits
        if limits is None and all_vmin:
            shared_limits = (min(all_vmin), max(all_vmax))

        for i, sig in enumerate(signals):
            if sig not in grids:
                axes[i].set_title(f'{sig} \u2014 No Data')
                axes[i].axis('off')
                continue

            pcv, pco, dazi, dzen = grids[sig]
            pco_text = None
            if not self.show_pcc_var.get() and pco is not None:
                pco_text = self._format_pco_text(pco)

            plot_pcc_stereographic(
                pcv, pco, dazi, dzen,
                signal_label='PCC [mm]' if self.show_pcc_var.get() else 'PCV [mm]',
                limits=shared_limits,
                show_pcc=self.show_pcc_var.get(),
                title=sig,
                pco_text=pco_text,
                ax=axes[i]
            )

        # Hide unused subplots
        for j in range(n, len(axes)):
            axes[j].axis('off')

        fig.suptitle(self._make_title(ant_name, ant_serial), fontsize=14, fontweight='bold')
        # bottom margin gives the PCO box (now below each polar axes) room so it
        # never overlaps the circle/angle labels.
        fig.subplots_adjust(top=0.90, bottom=0.14, wspace=0.45, hspace=0.35)
        plt.show()

        self.status_var.set(f"Stereographic grid shown ({n} signals)")


    def _close_all_figures(self):
        """Close all open matplotlib figure windows."""
        import matplotlib.pyplot as plt
        plt.close('all')
        self.status_var.set("All figures closed.")

    def _show_about(self):
        messagebox.showinfo("Information - PCC-Viewer",
                            "PCC-Viewer\n" + VERSION_TEXT + "\n\n"
                            "Visualizes GNSS antenna Phase Center Corrections\n"
                            "using stereographic projections and elevation\n"
                            "profiles from ANTEX v1.4 and v2.0 files.\n\n"
                            "Single-file (absolute PCC) and two-file (DPCC)\n"
                            "comparison modes available.\n\n"
                            "Institut f\u00fcr Erdmessung (IfE)\n"
                            "Leibniz Universit\u00e4t Hannover\n\n"
                            "License: GNU General Public License v3 (GPLv3)\n\n"
                            "Developers:\n"
                            "  Amr Fawzy, M.Sc.\n"
                            "  Dr.-Ing. Johannes Kr\u00f6ger")

    def _show_contact(self):
        _show_ife_contact(self)

    def _show_mailing_list(self):
        """The mailing list dialog, on request, whatever was answered before."""
        if mailing_list is None:
            messagebox.showwarning(
                'IfE software mailing list',
                'This installation is missing mailing_list.py, so the '
                'subscription dialog cannot be shown. Please report it to '
                'the IfE, the Contact button has the address.')
            return
        mailing_list.show_on_request(self, 'PCC-Viewer')


# =============================================================================
# Entry Point
# =============================================================================

def main():
    """Launch PCC-Viewer application."""
    # Handle DPI awareness on Windows
    if sys.platform == 'win32':
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    app = PCCViewerApp()
    if mailing_list is not None:
        mailing_list.maybe_show(app, 'PCC-Viewer')
    app.mainloop()


if __name__ == '__main__':
    main()
