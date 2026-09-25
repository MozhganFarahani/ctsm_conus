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
per-gauge work is this cheap -- see ctsm_streamflow_eval_multiconfig.py's
docstring for the numbers).

--parallel controls dask's multi-threaded reading of the mizuRoute file set
(xr.open_mfdataset(parallel=...)) -- meaningful when you have hundreds of
files, since it reads them concurrently rather than one at a time.

Usage
-----
    module load conda && conda activate npl

    python ctsm_streamflow_eval.py \\
        --archive-root /glade/derecho/scratch/mozhgana/archive \\
        --config control \\
        --outdir ./control_qc/streamflow

    python ctsm_streamflow_eval.py --archive-root ... --config irrig_on \\
        --outdir ./irrig_on_qc/streamflow --parallel --limit 100
"""

import argparse
import glob
import os
import sys
import warnings

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "config"))
import paths  # analysis/config/paths.py

warnings.filterwarnings("ignore", category=FutureWarning, module="xarray")

MODEL_START, MODEL_END = "1980-10-01", "2018-09-30"
MIN_MONTHS = 12
DEFAULT_CROSSWALK = paths.CROSSWALK
DEFAULT_OBS_DAILY = paths.OBS_DAILY


def load_mizuroute(pattern, parallel):
    import xarray as xr
    files = sorted(glob.glob(pattern))
    if not files:
        sys.exit(f"No mizuRoute files matched: {pattern}")
    keep = lambda ds: ds[[v for v in ("RoutedRunoff", "reachID") if v in ds.variables]]
    ds = xr.open_mfdataset(files, combine="nested", concat_dim="time",
                            decode_times=True, parallel=parallel,
                            engine="netcdf4", preprocess=keep)
    reach_id_1d = ds["reachID"].isel(time=0).compute().values.astype(int)
    print(f"[mizuroute] {len(files)} files, {len(reach_id_1d)} reaches, "
          f"time {ds.time.values[0]} -> {ds.time.values[-1]} "
          f"({'parallel' if parallel else 'serial'} read)")
    return ds, reach_id_1d


def bulk_extract(da, ids_present, wanted_ids, freq_resample=None):
    """One indexed read for all wanted_ids at once, aligned to a monthly
    PeriodIndex. `da` must have a 'seg' or 'site' dim matching ids_present."""
    dim = "seg" if "seg" in da.dims else "site"
    valid = [i for i in wanted_ids if i in ids_present]
    if not valid:
        return pd.DataFrame()
    sub = da.sel({dim: valid}).compute() if dim == "site" else \
          da.isel({dim: [ids_present.index(i) for i in valid]}).compute()

    time_vals = sub["time"].values
    if freq_resample:
        # Needs real datetime arithmetic for daily->monthly resampling.
        # Observed data's calendar is standard, so pd.to_datetime is fine here.
        df = pd.DataFrame(sub.values, index=pd.to_datetime(time_vals), columns=valid)
        df = df.resample(freq_resample).mean()
        df.index = pd.PeriodIndex(df.index, freq="M")
    else:
        # FIX: mizuRoute output commonly uses a noleap calendar, decoded by
        # xarray as cftime.DatetimeNoLeap objects, which pd.to_datetime()
        # cannot convert at all (raises TypeError). Since this is already
        # monthly and only needs month-level alignment, build the
        # PeriodIndex directly from year/month rather than routing through
        # a datetime64 conversion that may not support the calendar in use.
        if isinstance(time_vals[0], np.datetime64):
            period_idx = pd.PeriodIndex(pd.to_datetime(time_vals), freq="M")
        else:  # cftime object (e.g. DatetimeNoLeap, Datetime360Day, etc.)
            period_idx = pd.PeriodIndex(
                [f"{t.year}-{t.month:02d}" for t in time_vals], freq="M")
        df = pd.DataFrame(sub.values, index=period_idx, columns=valid)
    return df


def vectorized_metrics(df_gauges, modeled_df, observed_df):
    """NSE/KGE/PBIAS for every gauge at once -- no per-gauge loop.
    Aligns modeled/observed to a common monthly index and gauge order,
    then does the math as 2D numpy array reductions along the time axis."""
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
    M = modeled_df.loc[common_idx, reach_ids].to_numpy(dtype=float)
    O = observed_df.loc[common_idx, gage_ids].to_numpy(dtype=float)

    mask = ~np.isnan(M) & ~np.isnan(O)
    n_valid = mask.sum(axis=0)
    Mm, Om = np.where(mask, M, np.nan), np.where(mask, O, np.nan)

    obs_mean, sim_mean = np.nanmean(Om, axis=0), np.nanmean(Mm, axis=0)
    sse = np.nansum((Om - Mm) ** 2, axis=0)
    sst = np.nansum((Om - obs_mean) ** 2, axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        nse = 1 - sse / sst
        obs_std = np.nanstd(Om, axis=0, ddof=1)
        sim_std = np.nanstd(Mm, axis=0, ddof=1)
        # FIX: must use the same ddof=1 (sample) normalization here as the
        # stds above -- nanmean() divides by n, not n-1, which desynced the
        # covariance from the std convention and biased corr (caught by
        # cross-checking against the scalar pandas .corr()/.std() version;
        # max abs diff was 7e-3 before this fix, ~1e-14 after).
        cov = np.nansum((Om - obs_mean) * (Mm - sim_mean), axis=0) / (n_valid - 1)
        corr = cov / (obs_std * sim_std)
        alpha, beta = sim_std / obs_std, sim_mean / obs_mean
        kge = 1 - np.sqrt((corr - 1) ** 2 + (alpha - 1) ** 2 + (beta - 1) ** 2)
        pbias = 100 * (sim_mean - obs_mean) / obs_mean

    out = df_gauges.copy()
    out["n_months"], out["NSE"], out["KGE"], out["PBIAS"], out["corr"] = \
        n_valid, nse, kge, pbias, corr
    out.loc[out["n_months"] < MIN_MONTHS, ["NSE", "KGE", "PBIAS", "corr"]] = np.nan
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--archive-root", default=paths.ARCHIVE,
                     help="Directory containing {config}/rof/hist/*.nc")
    ap.add_argument("--config", required=True,
                     help="Config (subdirectory) name to evaluate, e.g. control, irrig_on")
    ap.add_argument("--crosswalk", default=DEFAULT_CROSSWALK)
    ap.add_argument("--obs-daily", default=DEFAULT_OBS_DAILY)
    ap.add_argument("--outdir", default="./streamflow_eval")
    ap.add_argument("--parallel", action="store_true",
                     help="Read mizuRoute files with dask's parallel=True "
                          "(default: serial, parallel=False)")
    ap.add_argument("--limit", type=int, default=None, help="Evaluate only first N gauges")
    args = ap.parse_args()

    import os
    os.makedirs(args.outdir, exist_ok=True)
    import xarray as xr

    mizuroute_pattern = os.path.join(args.archive_root, args.config, "rof", "hist", "*.nc")
    df_gauges = pd.read_csv(args.crosswalk)
    if args.limit:
        df_gauges = df_gauges.head(args.limit)

    ds_rof, reach_id_1d = load_mizuroute(mizuroute_pattern, args.parallel)
    ds_obs = xr.open_dataset(args.obs_daily, decode_times=True, engine="netcdf4")
    flow_var = next((v for v in ds_obs.data_vars
                      if v.lower() in ("flow", "streamflow", "discharge", "q")),
                     list(ds_obs.data_vars)[0])
    obs_sites = list(ds_obs["site"].values.astype(int))

    print(f"[{args.config}] bulk-extracting {len(df_gauges)} reaches + gauges ...")
    modeled_df = bulk_extract(ds_rof["RoutedRunoff"], list(reach_id_1d),
                               df_gauges["merit_reach_id"].astype(int).tolist())
    obs_slice = ds_obs[flow_var].sel(time=slice(MODEL_START, MODEL_END))
    wanted_gages = pd.to_numeric(df_gauges["GAGE_ID"], errors="coerce").dropna().astype(int).tolist()
    observed_df = bulk_extract(obs_slice, obs_sites, wanted_gages, freq_resample="MS")

    print(f"[{args.config}] computing metrics (vectorized, no per-gauge loop) ...")
    results = vectorized_metrics(df_gauges, modeled_df, observed_df)
    ok = results.dropna(subset=["NSE"])

    out_path = os.path.join(args.outdir, f"{args.config}_streamflow_eval.csv")
    results.to_csv(out_path, index=False)
    print(f"\n[{args.config}] {len(ok)}/{len(df_gauges)} gauges evaluated "
          f"(rest: missing reach/gauge or <{MIN_MONTHS} months overlap)")
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
