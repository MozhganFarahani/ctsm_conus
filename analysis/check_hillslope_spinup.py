#!/usr/bin/env python
"""
Check hillslope spinup equilibration
=======================================================================
SIF-T FY26 (Farahani)

A spinup "working" means two different things -- this checks the one that
actually matters scientifically: whether key state variables (soil
moisture, water table depth, snow storage, total water storage) have
stopped drifting and settled into a repeating annual cycle, not just that
the job ran to completion without crashing.

Plots domain-mean ANNUAL values of TWS, peak SWE, water table depth, and
total soil moisture across the full spinup so far. A converged spinup
looks flat (oscillating around a stable mean) in the final several years;
a spinup that still needs more time shows a visible trend even at the end.

Usage
-----
    module load conda && conda activate npl-2026a
    python check_hillslope_spinup.py \
  --run-dir /glade/derecho/scratch/mozhgana/archive/hillslope_on/lnd/hist \
  --outdir ./hillslope_spinup_check
  

Caveat: this uses the standard gridcell-averaged h0 history output, which
is what you configured (hist_fincl1/2). CLM's default history output is
already area-weighted back to the gridcell level -- it does NOT preserve
per-hillslope-column values distinctly unless a separate column/patch-level
("1D vector") history output mode is requested. So this check confirms the
GRIDCELL-AVERAGE state has equilibrated, but can't directly tell you
whether individual hillslope columns have differentiated from each other
(the thing the use_init_interp warning was about). If you need that
specifically, ask Sean whether a column-level output stream is needed.
"""

import argparse
import glob
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning, module="xarray")

STATE_VARS = ["TWS", "H2OSNO", "ZWT", "TOTSOILLIQ", "TOTSOILICE"]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--outdir", default="./hillslope_spinup_check")
    ap.add_argument("--case-prefix", default="hillslope_on")
    args = ap.parse_args()

    import os
    os.makedirs(args.outdir, exist_ok=True)
    import xarray as xr

    pattern = os.path.join(args.run_dir, f"{args.case_prefix}.clm2.h0a.*.nc")
    files = sorted(glob.glob(pattern))
    if not files:
        sys.exit(f"No h0 files matched: {pattern}")
    print(f"Found {len(files)} monthly h0 files, "
          f"{files[0].split('.')[-2]} -> {files[-1].split('.')[-2]}")

    ds = xr.open_mfdataset(
        files, combine="nested", concat_dim="time", decode_times=True,
        engine="netcdf4", data_vars="all",
        preprocess=lambda d: d[[v for v in STATE_VARS + ["landfrac"]
                                 if v in d.variables]],
    )

    available = [v for v in STATE_VARS if v in ds.data_vars]
    missing = [v for v in STATE_VARS if v not in ds.data_vars]
    if missing:
        print(f"NOTE: not in output, skipping: {missing}")
    print(f"Checking equilibration for: {available}")

    weight = ds["landfrac"].isel(time=0) if "landfrac" in ds else None

    def domain_mean(da):
        if weight is not None:
            return (da * weight).sum(dim=["lat", "lon"]) / weight.sum()
        return da.mean(dim=["lat", "lon"])

    annual = {}
    for v in available:
        if v == "H2OSNO":
            # peak (not mean) annual SWE is the physically meaningful metric
            series = domain_mean(ds[v]).groupby(ds["time"].dt.year).max()
        else:
            series = domain_mean(ds[v]).groupby(ds["time"].dt.year).mean()
        annual[v] = series.compute()

    print("\n--- Trend check: recent window, first-half vs second-half mean ---")
    print("(tests whether there's still a systematic drift, not just noise --")
    print(" a persistent trend accumulates across the window even when each")
    print(" single year's step looks small)\n")
    for v, series in annual.items():
        vals = series.values
        years = series["year"].values
        window = min(10, len(vals))
        if window < 6:
            print(f"{v}: only {len(vals)} year(s) so far -- too early to assess")
            continue
        recent = vals[-window:]
        half = window // 2
        first_half_mean = np.nanmean(recent[:half])
        second_half_mean = np.nanmean(recent[half:])
        drift = second_half_mean - first_half_mean
        noise = np.nanstd(recent)
        ratio = abs(drift) / (noise + 1e-9)
        flag = "OK -- looks converged" if ratio < 1.0 else \
               f"WATCH -- still drifting (systematic change is {ratio:.1f}x the noise level)"
        print(f"{v}: last {window}yr drift={drift:+.3f}, noise(std)={noise:.3f} -> {flag}")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(len(annual), 1, figsize=(9, 2.5 * len(annual)), sharex=True)
        if len(annual) == 1:
            axes = [axes]
        for ax, (v, series) in zip(axes, annual.items()):
            ax.plot(series["year"].values, series.values, marker="o", ms=3)
            ax.set_ylabel(v)
            ax.grid(alpha=0.3)
        axes[-1].set_xlabel("Year")
        fig.suptitle("Hillslope spinup: annual-mean state variables (domain mean)")
        fig.tight_layout()
        out_path = os.path.join(args.outdir, "hillslope_spinup_drift.png")
        fig.savefig(out_path, dpi=150)
        print(f"\nSaved -> {out_path}")
    except Exception as e:
        print(f"Plot failed (non-fatal): {e}")

    print("\nWhat to look for in the plot: each panel should flatten out")
    print("(oscillate around a stable level) toward the right edge. If a")
    print("variable is still visibly trending up or down at the most recent")
    print("years, the spinup likely needs to run longer before you branch")
    print("into the eval period.")


if __name__ == "__main__":
    main()
