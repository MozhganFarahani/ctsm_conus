#!/usr/bin/env python
"""
CTSM control-run exploration & sanity checks — SIF-T FY26 (Farahani)
=======================================================================

Purpose
-------
First pass over the control-configuration CTSM (h0/h1) + mizuRoute output
before branching into the four sensitivity experiments (SP vs. prognostic
phenology, static vs. evolving land cover, irrigation on/off, hillslope
hydrology on/off). This script does NOT compare to NLDAS/obs yet — it just
answers "is the control run sane and what do we actually have" so that step
is grounded in real numbers.

What it does
------------
1. Discovers h0 (monthly-ish diagnostic), h1 (higher-freq), and mizuRoute
   files under the paths you give it.
2. Opens each stream lazily with dask (safe for full-CONUS, full-time).
3. Prints an inventory: variables, dims, chunk sizes, time range, any gaps.
4. Runs a water-balance closure check (P - ET - R - dS/dt ≈ 0) at the
   domain scale as a first-order sanity check.
5. Checks mizuRoute streamflow for obviously broken reaches (all-zero,
   all-NaN, negative flow).
6. Saves a few quick-look plots (domain-mean time series, spatial maps of
   long-term means) to `--outdir` so you can eyeball results without a
   GUI session on Casper.

Usage
-----
    module load conda && conda activate npl   # or your CTSM postprocessing env
    python ctsm_control_explore.py \\
        --h0 "/glade/derecho/scratch/mozhgana/archive/control/lnd/hist/*.h0a.*.nc" \\
        --h1 "/glade/derecho/scratch/mozhgana/archive/control/lnd/hist/*.h1a.*.nc" \\
        --mizuroute "/glade/derecho/scratch/mozhgana/archive/control/rof/hist/*.nc" \\
        --lnd-in /glade/work/mozhgana/ctsm_conus/cime/scripts/control/CaseDocs/lnd_in \\
        --outdir ./control_qc

Notes
-----
- EDIT THE PATHS in --h0/--h1/--mizuroute (glob patterns, quote them so the
  shell doesn't expand the wildcard) or just call this with defaults edited
  below in `DEFAULT_PATHS`.
- CONUS at ~10 km, full time series is large. This uses dask chunking and
  only pulls small reductions (means, sums) into memory — it never loads
  the full array. If you hit memory errors, reduce `--chunk-time`.
- Variable names are tuned to Mozhgan's actual control-run lnd_in
  (hist_fincl1/2): RAIN+SNOW for precip, QFLX_EVAP_TOT for ET, QRUNOFF for
  total runoff, TWS for total water storage (used directly for dS/dt rather
  than reconstructed from SWE+soil water). If a variable is missing the
  script says so and skips that check rather than guessing.
- Pass --lnd-in to also parse the CTSM namelist and print a one-line config
  summary (phenology mode, land cover, irrigation, hillslope) — useful once
  you're running the 4 sensitivity configs and want a quick record of which
  axis each one flips relative to control.
"""

import argparse
import glob
import os
import sys
import warnings

import numpy as np

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# EDIT THESE if you'd rather not pass --h0/--h1/--mizuroute every time
# ---------------------------------------------------------------------------
DEFAULT_PATHS = {
    "h0": "/glade/derecho/scratch/mozhgana/archive/control/lnd/hist/*.h0a.*.nc",
    "h1": "/glade/derecho/scratch/mozhgana/archive/control/lnd/hist/*.h1a.*.nc",
    "mizuroute": "/glade/derecho/scratch/mozhgana/archive/control/rof/hist/*.nc",
}

# Water-balance terms, matched to the actual control-run hist_fincl1/2 list:
# RAIN, SNOW, QFLX_EVAP_TOT, QRUNOFF, TWS are all present in both h0 and h1.
WBAL_VARS = {
    "rain": "RAIN",
    "snow": "SNOW",
    "et": "QFLX_EVAP_TOT",
    "runoff": "QRUNOFF",
    "storage": "TWS",   # use directly for dS/dt instead of reconstructing
}


def parse_namelist(path):
    """Minimal Fortran-namelist parser: handles 'key = value[, value...]'
    lines, continuation lines (no new 'key ='), and strips !-comments.
    Good enough for lnd_in / user_nl_clm — not a general namelist parser."""
    nml = {}
    current_key = None
    with open(path) as f:
        for raw in f:
            line = raw.split("!")[0].strip()
            if not line or line.startswith("&") or line == "/":
                continue
            if "=" in line and not line.startswith("'"):
                key, _, val = line.partition("=")
                key = key.strip()
                if key.replace("_", "").isalnum():
                    current_key = key
                    nml[current_key] = val.strip().rstrip(",")
                    continue
            if current_key:
                nml[current_key] += " " + line.rstrip(",")
    return nml


def summarize_config(nml):
    def flag(key, default="?"):
        v = nml.get(key, default)
        return v.replace("'", "").strip()

    use_cn = flag("use_cn")
    irrigate = flag("irrigate")
    use_hillslope = flag("use_hillslope")
    use_hillslope_routing = flag("use_hillslope_routing")
    has_dynlu = "flanduse_timeseries" in nml
    finidat = flag("finidat")
    start_ymd = flag("start_ymd")

    phenology = "SP (satellite phenology)" if use_cn == ".false." else \
                "prognostic (CN/BGC)" if use_cn == ".true." else "unknown (use_cn=%s)" % use_cn
    landcover = "evolving (flanduse_timeseries set)" if has_dynlu else "static"

    print("\n--- Control config summary (from lnd_in) ---")
    print(f"  Phenology:          {phenology}")
    print(f"  Land cover:         {landcover}")
    print(f"  Irrigation:         {'ON' if irrigate == '.true.' else 'OFF' if irrigate == '.false.' else irrigate}")
    print(f"  Hillslope hydrology: {'ON' if use_hillslope == '.true.' else 'OFF' if use_hillslope == '.false.' else use_hillslope} "
          f"(routing: {use_hillslope_routing})")
    print(f"  finidat (restart):  {finidat}")
    print(f"  start_ymd:          {start_ymd}")
    if finidat and start_ymd.isdigit() and len(start_ymd) == 8:
        # finidat filename usually embeds a date like ...r.YYYY-MM-DD-SSSSS.nc
        import re
        m = re.search(r"(\d{4})-\d{2}-\d{2}", finidat)
        if m and m.group(1) != start_ymd[:4]:
            print(f"  NOTE: finidat restart year ({m.group(1)}) differs from "
                  f"start_ymd year ({start_ymd[:4]}) — confirm this is the "
                  f"intended spinup->transient handoff, not a stale restart file.")
    print("(Record this per-run — once the 4 sensitivity configs exist, diffing "
          "these lines against control is the fastest way to confirm each run "
          "only flips the one intended axis.)")


def try_import_xarray():
    try:
        import xarray as xr  # noqa
        return xr
    except ImportError:
        sys.exit(
            "xarray not found. On Casper/Derecho: `module load conda` then "
            "`conda activate npl` (or your CTSM postprocessing env) before "
            "running this script."
        )


def discover(pattern, label):
    files = sorted(glob.glob(pattern))
    print(f"\n[{label}] pattern: {pattern}")
    print(f"[{label}] found {len(files)} file(s)")
    if files:
        print(f"[{label}] first: {os.path.basename(files[0])}")
        print(f"[{label}] last:  {os.path.basename(files[-1])}")
    else:
        print(f"[{label}] WARNING: no files matched — check the path/glob.")
    return files


def open_stream(xr, files, chunk_time, label):
    if not files:
        return None
    try:
        ds = xr.open_mfdataset(
            files,
            combine="by_coords",
            parallel=True,
            chunks={"time": chunk_time},
            decode_times=True,
        )
        print(f"[{label}] opened OK — {len(ds.data_vars)} variables, "
              f"time range {ds.time.values[0]} -> {ds.time.values[-1]}")
        return ds
    except Exception as e:
        print(f"[{label}] ERROR opening dataset: {e}")
        return None


def inventory(ds, label, outdir):
    if ds is None:
        return
    lines = [f"=== {label} inventory ===",
             f"dims: {dict(ds.dims)}",
             f"n_timesteps: {ds.dims.get('time', 'NA')}",
             "", "variables:"]
    for v in sorted(ds.data_vars):
        da = ds[v]
        units = da.attrs.get("units", "?")
        long_name = da.attrs.get("long_name", "")
        lines.append(f"  {v:20s} dims={da.dims} units={units:10s} {long_name}")
    text = "\n".join(lines)
    print(text[:3000] + ("\n...(truncated, see file)" if len(text) > 3000 else ""))
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, f"{label}_inventory.txt"), "w") as f:
        f.write(text)


def find_var(ds, candidates):
    for name in candidates:
        if name in ds.data_vars:
            return name
    return None


def check_time_gaps(ds, label):
    if ds is None or "time" not in ds.coords:
        return
    t = ds["time"].values
    if len(t) < 3:
        return
    diffs = np.diff(t).astype("timedelta64[h]").astype(float)
    typical = np.median(diffs)
    gaps = np.where(np.abs(diffs - typical) > 0.1 * typical + 1e-6)[0]
    if len(gaps):
        print(f"[{label}] WARNING: {len(gaps)} irregular time step(s) "
              f"(typical spacing {typical:.1f}h). First few indices: {gaps[:5]}")
    else:
        print(f"[{label}] time steps regular (~{typical:.1f}h spacing), "
              f"n={len(t)}")


def water_balance_check(xr, ds, label, outdir):
    """Domain-mean water balance closure: dTWS/dt ?= (RAIN+SNOW) - ET - QRUNOFF,
    all in mm/day. Uses TWS directly (present in both h0/h1) rather than
    reconstructing storage from SWE + soil layers piecemeal."""
    if ds is None:
        return

    names = {k: v for k, v in WBAL_VARS.items()}
    missing = [v for v in names.values() if v not in ds.data_vars]
    if missing:
        print(f"[{label}] water-balance check skipped — missing vars: {missing} "
              f"(unexpected — these are in the control run's hist_fincl list; "
              f"check this stream actually is h0/h1 and not something else)")
        return

    print(f"[{label}] running water balance check: "
          f"dTWS/dt vs (RAIN+SNOW) - QFLX_EVAP_TOT - QRUNOFF")

    def domain_mean(da):
        weight = None
        for wname in ["landfrac", "area"]:
            if wname in ds:
                weight = ds[wname]
                break
        spatial_dims = [d for d in da.dims if d != "time"]
        if weight is not None:
            # landfrac/area are physically time-invariant, but some CTSM
            # archives write them with a 'time' dim anyway. Take a single
            # time slice so weight.sum() doesn't accidentally collapse
            # across time too (that silently corrupts the weighted mean).
            if "time" in weight.dims:
                weight = weight.isel(time=0)
            return (da * weight).sum(dim=spatial_dims) / weight.sum(dim=spatial_dims)
        return da.mean(dim=spatial_dims)

    # Flux terms: CTSM gives these as mm/s (kg/m2/s) -> convert to mm/day
    precip = domain_mean(ds[names["rain"]] + ds[names["snow"]]) * 86400
    et = domain_mean(ds[names["et"]]) * 86400
    runoff = domain_mean(ds[names["runoff"]]) * 86400

    # Storage: TWS is already mm; take the time derivative (per day) using
    # the actual timestep spacing rather than assuming daily.
    tws = domain_mean(ds[names["storage"]])
    dt_days = (ds["time"].diff("time").astype("timedelta64[s]").astype(float) / 86400.0)
    dtws_dt = tws.diff("time") / dt_days.values

    # Align: dtws_dt and the flux terms both drop the first timestep
    flux_rhs = (precip - et - runoff).isel(time=slice(1, None))
    residual = (dtws_dt - flux_rhs).compute()

    print(f"[{label}] closure residual [dTWS/dt - (P-ET-R)] (mm/day): "
          f"mean={float(residual.mean()):.4f}, "
          f"std={float(residual.std()):.4f}, "
          f"min={float(residual.min()):.4f}, max={float(residual.max()):.4f}")
    print(f"[{label}] (a well-behaved run should have this residual small and "
          f"centered near zero — near-zero mean with nonzero std is normal "
          f"noise from averaging-interval effects; a systematic nonzero mean, "
          f"especially one that grows over the run, points to a mass-balance "
          f"bug or ongoing spinup drift worth resolving before branching into "
          f"the 4 sensitivity configs)")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
        flux_rhs.plot(ax=axes[0], label="P - ET - R")
        dtws_dt.plot(ax=axes[0], label="dTWS/dt", alpha=0.7)
        axes[0].legend()
        axes[0].set_ylabel("mm/day")
        axes[0].set_title(f"{label}: domain-mean water balance terms")

        residual.plot(ax=axes[1])
        axes[1].axhline(0, color="k", lw=0.5)
        axes[1].set_ylabel("residual (mm/day)")
        axes[1].set_title("closure residual")

        os.makedirs(outdir, exist_ok=True)
        fig.tight_layout()
        fig.savefig(os.path.join(outdir, f"{label}_water_balance.png"), dpi=150)
        plt.close(fig)
        print(f"[{label}] saved plot -> {outdir}/{label}_water_balance.png")
    except Exception as e:
        print(f"[{label}] plot failed (non-fatal): {e}")


def check_mizuroute(xr, files, outdir):
    if not files:
        print("\n[mizuRoute] no files found — skipping streamflow checks.")
        return
    ds = open_stream(xr, files, chunk_time=500, label="mizuRoute")
    if ds is None:
        return
    inventory(ds, "mizuroute", outdir)

    flow_name = None
    for cand in ["RoutedRunoff", "IRFroutedRunoff", "KWTroutedRunoff", "Qout", "flow"]:
        if cand in ds.data_vars:
            flow_name = cand
            break
    if flow_name is None:
        print("[mizuRoute] could not identify a routed-flow variable — "
              "check inventory file for the actual name and adjust the script.")
        return

    q = ds[flow_name]
    print(f"[mizuRoute] using flow var '{flow_name}', dims={q.dims}")

    n_reaches = q.sizes.get("seg", q.sizes.get("reachID", None))
    all_zero = (q == 0).all(dim="time").compute()
    all_nan = q.isnull().all(dim="time").compute()
    has_negative = (q < 0).any(dim="time").compute()

    print(f"[mizuRoute] reaches: {n_reaches}")
    print(f"[mizuRoute] reaches with all-zero flow: {int(all_zero.sum())}")
    print(f"[mizuRoute] reaches with all-NaN flow:  {int(all_nan.sum())}")
    print(f"[mizuRoute] reaches with any negative flow: {int(has_negative.sum())}")
    print("[mizuRoute] (all-zero/NaN reaches are worth spot-checking against "
          "the river network — could be headwater artifacts or a routing "
          "config issue; negative flow generally indicates a bug)")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--h0", default=DEFAULT_PATHS["h0"],
                     help="Glob pattern for h0 history files")
    ap.add_argument("--h1", default=DEFAULT_PATHS["h1"],
                     help="Glob pattern for h1 history files")
    ap.add_argument("--mizuroute", default=DEFAULT_PATHS["mizuroute"],
                     help="Glob pattern for mizuRoute output files")
    ap.add_argument("--outdir", default="./control_qc",
                     help="Where to write inventories and plots")
    ap.add_argument("--chunk-time", type=int, default=30,
                     help="Dask chunk size along time dim (tune for memory)")
    ap.add_argument("--lnd-in", default=None,
                     help="Path to this run's lnd_in namelist (or user_nl_clm) "
                          "to auto-print a config summary (phenology, land "
                          "cover, irrigation, hillslope)")
    args = ap.parse_args()

    xr = try_import_xarray()
    os.makedirs(args.outdir, exist_ok=True)

    if args.lnd_in:
        print("=" * 70)
        print("STEP 0: parse namelist")
        print("=" * 70)
        try:
            nml = parse_namelist(args.lnd_in)
            summarize_config(nml)
        except Exception as e:
            print(f"Could not parse {args.lnd_in}: {e}")

    print("=" * 70)
    print("STEP 1: discover files")
    print("=" * 70)
    h0_files = discover(args.h0, "h0")
    h1_files = discover(args.h1, "h1")
    mizu_files = discover(args.mizuroute, "mizuroute")

    print("\n" + "=" * 70)
    print("STEP 2: open + inventory h0 / h1")
    print("=" * 70)
    ds_h0 = open_stream(xr, h0_files, args.chunk_time, "h0")
    inventory(ds_h0, "h0", args.outdir)
    check_time_gaps(ds_h0, "h0")

    ds_h1 = open_stream(xr, h1_files, args.chunk_time, "h1")
    inventory(ds_h1, "h1", args.outdir)
    check_time_gaps(ds_h1, "h1")

    print("\n" + "=" * 70)
    print("STEP 3: water balance sanity check (control config)")
    print("=" * 70)
    # h1 is usually the higher-frequency stream with the flux terms needed;
    # falls back to h0 if h1 doesn't have them.
    water_balance_check(xr, ds_h1 if ds_h1 is not None else ds_h0,
                         "h1" if ds_h1 is not None else "h0", args.outdir)

    print("\n" + "=" * 70)
    print("STEP 4: mizuRoute streamflow checks")
    print("=" * 70)
    check_mizuroute(xr, mizu_files, args.outdir)

    print("\n" + "=" * 70)
    print(f"DONE. Inventories, logs-worthy output, and plots are in: {args.outdir}")
    print("Next steps once this looks clean:")
    print("  1. Pull in NLDAS (or chosen obs product) on the same grid/period")
    print("     for snow (SWE), soil moisture, ET, runoff comparison.")
    print("  2. Regrid/align mizuRoute reaches to USGS gauge locations for")
    print("     streamflow verification (reuse your SUMMA/USACE workflow).")
    print("  3. Once control checks out, set up the 4 sensitivity configs")
    print("     (SP/prognostic phenology, static/evolving land cover,")
    print("     irrigation on/off, hillslope hydrology on/off) as diffs")
    print("     against this control.")
    print("=" * 70)


if __name__ == "__main__":
    main()