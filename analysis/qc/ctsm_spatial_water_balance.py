#!/usr/bin/env python
"""
CTSM control-run spatial water-balance map — SIF-T FY26 (Farahani)
=======================================================================

Purpose
-------
The domain-mean water-balance check (ctsm_control_explore.py, Step 3) can
look clean while individual regions have real, compensating errors — e.g.
excess runoff in one region canceling a deficit somewhere else. This script
computes the water-balance closure residual PER GRID CELL, long-term mean
and by season, so regional problems don't hide behind a good domain average.

Why h0 (monthly), not h1 (daily)
---------------------------------
h1 is daily x 38 years x 224x464 grid — tens of GB per variable if you try
to hold it. h0 is monthly (456 steps), ~30x less data, and is plenty of
temporal resolution to see persistent SPATIAL bias patterns. This script
intentionally stays on h0. If you later want daily-resolution spatial maps
for a specific short period (e.g. one snowmelt season), that's a different,
narrower query — ask, don't rerun this on h1 wholesale.

What it does
------------
1. Opens h0 lazily with dask, chunked so nothing beyond the final small
   (lat, lon) reduction is ever pulled fully into memory.
2. Computes the per-gridcell closure residual: dTWS/dt - (RAIN+SNOW - ET -
   QRUNOFF), in mm/day, for every month.
3. Reduces to: long-term annual-mean residual map, residual std map
   (interannual variability), and a JJA-minus-DJF seasonal-asymmetry map
   (snowmelt-timing errors often show up here even when the annual mean
   looks fine).
4. Masks ocean/non-land cells using `landmask`.
5. Saves the small (lat,lon) result fields as NetCDF (reusable for diffing
   against the 4 sensitivity configs later) and as PNG maps.

Usage
-----
    module load conda && conda activate npl-2026a
    python ctsm_spatial_water_balance.py \\
        --h0 "/glade/derecho/scratch/mozhgana/archive/control/lnd/hist/*.h0a.*.nc" \\
        --outdir ./control_qc/spatial \\
        --label control

Recommend running this as a short batch job rather than interactively:
    qsub -I -l select=1:ncpus=4:mem=32GB -l walltime=00:30:00 -q casper -A "$PROJECT"
32 GB is generous headroom for h0-monthly at CONUS scale; adjust down if
your allocation is tight.
"""

import argparse
import glob
import os
import sys
import warnings

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config"))
import paths  # analysis/config/paths.py

warnings.filterwarnings("ignore")

WBAL_VARS = {
    "rain": "RAIN",
    "snow": "SNOW",
    "et": "QFLX_EVAP_TOT",
    "runoff": "QRUNOFF",
    "storage": "TWS",
}


def open_h0(xr, pattern, chunk_time):
    files = sorted(glob.glob(pattern))
    print(f"h0 pattern: {pattern}")
    print(f"h0 files found: {len(files)}")
    if not files:
        sys.exit("No h0 files matched — check --h0 path.")
    ds = xr.open_mfdataset(
        files, combine="by_coords", parallel=True,
        chunks={"time": chunk_time}, decode_times=True,
    )
    print(f"h0 opened OK — time range {ds.time.values[0]} -> {ds.time.values[-1]}, "
          f"n_timesteps={ds.sizes['time']}")
    missing = [v for v in WBAL_VARS.values() if v not in ds.data_vars]
    if missing:
        sys.exit(f"Missing required variable(s) in h0: {missing}")
    return ds


def compute_residual_field(ds):
    """Per-gridcell residual time series: dTWS/dt - (P - ET - R), mm/day.
    Keeps (time, lat, lon) — caller reduces further (mean/std/season)."""
    precip = (ds[WBAL_VARS["rain"]] + ds[WBAL_VARS["snow"]]) * 86400
    et = ds[WBAL_VARS["et"]] * 86400
    runoff = ds[WBAL_VARS["runoff"]] * 86400
    tws = ds[WBAL_VARS["storage"]]

    dt_days = ds["time"].diff("time").astype("timedelta64[s]").astype(float) / 86400.0
    dtws_dt = tws.diff("time") / dt_days

    flux_rhs = (precip - et - runoff).isel(time=slice(1, None))
    # align time coord exactly (diff() shifts it) before subtracting
    flux_rhs = flux_rhs.assign_coords(time=dtws_dt["time"])
    residual = dtws_dt - flux_rhs
    residual.name = "wbal_residual"
    residual.attrs["units"] = "mm/day"
    residual.attrs["long_name"] = "dTWS/dt - (RAIN+SNOW-QFLX_EVAP_TOT-QRUNOFF)"
    return residual


def get_land_mask(ds):
    for name in ["landmask", "landfrac"]:
        if name in ds:
            m = ds[name]
            if "time" in m.dims:
                m = m.isel(time=0)
            return (m > 0).compute()
    print("WARNING: no landmask/landfrac found — not masking ocean cells.")
    return None


def make_residual_maps(residual, land_mask, outdir, label):
    os.makedirs(outdir, exist_ok=True)

    print("Reducing: long-term mean, std ...")
    mean_map = residual.mean(dim="time").compute()
    std_map = residual.std(dim="time").compute()

    print("Reducing: seasonal (JJA - DJF) asymmetry ...")
    season = residual["time"].dt.season
    jja = residual.where(season == "JJA", drop=True).mean(dim="time")
    djf = residual.where(season == "DJF", drop=True).mean(dim="time")
    seasonal_diff = (jja - djf).compute()

    if land_mask is not None:
        mean_map = mean_map.where(land_mask)
        std_map = std_map.where(land_mask)
        seasonal_diff = seasonal_diff.where(land_mask)

    # --- save fields for reuse (e.g. diffing against sensitivity runs) ---
    import xarray as xr
    out_ds = xr.Dataset({
        "residual_mean": mean_map,
        "residual_std": std_map,
        "residual_jja_minus_djf": seasonal_diff,
    })
    nc_path = os.path.join(outdir, f"{label}_wbal_spatial.nc")
    out_ds.to_netcdf(nc_path)
    print(f"Saved spatial fields -> {nc_path}")

    # --- land-only summary stats (helps decide if maps show real problems) ---
    for name, field in [("annual-mean residual", mean_map),
                         ("residual std", std_map),
                         ("JJA-DJF residual asymmetry", seasonal_diff)]:
        vals = field.values
        vals = vals[np.isfinite(vals)]
        if len(vals) == 0:
            continue
        print(f"[{name}] land-cell stats (mm/day): "
              f"mean={np.mean(vals):.3f}, p5={np.percentile(vals,5):.3f}, "
              f"p95={np.percentile(vals,95):.3f}, "
              f"|max|={np.max(np.abs(vals)):.3f}")

    # --- top offending cells (for manual geographic inspection) ---
    flat = mean_map.stack(cell=("lat", "lon"))
    flat = flat.where(np.isfinite(flat), drop=True)
    order = np.argsort(np.abs(flat.values))[::-1][:15]
    print("\nTop 15 grid cells by |long-term mean residual| "
          "(cross-check against known irrigated/karst/mountain regions):")
    for i in order:
        cell = flat.isel(cell=i)
        lat = float(cell["lat"].values)
        lon = float(cell["lon"].values)
        val = float(cell.values)
        print(f"  lat={lat:7.3f}  lon={lon:8.3f}  residual={val:8.3f} mm/day")

    # --- plots ---
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        use_cartopy = False
        try:
            import cartopy.crs as ccrs
            import cartopy.feature as cfeature
            use_cartopy = True
        except ImportError:
            pass

        panels = [
            (mean_map, "Long-term mean residual (mm/day)", "RdBu_r"),
            (std_map, "Residual std across time (mm/day)", "viridis"),
            (seasonal_diff, "JJA minus DJF residual (mm/day)", "RdBu_r"),
        ]

        for field, title, cmap in panels:
            if use_cartopy:
                fig = plt.figure(figsize=(10, 5))
                ax = plt.axes(projection=ccrs.PlateCarree())
                ax.add_feature(cfeature.STATES, linewidth=0.3)
                ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
                vmax = float(np.nanpercentile(np.abs(field.values), 95))
                im = field.plot(ax=ax, transform=ccrs.PlateCarree(),
                                 cmap=cmap, vmin=-vmax if "RdBu" in cmap else None,
                                 vmax=vmax, add_colorbar=True)
            else:
                fig, ax = plt.subplots(figsize=(10, 5))
                vmax = float(np.nanpercentile(np.abs(field.values), 95))
                field.plot(ax=ax, cmap=cmap,
                           vmin=-vmax if "RdBu" in cmap else None, vmax=vmax)
            ax.set_title(f"{label}: {title}")
            fname = title.split("(")[0].strip().lower().replace(" ", "_")
            fig.tight_layout()
            fig.savefig(os.path.join(outdir, f"{label}_{fname}.png"), dpi=150)
            plt.close(fig)
            print(f"Saved plot -> {outdir}/{label}_{fname}.png")

        if not use_cartopy:
            print("(cartopy not available — plotted plain lat/lon grid, no "
                  "coastlines/state borders. `conda install cartopy` in your "
                  "env if you want those.)")
    except Exception as e:
        print(f"Plotting failed (non-fatal, NetCDF was still saved): {e}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="control",
                     help="Config (archive folder) to map (default: control)")
    ap.add_argument("--h0", help="Glob pattern for h0 history files "
                                 "(default: <archive>/<config>/lnd/hist/*.h0a.*.nc)")
    ap.add_argument("--outdir", help="default: <output root>/qc/<config>/spatial")
    ap.add_argument("--label",
                     help="Run label, used as output filename prefix "
                          "(default: the config name, so maps from different "
                          "runs don't overwrite each other)")
    ap.add_argument("--chunk-time", type=int, default=60)
    args = ap.parse_args()
    args.h0 = args.h0 or paths.lnd_hist(args.config) + "/*.h0a.*.nc"
    args.outdir = args.outdir or f"{paths.OUTPUT_ROOT}/qc/{args.config}/spatial"
    args.label = args.label or args.config

    import xarray as xr
    ds = open_h0(xr, args.h0, args.chunk_time)
    land_mask = get_land_mask(ds)
    residual = compute_residual_field(ds)
    make_residual_maps(residual, land_mask, args.outdir, args.label)

    print("\nDone. If any region jumps out (large |mean residual| or strong "
          "JJA-DJF asymmetry), worth checking against known geography before "
          "moving on — e.g. mountainous snow zones for melt-timing issues, "
          "Central Valley / irrigated cropland for a runoff/ET mismatch that "
          "your control (irrigation OFF) might legitimately have relative to "
          "reality, karst/groundwater-dominated basins where CTSM's subsurface "
          "representation is known to be weak.")


if __name__ == "__main__":
    main()
