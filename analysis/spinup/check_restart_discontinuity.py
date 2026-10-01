#!/usr/bin/env python
"""
Check for a restart-boundary discontinuity in TOTSOILICE
=======================================================================
SIF-T FY26 (Farahani)

The annual-mean hillslope spinup check showed TOTSOILICE dropping to a
visibly lower band right around 1997-1998 -- which lines up suspiciously
well with one of this run's own restart-segment boundaries (1998-10-01),
given hillslope is the only config with multiple restart transitions AND
documented restart-handling bugs (DRV_RESTART_POINTER, missing checkpoints)
in this project. Control/irrigation/land-cover show no similar artifact,
and none of them had anywhere near this many restart transitions.

This pulls MONTHLY (not annual-mean) TOTSOILICE right around the boundary
to distinguish:
  - a sharp, single-timestep discontinuity exactly at the restart date
    -> restart artifact, worth flagging/investigating further before
       trusting this spinup
  - a gradual multi-month decline spanning the boundary
    -> more likely a genuine seasonal/interannual signal, not a bug

Usage
-----

    module load conda && conda activate npl-2026a
    python check_restart_discontinuity.py \
  --run-dir /glade/derecho/scratch/mozhgana/archive/hillslope_on/lnd/hist \
  --restart-date 1998-10-01 \
  --outdir ./hillslope_spinup_check

"""

import argparse
import glob
import os
import sys
import warnings

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from lib import io as lio  # analysis/lib/io.py

warnings.filterwarnings("ignore", category=FutureWarning, module="xarray")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--restart-date", required=True,
                     help="Suspected boundary, e.g. 1998-10-01")
    ap.add_argument("--var", default="TOTSOILICE")
    ap.add_argument("--window-months", type=int, default=8,
                     help="Months of h1 (daily-tape monthly climatology) or "
                          "h0 (monthly) data to pull on each side of the boundary")
    ap.add_argument("--outdir", default="./hillslope_spinup_check")
    ap.add_argument("--case-prefix", default="hillslope_on")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    restart = pd.Period(args.restart_date, freq="M")
    start = restart - args.window_months
    end = restart + args.window_months

    pattern = os.path.join(args.run_dir, f"{args.case_prefix}.clm2.h0a.*.nc")
    files = sorted(glob.glob(pattern))
    if not files:
        sys.exit(f"No h0 files matched: {pattern}")

    # only open files in the window -- cheap, no need for the full record
    wanted_files = []
    for f in files:
        try:
            ym = f.split(".")[-2]  # e.g. "1997-08"
            p = pd.Period(ym, freq="M")
            if start <= p <= end:
                wanted_files.append(f)
        except Exception:
            continue
    if not wanted_files:
        sys.exit("No files found in the requested window -- check --restart-date "
                  "and file naming.")
    print(f"Using {len(wanted_files)} monthly files from "
          f"{wanted_files[0].split('.')[-2]} to {wanted_files[-1].split('.')[-2]}")

    ds = lio.open_land_hist(wanted_files, [args.var, "landfrac"])
    if args.var not in ds.data_vars:
        sys.exit(f"{args.var} not in these files. Available: {list(ds.data_vars)}")

    series = lio.domain_mean(ds[args.var], ds).compute()
    months = lio.monthly_index(series["time"].values).astype(str).tolist()

    df = pd.Series(series.values, index=months, name=args.var)
    print(f"\n{args.var}, monthly, around {args.restart_date}:")
    print(df.to_string())

    diffs = df.diff()
    boundary_str = f"{restart.year}-{restart.month:02d}"
    if boundary_str not in diffs.index:
        sys.exit(f"Boundary month {boundary_str} not in the pulled window -- "
                  f"widen --window-months.")

    boundary_diff = diffs[boundary_str]
    other_diffs = diffs.drop(index=boundary_str).dropna()
    baseline = other_diffs.abs().median()
    ratio = abs(boundary_diff) / (baseline + 1e-9)

    print(f"\nChange at the restart boundary ({boundary_str}): {boundary_diff:+.3f}")
    print(f"Typical month-to-month change elsewhere in this window "
          f"(median abs diff): {baseline:.3f}")
    print(f"Boundary change is {ratio:.1f}x the typical change elsewhere.")
    # FIX: "is the boundary the single largest diff" is NOT a reliable test --
    # with steady noise, any month can end up nominally largest by chance
    # (confirmed by testing against a smooth, no-jump synthetic series, which
    # got a false positive under that simpler rule). What actually matters is
    # whether the boundary's change is an OUTLIER relative to typical
    # variability elsewhere, not merely the nominal maximum.
    if ratio > 4:
        print(f"-> LIKELY a restart discontinuity: the boundary-month change "
              f"is a clear outlier ({ratio:.1f}x typical), not consistent with "
              f"ordinary month-to-month variability.")
    elif ratio > 2:
        print(f"-> AMBIGUOUS: somewhat elevated ({ratio:.1f}x typical) but not "
              f"a clear-cut outlier. Look at the plot before concluding either way.")
    else:
        print(f"-> Looks consistent with ordinary variability elsewhere in the "
              f"window -- no strong evidence of a restart-specific discontinuity.")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(11, 4))
        ax.plot(range(len(df)), df.values, marker="o", ms=4)
        boundary_idx = df.index.get_loc(boundary_str) if boundary_str in df.index else None
        if boundary_idx is not None:
            ax.axvline(boundary_idx, color="r", ls="--", lw=1, label=f"restart boundary ({boundary_str})")
            ax.legend()
        ax.set_xticks(range(0, len(df), max(1, len(df) // 12)))
        ax.set_xticklabels([df.index[i] for i in range(0, len(df), max(1, len(df) // 12))],
                            rotation=45, ha="right")
        ax.set_ylabel(args.var)
        ax.set_title(f"{args.var} around suspected restart boundary")
        ax.grid(alpha=0.3)
        fig.tight_layout()
        out_path = os.path.join(args.outdir, f"{args.var}_restart_boundary_check.png")
        fig.savefig(out_path, dpi=150)
        print(f"\nSaved -> {out_path}")
    except Exception as e:
        print(f"Plot failed (non-fatal): {e}")


if __name__ == "__main__":
    main()
