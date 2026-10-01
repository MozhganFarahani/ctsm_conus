#!/usr/bin/env python
"""
CTSM CONUS monthly climatology: cache + maps for every history field.

Stage 1  build a monthly climatology (12 x lat x lon per variable) from the h0a
         monthly files and cache it to one NetCDF. Runs once.
Stage 2  plot from the cache:
           --monthly   one figure per variable, 12 subplots, shared color scale
           --seasonal  one figure per variable, 4 subplots (DJF/MAM/JJA/SON)
           --summary   one multi-panel page of domain-mean seasonal cycles

Inputs : control h0a monthly files (paths.lnd_hist("control")) and the field list
         ctsm_control_history_fields.csv next to this script
Outputs: the cache paths.CLIM_CACHE and figures under paths.CLIM_OUT
         (<output root>/climatology/); see README.md in this folder

Examples
    python ctsm_climatology_maps.py                       # build cache, all figures
    python ctsm_climatology_maps.py --monthly             # maps only, reuse cache
    python ctsm_climatology_maps.py --rebuild --vars QRUNOFF TSA H2OSNO
--hist-dir, --outdir and --cache override the input folder, figure folder and cache.
"""

import argparse
import glob
import os
import re
import sys
import warnings

import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config"))
import paths  # analysis/config/paths.py
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from lib.plotting import PROJ, basemap  # analysis/lib/plotting.py

warnings.filterwarnings("ignore", category=RuntimeWarning)

# ----------------------------------------------------------------------------
# paths / run configuration
# ----------------------------------------------------------------------------
DEFAULT_PATHS = {
    "ctsm_hist_dir": paths.lnd_hist("control") + "/",
    # the field list sits next to this script
    "fields_csv": os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "ctsm_control_history_fields.csv"),
    "out_dir": paths.CLIM_OUT,
    "cache_nc": paths.CLIM_CACHE,
}

# analysis window, inclusive, YYYY-MM. First spin-up year already excluded.
START_YM, END_YM = "1981-10", "2018-10"

DPI = 130

# how to collapse a soil-level dimension: "sum" or a list of 0-based level indices
LEVELS = {
    "SOILLIQ": "sum",
    "SOILICE": "sum",
    "TSOI": [0, 4, 9],
    "QIN": [0],
    "QOUT": [0],
}
LEVELS_DEFAULT = [0]

# fluxes whose spatial distribution is log-normal enough to need a log scale
LOG_VARS = {
    "QRUNOFF", "QDRAI", "QOVER", "QH2OSFC", "QDRAI_PERCH", "QFLX_SNOW_DRAIN",
    "RAIN", "SNOW", "H2OSNO", "H2OSFC",
}

# Explicit colour scales, checked before any automatic rule. Keys are BASE field
# names, so "TSOI" covers TSOI_L1/L5/L10 and "SOILLIQ" covers SOILLIQ_total.
#   ("log" | "lin" | "div", vmin, vmax);  None for a limit means "use automatic"
# NOTE on "div": for degC (see PIVOT_UNITS) the limits are honoured as given and
# the scale pivots at 0. For every other unit the scale is forced SYMMETRIC using
# max(|vmin|, |vmax|), so pass symmetric values there or you will be surprised.
VAR_NORM = {
    # --- water fluxes, mm/day. log-normal across three decades ---------------
    "QRUNOFF":         ("log", 0.01, 10.0),
    "QOVER":           ("log", 0.01, 10.0),
    "QDRAI":           ("log", 0.01, 10.0),
    "QH2OSFC":         ("log", 0.001, 5.0),
    "QDRAI_PERCH":     ("log", 0.001, 5.0),
    "QFLX_SNOW_DRAIN": ("log", 0.01, 10.0),
    "RAIN":            ("log", 0.01, 20.0),
    "SNOW":            ("log", 0.01, 10.0),

    # --- ET components, mm/day. linear: range is one decade, not three -------
    "QVEGT":           ("lin", 0.0, 5.0),
    "QVEGE":           ("lin", 0.0, 2.0),
    "QSOIL":           ("div", -1.0, 1.0),    # negative = dew
    "QFLX_EVAP_TOT":   ("lin", 0.0, 6.0),
    "QIN":             ("div", -5.0, 5.0),    # per-layer, sign meaningful
    "QOUT":            ("div", -5.0, 5.0),

    # --- storage -------------------------------------------------------------
    "H2OSNO":          ("log", 1.0, 1000.0),  # SWE, mm
    "SNOWDP":          ("log", 0.01, 5.0),
    "H2OSFC":          ("log", 0.01, 100.0),
    "SOILLIQ":         ("lin", 0.0, 1500.0),  # column total, kg/m^2
    "SOILICE":         ("lin", 0.0, 500.0),
    "TOTSOILLIQ":      ("lin", 0.0, 1500.0),
    "TOTSOILICE":      ("lin", 0.0, 500.0),
    "TWS":             ("lin", 0.0, 3000.0),

    # --- depths, m -----------------------------------------------------------
    "ZWT":             ("lin", 0.0, 25.0),
    "ZWT_PERCH":       ("lin", 0.0, 5.0),
    "FROST_TABLE":     ("lin", 0.0, 10.0),
    "ALT":             ("lin", 0.0, 5.0),     # mostly NaN outside cold regions

    # --- temperatures, degC. asymmetric limits are honoured, pivot at 0 ------
    "TSA":             ("div", -25.0, 35.0),
    "TBOT":            ("div", -25.0, 35.0),
    "TG":              ("div", -25.0, 40.0),
    "TV":              ("div", -25.0, 40.0),
    "TSKIN":           ("div", -25.0, 45.0),
    "TSOI":            ("div", -20.0, 35.0),

    # --- energy fluxes, W/m^2. div entries are symmetric by construction -----
    "FSH":             ("div", -120.0, 120.0),
    "EFLX_LH_TOT":     ("lin", 0.0, 150.0),
    "EFLX_SOIL_GRND":  ("div", -50.0, 50.0),
    "FGR12":           ("div", -20.0, 20.0),
    "FIRA":            ("lin", 20.0, 110.0),  # check sign convention first
    "FIRE":            ("lin", 250.0, 450.0),
    "FSDS":            ("lin", 50.0, 350.0),

    # --- fractions and vegetation -------------------------------------------
    "FSNO":            ("lin", 0.0, 1.0),
    "FH2OSFC":         ("lin", 0.0, 0.5),
    "BTRANMN":         ("lin", 0.0, 1.0),
    "TLAI":            ("lin", 0.0, 6.0),
    "FPSN":            ("lin", 0.0, 15.0),
}

# How colour limits are chosen. The NORM TYPE (log/lin/div) always comes from
# VAR_NORM or the automatic rules -- that is set by the field's distribution and
# sign, not a matter of taste. This only controls the numbers.
#   "fixed"  use the vmin/vmax in VAR_NORM where given, else fall back to "pct".
#            The only mode that is stable across runs, so the only one usable for
#            comparing control against the sensitivity experiments.
#   "pct"    2-98th percentile of the data. Robust to a few pathological
#            gridcells, but clips ~4% of cells and moves when the data moves.
#   "minmax" actual data range. Nothing hidden, so outliers stay visible, but a
#            single bad cell can flatten the map -- much less so on a log scale.
LIMITS = "minmax"

# (scale, offset, new_unit) applied as value * scale + offset
CONVERT = {
    "mm/s": (86400.0, 0.0, "mm/day"),
    "K": (1.0, -273.15, "degC"),
}

CMAP_BY_UNIT = {
    "mm/day": "YlGnBu",
    "mm": "YlGnBu",
    "kg/m^2": "YlGnBu",
    "degC": "RdYlBu_r",
    "m": "viridis_r",
    "unitless": "Blues",
    "W/m^2": "inferno",
    "m^2/m^2": "YlGn",
    "umol m-2 s-1": "YlGn",
}
CMAP_DIVERGING = "RdBu_r"

# units where 0 is a meaningful pivot but the range is naturally lopsided, so
# limits stay asymmetric (TwoSlopeNorm) instead of being forced symmetric
PIVOT_UNITS = {"degC"}

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
SEASONS = {"DJF": [12, 1, 2], "MAM": [3, 4, 5],
           "JJA": [6, 7, 8], "SON": [9, 10, 11]}
DAYS_NOLEAP = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
               7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}

FILE_RE = re.compile(r"\.h0a\.(\d{4})-(\d{2})\.nc$")
SUFFIX_RE = re.compile(r"_(total|L\d+)$")


# ----------------------------------------------------------------------------
# metadata
# ----------------------------------------------------------------------------
def load_fields(csv_path):
    """Field -> {definition, unit} from the history-fields CSV."""
    df = pd.read_csv(csv_path)
    return {r.Field: {"definition": r.Definition, "unit": str(r.Units).strip()}
            for r in df.itertuples()}


def base_name(var):
    """SOILLIQ_total -> SOILLIQ, TSOI_L5 -> TSOI."""
    return SUFFIX_RE.sub("", var)


def var_meta(var, fields):
    info = fields.get(base_name(var), {"definition": var, "unit": "unknown"})
    unit = info["unit"]
    scale, offset, unit = CONVERT.get(unit, (1.0, 0.0, unit))
    return {"definition": info["definition"], "unit": unit,
            "scale": scale, "offset": offset}


# ----------------------------------------------------------------------------
# stage 1: climatology cache
# ----------------------------------------------------------------------------
def select_files(hist_dir):
    """h0a files inside [START_YM, END_YM], with their calendar month."""
    files, months = [], []
    lo, hi = START_YM, END_YM
    for path in sorted(glob.glob(os.path.join(hist_dir, "*.clm2.h0a.????-??.nc"))):
        m = FILE_RE.search(os.path.basename(path))
        if not m:
            continue
        ym = f"{m.group(1)}-{m.group(2)}"
        if lo <= ym <= hi:
            files.append(path)
            months.append(int(m.group(2)))
    return files, np.array(months, dtype="int8")


def collapse_levels(ds, keep):
    """Subset variables and reduce any lev* dimension, so dask stays small."""
    out = {}
    for v in keep:
        da = ds[v]
        ldim = next((d for d in da.dims if d.startswith("lev")), None)
        if ldim is None:
            out[v] = da
            continue
        spec = LEVELS.get(v, LEVELS_DEFAULT)
        if spec == "sum":
            out[f"{v}_total"] = da.sum(ldim, min_count=1, keep_attrs=True)
        else:
            for k in spec:
                if k < da.sizes[ldim]:
                    out[f"{v}_L{k + 1}"] = da.isel({ldim: k}, drop=True)
    coords = {c: ds[c] for c in ("lat", "lon") if c in ds.coords}
    return xr.Dataset(out, coords=coords)


def build_cache(hist_dir, fields, cache_nc, want=None):
    files, months = select_files(hist_dir)
    if not files:
        raise SystemExit(f"no h0a files in {hist_dir} for {START_YM}..{END_YM}")
    print(f"stage 1: {len(files)} monthly files, {files[0][-10:-3]} .. {files[-1][-10:-3]}")

    requested = set(want) if want else set(fields)
    probe = xr.open_dataset(files[0], decode_times=False)
    present = [v for v in probe.data_vars if v in requested]
    missing = sorted(requested - set(present))
    probe.close()
    print(f"        {len(present)} fields found; {len(missing)} absent: {', '.join(missing) or 'none'}")

    ds = xr.open_mfdataset(
        files, combine="nested", concat_dim="time", decode_times=False,
        parallel=True, chunks={"time": 12},
        data_vars="minimal", coords="minimal", compat="override",
        preprocess=lambda d: collapse_levels(d, [v for v in present if v in d.data_vars]),
    )
    ds = ds.assign_coords(month=("time", months))

    # noleap calendar: every instance of a given month has equal length,
    # so the unweighted across-year mean is exact.
    clim = ds.groupby("month").mean("time", keep_attrs=True)
    clim = clim.transpose("month", "lat", "lon")

    for v in clim.data_vars:
        m = var_meta(v, fields)
        clim[v].attrs.update(long_name=m["definition"], units=m["unit"])
    clim.attrs.update(
        title="CTSM monthly climatology",
        window=f"{START_YM}..{END_YM}",
        n_months=len(files),
    )

    os.makedirs(os.path.dirname(cache_nc) or ".", exist_ok=True)
    enc = {v: {"zlib": True, "complevel": 4, "dtype": "float32"} for v in clim.data_vars}
    print("        computing and writing cache ...")
    clim.compute().to_netcdf(cache_nc, encoding=enc)
    ds.close()
    print(f"        wrote {cache_nc} ({os.path.getsize(cache_nc) / 1e6:.0f} MB)")


# ----------------------------------------------------------------------------
# plotting helpers
# ----------------------------------------------------------------------------
def scaled(clim, var, fields):
    m = var_meta(var, fields)
    return clim[var] * m["scale"] + m["offset"], m


def color_setup(data, var, unit):
    """Shared norm + cmap + a stats dict describing what the scale hides.

    Returning one norm for all panels is the point: per-panel autoscaling would
    make the months non-comparable. cmap None means 'fall back to the unit'.

    Precedence matters. An explicit VAR_NORM entry wins, then LOG_VARS, and only
    then the automatic spans-zero test. Checking spans-zero first is wrong: a
    handful of negative lake/glacier gridcells in an otherwise positive water
    flux would drag the whole field onto a symmetric linear scale and wash out
    three decades of real structure.
    """
    finite = np.asarray(data)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return None, None, None

    base = base_name(var)
    kind, vmin, vmax = VAR_NORM.get(base, (None, None, None))
    # the kind is always honoured; the numbers only in "fixed" mode
    if LIMITS != "fixed":
        vmin = vmax = None
    fixed = vmin is not None or vmax is not None
    if kind is None:
        kind = "log" if base in LOG_VARS else "auto"

    # for a log scale only positive cells set the limits; non-positive ones are
    # masked by LogNorm and counted so the drop-out is never silent
    pool = finite[finite > 0] if kind == "log" else finite
    if pool.size == 0:
        return None, None, None

    if LIMITS == "minmax":
        lo, hi = float(pool.min()), float(pool.max())
    else:
        lo, hi = (float(x) for x in np.percentile(pool, [2, 98]))
    if hi <= lo:
        lo, hi = float(pool.min()), float(pool.max())
        if hi <= lo:
            hi = lo + 1.0
    lo = lo if vmin is None else vmin
    hi = hi if vmax is None else vmax

    if kind == "log":
        norm, cmap = mpl.colors.LogNorm(max(lo, hi / 1e4, 1e-6), hi), None
    elif kind == "div" or (kind == "auto" and lo < 0 < hi):
        if unit in PIVOT_UNITS:
            norm, cmap = mpl.colors.TwoSlopeNorm(vcenter=0.0, vmin=lo, vmax=hi), None
        else:
            a = max(abs(lo), abs(hi))
            norm, cmap = mpl.colors.Normalize(-a, a), CMAP_DIVERGING
    else:
        norm, cmap = mpl.colors.Normalize(lo, hi), None

    n = finite.size
    scale = {"LogNorm": "log", "TwoSlopeNorm": "diverging at 0",
             "Normalize": "diverging" if cmap == CMAP_DIVERGING else "linear",
             }[type(norm).__name__]
    stats = {
        "kind": scale, "fixed": fixed,
        "vmin": norm.vmin, "vmax": norm.vmax,
        "dmin": float(finite.min()), "dmax": float(finite.max()),
        "pct_under": 100.0 * np.count_nonzero(pool < norm.vmin) / n,
        "pct_over": 100.0 * np.count_nonzero(pool > norm.vmax) / n,
        "pct_masked": 100.0 * (n - pool.size) / n,
    }
    return norm, cmap, stats


def scale_caption(stats, unit):
    """One line stating the color limits, the true range, and what is hidden."""
    g = lambda x: f"{x:.3g}"
    how = ("fixed" if stats["fixed"]
           else "actual range" if LIMITS == "minmax" else "2-98th pct")
    parts = [
        f"color scale: {stats['kind']}, {g(stats['vmin'])} to {g(stats['vmax'])} ({how})",
        f"actual data range: {g(stats['dmin'])} to {g(stats['dmax'])} {unit}",
    ]
    sat = []
    if stats["pct_under"] >= 0.01:
        sat.append(f"{stats['pct_under']:.1f}% below")
    if stats["pct_over"] >= 0.01:
        sat.append(f"{stats['pct_over']:.1f}% above")
    if sat:
        parts.append("saturated: " + ", ".join(sat))
    if stats["pct_masked"] >= 0.01:
        parts.append(f"{stats['pct_masked']:.2f}% <= 0, masked")
    return "     ".join(parts)


def panel_figure(da, var, meta, labels, ncol, nrow, out_png):
    norm, cmap, stats = color_setup(da.values, var, meta["unit"])
    if norm is None:
        print(f"        skip {var}: no plottable values")
        return
    cmap = cmap or CMAP_BY_UNIT.get(meta["unit"], "viridis")

    fig, axes = plt.subplots(nrow, ncol, figsize=(4.3 * ncol, 2.7 * nrow),
                             subplot_kw={"projection": PROJ},
                             constrained_layout=True)
    axes = np.atleast_1d(axes).ravel()
    mesh = None
    for i, (ax, label) in enumerate(zip(axes, labels)):
        basemap(ax)
        mesh = ax.pcolormesh(da["lon"], da["lat"], da.isel({da.dims[0]: i}).values,
                             cmap=cmap, norm=norm, transform=PROJ,
                             shading="auto", zorder=1)
        ax.set_title(label, fontsize=11)
    for ax in axes[len(labels):]:
        ax.set_visible(False)

    cb = fig.colorbar(mesh, ax=axes.tolist(), orientation="horizontal",
                      fraction=0.045, pad=0.02, extend="both")
    cb.set_label(f"{var}  [{meta['unit']}]", fontsize=11)
    fig.suptitle(f"{var} — {meta['definition']}\n{START_YM} to {END_YM} climatology",
                 fontsize=13)
    # the limits are percentile-clipped, so state what the colorbar is hiding
    fig.text(0.5, -0.005, scale_caption(stats, meta["unit"]), ha="center",
             va="top", fontsize=8.5, color="0.35")
    fig.savefig(out_png, dpi=DPI, bbox_inches="tight")
    plt.close(fig)


def to_seasonal(da):
    w = xr.DataArray([DAYS_NOLEAP[m] for m in da["month"].values],
                     coords={"month": da["month"]}, dims="month")
    out = [da.sel(month=mm).weighted(w.sel(month=mm)).mean("month")
           for mm in SEASONS.values()]
    return xr.concat(out, dim="season").assign_coords(season=list(SEASONS))


# ----------------------------------------------------------------------------
# stage 2
# ----------------------------------------------------------------------------
def make_maps(clim, fields, out_dir, kind, want=None):
    sub = os.path.join(out_dir, kind)
    os.makedirs(sub, exist_ok=True)
    variables = [v for v in clim.data_vars if not want or base_name(v) in want]
    print(f"stage 2 ({kind}): {len(variables)} figures -> {sub}")

    for var in variables:
        da, meta = scaled(clim, var, fields)
        if kind == "seasonal":
            da = to_seasonal(da)
            labels, ncol, nrow = list(SEASONS), 4, 1
        else:
            labels, ncol, nrow = MONTHS, 4, 3
        panel_figure(da, var, meta, labels, ncol, nrow,
                     os.path.join(sub, f"{var}.png"))
        print(f"        {var}")


def area_weights(hist_dir, clim):
    """landfrac * area weights; drops the spurious time dim if present."""
    f = sorted(glob.glob(os.path.join(hist_dir, "*.clm2.h0a.????-??.nc")))[0]
    with xr.open_dataset(f, decode_times=False) as ds:
        w = None
        for name in ("area", "landfrac"):
            if name in ds:
                v = ds[name]
                if "time" in v.dims:
                    v = v.isel(time=0, drop=True)
                w = v if w is None else w * v
    if w is None:
        w = xr.ones_like(clim["lat"] * clim["lon"])
    return w.fillna(0.0)


def make_summary(clim, fields, hist_dir, out_dir):
    w = area_weights(hist_dir, clim)
    variables = sorted(clim.data_vars)
    ncol = 5
    nrow = int(np.ceil(len(variables) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(3.1 * ncol, 2.2 * nrow),
                             constrained_layout=True)
    axes = np.atleast_1d(axes).ravel()

    for ax, var in zip(axes, variables):
        da, meta = scaled(clim, var, fields)
        ts = da.weighted(w.broadcast_like(da.isel(month=0)).fillna(0)).mean(("lat", "lon"))
        ax.plot(range(1, 13), ts.values, "o-", ms=3, lw=1.4, color="#1f6fb4")
        ax.set_title(f"{var}\n[{meta['unit']}]", fontsize=8)
        ax.set_xticks([1, 4, 7, 10])
        ax.set_xticklabels(["J", "A", "J", "O"], fontsize=7)
        ax.tick_params(labelsize=7)
        ax.grid(alpha=0.3, lw=0.5)
    for ax in axes[len(variables):]:
        ax.set_visible(False)

    fig.suptitle(f"CONUS area-weighted mean seasonal cycle, {START_YM} to {END_YM}",
                 fontsize=14)
    out = os.path.join(out_dir, "seasonal_cycle_summary.png")
    fig.savefig(out, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"stage 2 (summary): {out}")


# ----------------------------------------------------------------------------
def main():
    global LIMITS
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--rebuild", action="store_true", help="recompute the climatology cache")
    p.add_argument("--monthly", action="store_true")
    p.add_argument("--seasonal", action="store_true")
    p.add_argument("--summary", action="store_true")
    p.add_argument("--vars", nargs="+", help="limit to these field names")
    p.add_argument("--limits", choices=["fixed", "pct", "minmax"], default=LIMITS,
                   help="colour limits: 'fixed' uses the VAR_NORM numbers (default, "
                        "stable across runs), 'pct' the robust 2-98th percentile, "
                        "'minmax' the actual data range. The log/lin/div scale type "
                        "is unaffected.")
    p.add_argument("--hist-dir", default=DEFAULT_PATHS["ctsm_hist_dir"],
                   help="h0a folder (default: %(default)s)")
    p.add_argument("--outdir", default=DEFAULT_PATHS["out_dir"],
                   help="figure folder (default: %(default)s)")
    p.add_argument("--cache", default=DEFAULT_PATHS["cache_nc"],
                   help="climatology cache file (default: %(default)s)")
    args = p.parse_args()

    LIMITS = args.limits

    if not (args.monthly or args.seasonal or args.summary):
        args.monthly = args.seasonal = args.summary = True

    fields = load_fields(DEFAULT_PATHS["fields_csv"])
    cache = args.cache
    out_dir = args.outdir
    os.makedirs(out_dir, exist_ok=True)

    if args.rebuild or not os.path.exists(cache):
        build_cache(args.hist_dir, fields, cache, args.vars)
    else:
        print(f"stage 1: reusing {cache} (--rebuild to recompute)")

    clim = xr.open_dataset(cache)
    want = set(args.vars) if args.vars else None
    if args.monthly:
        make_maps(clim, fields, out_dir, "monthly", want)
    if args.seasonal:
        make_maps(clim, fields, out_dir, "seasonal", want)
    if args.summary:
        make_summary(clim, fields, args.hist_dir, out_dir)
    clim.close()


if __name__ == "__main__":
    main()
