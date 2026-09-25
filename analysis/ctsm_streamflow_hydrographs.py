#!/usr/bin/env python
"""
CTSM control-run streamflow hydrograph sanity check — SIF-T FY26 (Farahani)
=======================================================================

Purpose
-------
Quick plausibility check on mizuRoute output before investing in a full
USGS gauge comparison: pull the reaches with the largest long-term mean
flow (which, on a CONUS domain, are almost certainly the outlets of major
rivers like the Mississippi, Missouri, Columbia) and plot their hydrographs.
Sanity-check: right order of magnitude? Right seasonal shape (spring
snowmelt peak in the Missouri/Columbia, more distributed flow in the
Mississippi, etc.)? Obviously broken (flat line, negative, spiky garbage)?

This does NOT require a river-network/name crosswalk file to run — it finds
the largest reaches by flow magnitude automatically. If you have a
reach-ID-to-name crosswalk (e.g. from your SUMMA/USACE gauge work), pass it
with --crosswalk to get real river names instead of bare reach IDs.

Usage
-----
    module load conda && conda activate npl
    python ctsm_streamflow_hydrographs.py \\
        --mizuroute "/glade/derecho/scratch/mozhgana/archive/control/rof/hist/*.nc" \\
        --outdir ./control_qc/streamflow \\
        --top-n 6

    # with a crosswalk CSV (columns: reachID,name — extra columns ignored)
    python ctsm_streamflow_hydrographs.py \\
        --mizuroute "..." --outdir ./control_qc/streamflow \\
        --crosswalk /path/to/reach_names.csv

    # or plot specific reaches you already know the IDs for:
    python ctsm_streamflow_hydrographs.py \\
        --mizuroute "..." --outdir ./control_qc/streamflow \\
        --reach-ids 71001234,71005678
"""

import argparse
import csv
import glob
import os
import sys
import warnings

import numpy as np

warnings.filterwarnings("ignore")


def try_import_xarray():
    try:
        import xarray as xr  # noqa
        return xr
    except ImportError:
        sys.exit(
            "xarray not found. On Casper/Derecho: `module load conda` then "
            "`conda activate npl` before running this script."
        )


def open_mizuroute(xr, pattern, chunk_time):
    files = sorted(glob.glob(pattern))
    print(f"mizuRoute pattern: {pattern}")
    print(f"mizuRoute files found: {len(files)}")
    if not files:
        sys.exit("No mizuRoute files matched — check --mizuroute path.")
    try:
        ds = xr.open_mfdataset(
            files, combine="by_coords", parallel=True,
            chunks={"time": chunk_time}, decode_times=True,
            engine="netcdf4",
        )
    except (ImportError, ValueError) as e:
        sys.exit(
            f"Failed to open with engine='netcdf4' ({e}).\n"
            "Fix: `module load conda && conda activate npl` before running "
            "this script, and confirm with `python -c \"import netCDF4\"`."
        )
    if "RoutedRunoff" not in ds.data_vars:
        sys.exit(f"'RoutedRunoff' not found. Variables present: "
                  f"{list(ds.data_vars)}")
    print(f"mizuRoute opened OK — time range {ds.time.values[0]} -> "
          f"{ds.time.values[-1]}, n_timesteps={ds.sizes['time']}, "
          f"n_reaches={ds.sizes['seg']}")
    return ds


def load_crosswalk(path):
    """CSV with at least columns 'reachID' and 'name'. Returns dict."""
    mapping = {}
    with open(path) as f:
        reader = csv.DictReader(f)
        if "reachID" not in reader.fieldnames or "name" not in reader.fieldnames:
            sys.exit(f"--crosswalk file must have 'reachID' and 'name' "
                      f"columns. Found: {reader.fieldnames}")
        for row in reader:
            try:
                mapping[int(row["reachID"])] = row["name"]
            except ValueError:
                continue
    print(f"Loaded {len(mapping)} reachID->name mappings from {path}")
    return mapping


def find_top_reaches(ds, top_n, scan_limit=3000, corr_threshold=0.999):
    """Long-term mean flow per reach, then greedily pick the top_n reaches
    that are NOT near-duplicates of an already-picked one. Near-duplicates
    happen constantly on real river networks: a big river's outlet is often
    split into several consecutive segments (or, near a delta, several
    physically distinct distributary channels carrying almost the same
    water) that all show up at the top of a plain flow-magnitude sort.
    Two reaches are treated as 'the same river' if their full time series
    correlate above corr_threshold — literally the same water shifted by a
    routing lag correlates ~1.0; a genuinely different river's flow does not."""
    print(f"Computing long-term mean flow per reach (n={ds.sizes['seg']}) ...")
    mean_flow = ds["RoutedRunoff"].mean(dim="time").compute()
    reach_ids = ds["reachID"].isel(time=0).compute().values.astype(int)

    order = np.argsort(mean_flow.values)[::-1][:scan_limit]

    selected = []          # list of (seg_idx, reachID, mean_flow)
    selected_series = []   # parallel list of the actual time series (np arrays)
    skipped_duplicates = 0

    for seg_idx in order:
        if len(selected) >= top_n:
            break
        candidate_ts = ds["RoutedRunoff"].isel(seg=int(seg_idx)).compute().values
        is_duplicate = False
        for sel_ts in selected_series:
            corr = np.corrcoef(candidate_ts, sel_ts)[0, 1]
            if corr > corr_threshold:
                is_duplicate = True
                skipped_duplicates += 1
                break
        if not is_duplicate:
            selected.append((int(seg_idx), int(reach_ids[seg_idx]), float(mean_flow.values[seg_idx])))
            selected_series.append(candidate_ts)

    if skipped_duplicates:
        print(f"(skipped {skipped_duplicates} near-duplicate reaches — same "
              f"river represented as multiple segments/distributaries, "
              f"correlation > {corr_threshold})")

    print(f"\nTop {len(selected)} DISTINCT reaches by long-term mean flow:")
    for seg_idx, rid, flow in selected:
        print(f"  seg_index={seg_idx:8d}  reachID={rid:12d}  "
              f"mean_flow={flow:10.1f} m3/s")
    return selected


def find_reaches_by_id(ds, reach_ids_wanted):
    reach_ids = ds["reachID"].isel(time=0).compute().values.astype(int)
    results = []
    for rid in reach_ids_wanted:
        matches = np.where(reach_ids == rid)[0]
        if len(matches) == 0:
            print(f"WARNING: reachID {rid} not found in this dataset — skipping.")
            continue
        seg_idx = int(matches[0])
        mean_flow = float(ds["RoutedRunoff"].isel(seg=seg_idx).mean(dim="time").compute())
        results.append((seg_idx, rid, mean_flow))
    return results


def plot_hydrographs(ds, reaches, outdir, label, crosswalk):
    os.makedirs(outdir, exist_ok=True)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not available — skipping plots (data still printed above).")
        return

    n = len(reaches)
    if n == 0:
        print("No reaches to plot.")
        return

    fig, axes = plt.subplots(n, 1, figsize=(11, 2.6 * n), sharex=True)
    if n == 1:
        axes = [axes]

    for ax, (seg_idx, rid, mean_flow) in zip(axes, reaches):
        ts = ds["RoutedRunoff"].isel(seg=seg_idx).compute()
        name = crosswalk.get(rid, None)
        title = f"reachID {rid}" + (f" — {name}" if name else "")
        ts.plot(ax=ax, linewidth=0.8)
        ax.set_title(f"{title}  (mean={mean_flow:,.0f} m\u00b3/s)", fontsize=10)
        ax.set_ylabel("m\u00b3/s")
        ax.axhline(0, color="k", lw=0.4)

    axes[-1].set_xlabel("")
    fig.suptitle(f"{label}: streamflow hydrographs, largest reaches", y=1.0)
    fig.tight_layout()
    out_path = os.path.join(outdir, f"{label}_top_reach_hydrographs.png")
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\nSaved plot -> {out_path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mizuroute", required=True,
                     help="Glob pattern for mizuRoute output files")
    ap.add_argument("--outdir", default="./control_qc/streamflow")
    ap.add_argument("--label", default="control")
    ap.add_argument("--top-n", type=int, default=6,
                     help="How many largest-flow DISTINCT reaches to plot (ignored if --reach-ids given)")
    ap.add_argument("--corr-threshold", type=float, default=0.999,
                     help="Reaches whose flow correlates above this with an "
                          "already-selected reach are treated as the same "
                          "river and skipped (default 0.999)")
    ap.add_argument("--reach-ids", default=None,
                     help="Comma-separated specific reachID values to plot instead of auto top-N")
    ap.add_argument("--crosswalk", default=None,
                     help="Optional CSV with 'reachID','name' columns to label known rivers")
    ap.add_argument("--chunk-time", type=int, default=100)
    args = ap.parse_args()

    xr = try_import_xarray()
    ds = open_mizuroute(xr, args.mizuroute, args.chunk_time)

    crosswalk = load_crosswalk(args.crosswalk) if args.crosswalk else {}

    if args.reach_ids:
        wanted = [int(x) for x in args.reach_ids.split(",")]
        reaches = find_reaches_by_id(ds, wanted)
    else:
        reaches = find_top_reaches(ds, args.top_n, corr_threshold=args.corr_threshold)

    plot_hydrographs(ds, reaches, args.outdir, args.label, crosswalk)

    print("\nWhat to look for:")
    print("  - Order of magnitude: Mississippi outlet is ~15,000-20,000 m3/s")
    print("    long-term mean (varies by exact reach location); Missouri/Columbia")
    print("    outlets are roughly 2,000-8,000 m3/s. If your top reach is off by")
    print("    orders of magnitude from this, worth investigating routing/topology.")
    print("  - Seasonal shape: snowmelt-fed basins (Missouri, Columbia, Colorado)")
    print("    should show a clear spring/early-summer peak; rain-dominated")
    print("    basins (lower Mississippi) should be flashier/more distributed.")
    print("  - No flat lines, no negative values, no implausible spikes.")
    print("  - If you have a reach-ID-to-USGS-gauge crosswalk from your")
    print("    SUMMA/USACE work, rerun with --crosswalk to label these by name")
    print("    and confirm you're actually looking at the rivers you think you are.")


if __name__ == "__main__":
    main()