#!/usr/bin/env python
"""
CTSM streamflow evaluation vs. observed gauges -- lean version
=======================================================================
SIF-T FY26 (Farahani)

One bulk, vectorized read of all needed reaches (mizuRoute) and gauges
(obs daily file), then NSE/KGE/PBIAS computed for every gauge at once with
numpy -- no per-gauge Python loop, no per-gauge file I/O. This is what
actually makes it fast; multiprocessing over individual gauges was tried
and benchmarked slower (fixed per-worker file-open cost dominates when the
per-gauge work is this cheap).

--parallel controls dask's multi-threaded reading of the mizuRoute file set
(xr.open_mfdataset(parallel=...)) -- meaningful when you have hundreds of
files, since it reads them concurrently rather than one at a time.

Inputs : mizuRoute RoutedRunoff of one config (<archive>/<config>/rof/hist),
         observed daily flow (paths.OBS_DAILY, resampled to monthly),
         gauge crosswalk (paths.CROSSWALK)
Outputs: <outdir>/<config>_streamflow_eval.csv, one row per gauge
         (default outdir: <output root>/streamflow); a summary prints to stdout

Usage
-----
    module load conda && conda activate npl-2026a
    python ctsm_streamflow_eval.py --config irrigation_on --parallel --limit 100
"""

import argparse
import os
import sys
import warnings

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "config"))
import paths  # analysis/config/paths.py
sys.path.insert(0, os.path.join(HERE, ".."))
from lib import io as lio       # analysis/lib/io.py
from lib import metrics         # analysis/lib/metrics.py

warnings.filterwarnings("ignore", category=FutureWarning, module="xarray")

DEFAULT_CROSSWALK = paths.CROSSWALK
DEFAULT_OBS_DAILY = paths.OBS_DAILY


def vectorized_metrics(df_gauges, modeled_df, observed_df):
    """NSE/KGE/PBIAS for every gauge at once (lib/metrics.py).
    Aligns modeled/observed to a common monthly index and gauge order."""
    reach_ids = df_gauges["merit_reach_id"].astype(int).to_numpy()
    gage_ids = pd.to_numeric(df_gauges["GAGE_ID"], errors="coerce")
    keep = (~gage_ids.isna()
            & pd.Series(reach_ids).isin(modeled_df.columns).to_numpy()
            & gage_ids.isin(observed_df.columns).to_numpy())
    df_gauges = df_gauges[keep].reset_index(drop=True)
    reach_ids = reach_ids[keep.to_numpy()]
    gage_ids = gage_ids[keep].astype(int).to_numpy()
    if len(df_gauges) == 0:
        return df_gauges.assign(NSE=[], KGE=[], PBIAS=[], n_months=[])

    common_idx = modeled_df.index.intersection(observed_df.index)
    m = metrics.nse_kge_pbias(observed_df.loc[common_idx, gage_ids],
                              modeled_df.loc[common_idx, reach_ids])

    out = df_gauges.copy()
    out["n_months"], out["NSE"], out["KGE"], out["PBIAS"], out["corr"] = \
        m["n"], m["nse"], m["kge"], m["pbias"], m["corr"]
    out.loc[out["n_months"] < metrics.MIN_MONTHS, ["NSE", "KGE", "PBIAS", "corr"]] = float("nan")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--archive-root", default=paths.ARCHIVE,
                     help="Directory containing {config}/rof/hist/*.nc")
    ap.add_argument("--config", required=True,
                     help="Config (subdirectory) name to evaluate, e.g. control, irrigation_on")
    ap.add_argument("--crosswalk", default=DEFAULT_CROSSWALK)
    ap.add_argument("--obs-daily", default=DEFAULT_OBS_DAILY)
    ap.add_argument("--outdir", default=f"{paths.OUTPUT_ROOT}/streamflow",
                    help="default: %(default)s")
    ap.add_argument("--parallel", action="store_true",
                     help="Read mizuRoute files with dask's parallel=True "
                          "(default: serial, parallel=False)")
    ap.add_argument("--limit", type=int, default=None, help="Evaluate only first N gauges")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    rof = lio.rof_files(args.archive_root, args.config)
    if not rof:
        sys.exit(f"No mizuRoute files under {args.archive_root}/{args.config}/rof/hist")
    df_gauges = lio.read_crosswalk(args.crosswalk)
    if args.limit:
        df_gauges = df_gauges.head(args.limit)

    ds_rof, reach_ids = lio.open_mizuroute(rof, ["RoutedRunoff"], parallel=args.parallel)
    print(f"[mizuroute] {len(rof)} files, {len(reach_ids)} reaches, "
          f"time {ds_rof.time.values[0]} -> {ds_rof.time.values[-1]} "
          f"({'parallel' if args.parallel else 'serial'} read)")
    ds_obs, flow_var, obs_sites = lio.open_obs_daily(args.obs_daily)

    print(f"[{args.config}] bulk-extracting {len(df_gauges)} reaches + gauges ...")
    modeled_df = lio.bulk_extract(ds_rof["RoutedRunoff"], reach_ids,
                                  df_gauges["merit_reach_id"].astype(int).tolist())
    obs_slice = ds_obs[flow_var].sel(time=slice(lio.EVAL_START, lio.EVAL_END))
    wanted_gages = pd.to_numeric(df_gauges["GAGE_ID"], errors="coerce").dropna().astype(int).tolist()
    observed_df = lio.bulk_extract(obs_slice, obs_sites, wanted_gages, resample="MS")

    print(f"[{args.config}] computing metrics (vectorized, no per-gauge loop) ...")
    results = vectorized_metrics(df_gauges, modeled_df, observed_df)
    ok = results.dropna(subset=["NSE"])

    out_path = os.path.join(args.outdir, f"{args.config}_streamflow_eval.csv")
    results.to_csv(out_path, index=False)
    print(f"\n[{args.config}] {len(ok)}/{len(df_gauges)} gauges evaluated "
          f"(rest: missing reach/gauge or <{metrics.MIN_MONTHS} months overlap)")
    if len(ok):
        print(f"  median NSE={ok['NSE'].median():.3f}, "
              f"median KGE={ok['KGE'].median():.3f}, "
              f"median PBIAS={ok['PBIAS'].median():.1f}%")
        best = ok.loc[ok["NSE"].idxmax()]
        worst = ok.loc[ok["NSE"].idxmin()]
        print(f"  best:  {best.get('Long_Name', best.get('Station ID'))} "
              f"NSE={best['NSE']:.3f}")
        print(f"  worst: {worst.get('Long_Name', worst.get('Station ID'))} "
              f"NSE={worst['NSE']:.3f}")
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()
