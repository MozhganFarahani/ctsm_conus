#!/usr/bin/env python
"""Spinup drift check over a full run: domain means and three sites.

From the notebook check_spinup_v2.ipynb (sections 1-3), same method:
  1. Domain-mean (unweighted) water-year means of 8 fields from monthly h0a,
     full 12-month water years only; drift = mean of the last 2 WY vs the 2 WY before.
  2. Daily h1a series at three sites (nearest grid cell), annual means per site,
     and the same last-2 vs previous-2 year drift.
Figures go to --outdir; drift summaries print to stdout.

Inputs : <archive>/<case>/lnd/hist/<case>.clm2.h0a.*.nc and .h1a.*.nc (paths.lnd_hist)
Outputs: <outdir>/domain_mean_wy.png, <outdir>/site_daily.png

Usage
-----
    module load conda && conda activate npl-2026a
    python check_spinup_drift.py --case hillslope_on
    python check_spinup_drift.py --case hillslope_on --years 1981 1984   # short test
A full run reads ~24 GB per daily file: submit run_spinup_drift.pbs on Casper.

Note on the sites (finding kept from the notebook, not re-run here):
the S. Florida site (25.0625N, 283.9375E) sits on the southern edge row of the
NLDAS2 grid, on an isolated coastal fragment where the DATM Precip stream is
near zero (~1e-9 mm/s). Its TOTSOILLIQ decline/recovery is therefore a forcing
artifact, not a spinup problem. The notebook re-checked equilibration at an
interior wetland, Atchafalaya Basin LA (30.5N, 268.5E), after confirming its
forcing is real precipitation. The site list is kept as in the notebook so the
numbers match it.
"""

import argparse
import glob
import os
import re
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "config"))
import paths  # analysis/config/paths.py
sys.path.insert(0, os.path.join(HERE, ".."))
from lib import io as lio  # analysis/lib/io.py

DOMAIN_FIELDS = [
    "TOTSOILLIQ", "TOTSOILICE", "ZWT", "H2OSNO",
    "TWS", "FSH", "EFLX_LH_TOT", "TSOI",
]
SITE_FIELDS = ["TOTSOILLIQ", "TOTSOILICE", "ZWT", "TSOI", "RAIN", "SNOW"]

# Sites derived from the P/storage ratio calc (lowest & highest in our own
# domain), plus Yuma as a general arid-Southwest reference.
KNOWN_SITES = {
    (25.0625, 283.9375): "S. Florida wetland (lowest P/storage ratio)",
    (32.7, 245.4): "Yuma, AZ area (arid Southwest reference)",
    (47.8125, 236.0625): "WA Pacific NW (highest P/storage ratio)",
}

# TSOI has a levgrnd dimension -- use a deep layer (index 15) for the site plots,
# consistent with earlier analysis.
DEEP_LAYER_IDX = 15


def file_water_year(path):
    """Water year of a history file from its name: h0a .YYYY-MM.nc (Oct-Dec ->
    next WY), h1a .YYYY-10-02-00000.nc (one file per WY, starting in October)."""
    y, m = map(int, re.search(r"\.(\d{4})-(\d{2})[.-]", os.path.basename(path)).groups())
    return y + 1 if m >= 10 else y


def select_years(files, years):
    if years is None:
        return files
    return [f for f in files if years[0] <= file_water_year(f) <= years[1]]


def water_year_labels(time_da):
    months = time_da.dt.month.values
    years = time_da.dt.year.values
    return np.where(months >= 10, years + 1, years)


def drift(series, dim):
    """(prior, recent, % change): mean of the last 2 steps vs the 2 before."""
    recent = series.isel({dim: slice(-2, None)}).mean().values
    prior = series.isel({dim: slice(-4, -2)}).mean().values
    pct_change = 100 * (recent - prior) / prior if prior != 0 else np.nan
    return prior, recent, pct_change


def get_plot_series(ds_site, field):
    da = ds_site[field]
    if "levgrnd" in da.dims:
        da = da.isel(levgrnd=DEEP_LAYER_IDX)
    time_vals = np.array(
        [t.strftime("%Y-%m-%d") for t in ds_site["time"].values], dtype="datetime64[D]"
    )
    return time_vals, da.values


def domain_check(hist_dir, case, years, outdir):
    files_monthly = select_years(sorted(glob.glob(f"{hist_dir}/{case}.clm2.h0a.*.nc")), years)
    print(f"Found {len(files_monthly)} monthly files")
    print(files_monthly[0], "...", files_monthly[-1])
    ds_monthly = lio.open_land_hist(files_monthly, DOMAIN_FIELDS, parallel=True)

    # Assign water-year coordinate, keep only full (12-month) water years
    wy = water_year_labels(ds_monthly["time"])
    ds_monthly = ds_monthly.assign_coords(water_year=("time", wy))
    months_per_wy = ds_monthly["time"].groupby("water_year").count()
    full_water_years = months_per_wy.where(months_per_wy == 12, drop=True)["water_year"].values
    print("Full (12-month) water years:", full_water_years)

    domain_mean_wy = {}
    for f in DOMAIN_FIELDS:
        if f not in ds_monthly:
            print(f"WARNING: {f} not found, skipping.")
            continue
        spatial_dims = [d for d in ds_monthly[f].dims if d not in ("time",)]
        da = ds_monthly[f].mean(dim=spatial_dims, skipna=True)
        grouped = da.groupby("water_year").mean().load()
        grouped = grouped.where(grouped["water_year"].isin(full_water_years), drop=True)
        domain_mean_wy[f] = grouped

    n = len(domain_mean_wy)
    fig, axes = plt.subplots(n, 1, figsize=(9, 2.5 * n), sharex=True)
    axes = np.atleast_1d(axes)
    for ax, (fname, da) in zip(axes, domain_mean_wy.items()):
        ax.plot(da["water_year"].values, da.values, marker="o")
        units = ds_monthly[fname].attrs.get("units", "")
        ax.set_ylabel(f"{fname}\n({units})")
        ax.grid(alpha=0.3)
    axes[-1].set_xlabel("Water Year")
    fig.suptitle(f"{case}: domain-mean water-year values", y=1.02)
    fig.tight_layout()
    fig.savefig(f"{outdir}/domain_mean_wy.png", dpi=120, bbox_inches="tight")
    plt.close(fig)

    print("--- Domain-mean drift summary (last 2 WY mean vs previous 2 WY mean) ---")
    for fname, da in domain_mean_wy.items():
        if len(da) >= 4:
            prior, recent, pct = drift(da, "water_year")
            print(f"{fname}: prior={prior:.4f}, recent={recent:.4f}, change={pct:.2f}%")
        else:
            print(f"{fname}: not enough water years to compare")


def site_check(hist_dir, case, years, outdir):
    files_daily = select_years(sorted(glob.glob(f"{hist_dir}/{case}.clm2.h1a.*.nc")), years)
    print(f"Found {len(files_daily)} daily files")
    ds_daily = lio.open_land_hist(files_daily, SITE_FIELDS, parallel=True)

    lats = [lat for (lat, lon) in KNOWN_SITES.keys()]
    lons = [lon for (lat, lon) in KNOWN_SITES.keys()]
    names = list(KNOWN_SITES.values())

    # One combined selection across all sites, a single read
    points = ds_daily.sel(
        lat=xr.DataArray(lats, dims="site"),
        lon=xr.DataArray(lons, dims="site"),
        method="nearest",
    ).load()

    site_data = {}
    for i, name in enumerate(names):
        site_point = points.isel(site=i)
        site_data[name] = site_point
        print(f"{name}: requested ({lats[i]}, {lons[i]}), nearest grid cell "
              f"({float(site_point['lat']):.3f}, {float(site_point['lon']):.3f})")

    fig, axes = plt.subplots(len(SITE_FIELDS), 1, figsize=(11, 3 * len(SITE_FIELDS)), sharex=True)
    for ax, field in zip(axes, SITE_FIELDS):
        for name, ds_site in site_data.items():
            if field in ds_site:
                x, y = get_plot_series(ds_site, field)
                ax.plot(x, y, label=name, linewidth=0.8, alpha=0.85)
        ax.set_ylabel(field)
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
    axes[-1].set_xlabel("Date")
    fig.suptitle(f"{case}: site-level daily series", y=1.01)
    fig.tight_layout()
    fig.savefig(f"{outdir}/site_daily.png", dpi=120, bbox_inches="tight")
    plt.close(fig)

    # Annual means per site -- easier to read drift than noisy daily data
    annual_by_site = {}
    for field in SITE_FIELDS:
        print(f"\n--- {field} annual means ---")
        annual_by_site[field] = {}
        for name, ds_site in site_data.items():
            if field not in ds_site:
                continue
            da = ds_site[field]
            if "levgrnd" in da.dims:
                da = da.isel(levgrnd=DEEP_LAYER_IDX)
            annual = da.resample(time="YS").mean()
            annual_by_site[field][name] = annual
            print(f"{name}:")
            for t, v in zip(annual["time"].dt.year.values, annual.values):
                print(f"  {t}: {v:.3f}")

    print("--- Site-level drift summary (last 2yr mean vs previous 2yr mean) ---")
    for field in SITE_FIELDS:
        print(f"\n{field}:")
        for name, annual in annual_by_site[field].items():
            if len(annual) >= 4:
                prior, recent, pct = drift(annual, "time")
                print(f"  {name}: prior={prior:.4f}, recent={recent:.4f}, change={pct:.2f}%")
            else:
                print(f"  {name}: not enough years to compare")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", default="hillslope_on",
                    help="case name under the archive (default: hillslope_on)")
    ap.add_argument("--years", type=int, nargs=2, metavar=("WY1", "WY2"),
                    help="only water years WY1..WY2 (default: all files)")
    ap.add_argument("--outdir", help="figure folder (default: <output root>/spinup/<case>)")
    ap.add_argument("--skip-sites", action="store_true",
                    help="domain-mean part only (the daily site part is the heavy one)")
    args = ap.parse_args()

    outdir = args.outdir or f"{paths.OUTPUT_ROOT}/spinup/{args.case}"
    os.makedirs(outdir, exist_ok=True)
    hist_dir = paths.lnd_hist(args.case)

    domain_check(hist_dir, args.case, args.years, outdir)
    if not args.skip_sites:
        site_check(hist_dir, args.case, args.years, outdir)
    print(f"\nFigures in {outdir}")


if __name__ == "__main__":
    main()
