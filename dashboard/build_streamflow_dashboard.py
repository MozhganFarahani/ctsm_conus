
#!/usr/bin/env python
"""
CTSM CONUS evaluation dashboard -- multi-configuration
======================================================
SIF-T FY26 (Farahani)

ONE self-contained HTML file comparing any number of CTSM configurations at
~2,300 streamflow gauges, with CTSM fields averaged over each gauge's
upstream contributing area.

Layout
------
  left    controls, map, wide monthly time series, comparison table
  right   six seasonal-climatology panels (3 rows x 2 cols)
            1  streamflow (fixed; the only panel with observations)
            2-6  selectable, defaulting to precipitation, SWE, ET,
                 soil moisture, runoff

The time series gets the wide space because 456 points need horizontal
extent; a 12-point climatology does not.

Design principles
-----------------
COLOUR ENCODES CONFIGURATION, PANEL ENCODES VARIABLE, observed is black.
One variable per panel means one unit per panel, so no dual axes anywhere.
The configuration checkboxes are the shared legend for all seven plots.

Difference mode switches every panel to (configuration - baseline) at once.
Precipitation then flattens to zero, which is a free check that the forcing
really is identical across configurations.

Inputs
------
For each config: h0a land history and mizuRoute history (<archive>/<config>),
finidat from the run folder (paths.RUN_ROOT). Shared: observed daily flow
(paths.OBS_DAILY), plus paths.OBS_MONTHLY for the 29 USBR_Colorado gauges
absent from the daily file (lib/io.py observed_monthly), gauge crosswalk (paths.CROSSWALK), augmented topology and
NLDAS-to-MERIT weights (paths.NTOPO, paths.WEIGHTS) via lib/basins.py, whose
weight matrices are cached in paths.UPSTREAM_CACHE.

Outputs
-------
<outdir>/<name>_dashboard.html, one self-contained file
(default outdir: paths.DASHBOARD_OUT, <output root>/dashboard).

Usage
-----
    module load conda && conda activate npl-2026a
    python build_streamflow_dashboard.py --configs control,irrigation_on --test-sample 8
The full build (all gauges, all configs) is run_dashboard.pbs.

The FIRST configuration listed is the default baseline for differences.

Initialization dates
--------------------
Each configuration's `finidat` is read from its run directory and shown in
the gauge header. These runs start from different spinup restarts, so early
differences can be initialization rather than process; the first
--spinup-years of the time series are shaded as a reminder.
"""

import argparse
import json
import os
import re
import sys
import warnings

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "analysis", "config"))
import paths  # analysis/config/paths.py
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "analysis"))
from lib import basins as ub  # analysis/lib/basins.py
from lib import io as lio       # analysis/lib/io.py
from lib import metrics         # analysis/lib/metrics.py
from dashboard_template import TEMPLATE

warnings.filterwarnings("ignore", category=FutureWarning, module="xarray")

DEFAULT_CROSSWALK = paths.CROSSWALK
DEFAULT_OBS_DAILY = paths.OBS_DAILY
DEFAULT_OBS_MONTHLY = paths.OBS_MONTHLY
DEFAULT_RUN_ROOT = paths.RUN_ROOT

CONFIG_COLORS = ["#4c78a8", "#f58518", "#54a24b", "#b279a2", "#e45756",
                 "#72b7b2", "#ff9da6", "#9d755d"]
CONFIG_LABELS = {"control": "Control",
                 "irrigation_on": "Irrigation",
                 "evolving_landcover": "Evolving land cover",
                 "hillslope_eval": "Hillslope",
                 "prog_phenology": "Prognostic phenology"}

# Panels 2-6; panel 1 is always streamflow.
DEFAULT_PANELS = ["PRECIP", "H2OSNO", "QFLX_EVAP_TOT", "SOILMOIST", "QRUNOFF"]


def sig(x, n=4):
    """Round to n significant digits; None if non-finite. Roughly halves the
    JSON versus full float repr with no visible change to any plot."""
    if x is None or not np.isfinite(x):
        return None
    return float(f"{float(x):.{n}g}")


def init_date(run_root, config):
    """Initialization date from the config's finidat, for the gauge header."""
    for p in (os.path.join(run_root, config, "run", "lnd_in"),
              os.path.join(run_root, config, "CaseDocs", "lnd_in")):
        if not os.path.isfile(p):
            continue
        try:
            with open(p) as f:
                for line in f:
                    m = re.match(r"\s*finidat\s*=\s*'([^']+)'", line)
                    if m:
                        d = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(m.group(1)))
                        return d.group(1) if d else os.path.basename(m.group(1))
        except OSError:
            pass
    return None


def usable_vars(ds, wanted):
    """Configured fields present in this stream AND shaped (time, lat, lon).

    Layered fields (levsoi) and anything else with extra dimensions are
    skipped here rather than silently mis-averaged, since basin_average
    assumes a 2-D spatial field.
    """
    ok, skipped = {}, []
    for v in wanted:
        if v not in ds.variables:
            continue
        d = tuple(ds[v].dims)
        if d == ("time", "lat", "lon"):
            ok[v] = ub.H0_VARS[v]
        else:
            skipped.append(f"{v}{d}")
    if skipped:
        print(f"    skipped (not time,lat,lon): {' '.join(skipped)}")
    return ok


# ------------------------------------------------------------ gauge subsets
def select_test_sample(df, n, area_col):
    key = area_col or "Longitude"
    d = df.copy()
    d["_k"] = pd.to_numeric(d[key], errors="coerce")
    d = d.dropna(subset=["_k"]).sort_values("_k")
    if len(d) <= n:
        return d.drop(columns="_k")
    return d.iloc[np.linspace(0, len(d) - 1, n).round().astype(int)].drop(columns="_k")


def print_selection(df, area_col):
    print(f"\nTesting {len(df)} gauge(s):")
    for _, r in df.iterrows():
        a = pd.to_numeric(r.get(area_col), errors="coerce") if area_col else None
        astr = f"{a:>10,.0f} km2" if a is not None and pd.notna(a) else "         ?"
        print(f"  {str(r['Station ID']):<12} {astr}  "
              f"({r['Latitude']:.2f}, {r['Longitude']:.2f})  "
              f"{str(r.get('Long_Name',''))[:40]}")
    print()


def build_html(payload, out_path):
    html = TEMPLATE.replace("__DATA_JSON__", json.dumps(payload))
    with open(out_path, "w") as f:
        f.write(html)


# -------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--archive-root", default=paths.ARCHIVE)
    ap.add_argument("--configs", required=True,
                    help="Comma-separated config names; the first is the "
                         "default baseline for differences")
    ap.add_argument("--run-root", default=DEFAULT_RUN_ROOT,
                    help="Where the case run directories live, for reading "
                         "each config's finidat (initialization date)")
    ap.add_argument("--crosswalk", default=DEFAULT_CROSSWALK)
    ap.add_argument("--obs-daily", default=DEFAULT_OBS_DAILY)
    ap.add_argument("--obs-monthly", default=DEFAULT_OBS_MONTHLY,
                    help="monthly obs, used for gauges absent from --obs-daily")
    ap.add_argument("--outdir", default=paths.DASHBOARD_OUT, help="default: %(default)s")
    ap.add_argument("--out-name", default=None)
    ap.add_argument("--vars", default=None,
                    help="Comma-separated h0 fields to average, or 'all'. "
                         "Default: lib/basins.py DEFAULT_VARS")
    ap.add_argument("--spinup-years", type=int, default=3,
                    help="Years shaded at the start of the time series as a "
                         "reminder that configs start from different "
                         "restarts (default 3; 0 disables)")
    ap.add_argument("--series-configs", default=None,
                    help="Configs to keep FULL monthly series for (default "
                         "all). Climatologies and metrics always kept.")
    ap.add_argument("--rof-shift", type=int, default=0)
    ap.add_argument("--test-basins", default=None)
    ap.add_argument("--test-sample", type=int, default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--check-mapping", action="store_true")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--parallel", action="store_true")
    args = ap.parse_args()

    configs = [c.strip() for c in args.configs.split(",") if c.strip()]
    ref = configs[0]
    keep_series = set(configs if not args.series_configs
                      else [c.strip() for c in args.series_configs.split(",")])
    os.makedirs(args.outdir, exist_ok=True)

    import xarray as xr
    if args.parallel:
        import dask
        # cpu_count() reports the whole node and ignores the PBS cgroup;
        # sched_getaffinity respects it. Cap dask so the real cores are not
        # oversubscribed.
        n = len(os.sched_getaffinity(0))
        dask.config.set(scheduler="threads", num_workers=n)
        print(f"--parallel: {n} CPU(s); dask capped to match.")

    h0_files = lambda c: lio.lnd_h0_files(args.archive_root, c)
    # evaluation period only (paths.py): drops spinup months left in an archive
    rof_files = lambda c: lio.eval_period_files(lio.rof_files(args.archive_root, c))

    # ---------------------------------------------------- gauges
    df = lio.read_crosswalk(args.crosswalk, dedupe=True)
    area_col = next((c for c in df.columns
                     if "area" in c.lower() or "sqkm" in c.lower()), None)
    print(f"Crosswalk: {len(df)} gauges;  configs: {configs}  (baseline = {ref})")

    if args.test_basins:
        want = {s.strip() for s in args.test_basins.split(",")}
        df = df[df["Station ID"].astype(str).isin(want)]
        if df.empty:
            sys.exit("No requested Station IDs found.")
        print_selection(df, area_col)
    elif args.test_sample:
        df = select_test_sample(df, args.test_sample, area_col)
        print_selection(df, area_col)
    elif args.limit:
        df = df.head(args.limit)

    # ---------------------------------------------------- weights (shared)
    first = next((c for c in configs if h0_files(c)), None)
    W = row_of = None
    if first:
        with xr.open_dataset(h0_files(first)[0]) as d0:
            glat = d0["lat"].values.astype(float)
            glon = d0["lon"].values.astype(float)
        print(f"h0 grid: {glat.size} x {glon.size} "
              f"({'ascending' if glat[1] > glat[0] else 'DESCENDING'} lat)")
        outlets = {r["Station ID"]: int(r["merit_reach_id"])
                   for _, r in df.iterrows() if pd.notna(r["merit_reach_id"])}
        W = ub.build_weights(outlets, glat, glon, use_cache=not args.no_cache)
        ub.summarize(W)
        row_of = {s: k for k, s in enumerate(W["ids"])}
        if args.check_mapping:
            print("\n--check-mapping: stopping before the heavy loads.")
            return
    else:
        print("WARNING: no h0 files for any config -- streamflow only.")
        if args.check_mapping:
            sys.exit("--check-mapping needs an h0 file.")

    # ---------------------------------------------------- observations
    print("Loading observed flow ...")
    gids = pd.to_numeric(df["GAGE_ID"], errors="coerce").dropna().astype(int).tolist()
    obs, obs_source = lio.observed_monthly(gids, args.obs_daily, args.obs_monthly)
    n_mon = sum(v == "monthly" for v in obs_source.values())
    print(f"  {len(obs_source) - n_mon} gauges from the daily file, {n_mon} from the monthly file")

    # ---------------------------------------------------- routed flow
    mod, have = {}, []
    reach_ids = df["merit_reach_id"].astype(int).tolist()
    for c in configs:
        rf = rof_files(c)
        if not rf:
            print(f"  !! no mizuRoute output for '{c}' -- skipping")
            continue
        print(f"Loading mizuRoute [{c}] ...")
        dsr, rid = lio.open_mizuroute(rf, ["RoutedRunoff"], parallel=args.parallel)
        mod[c] = lio.bulk_extract(dsr["RoutedRunoff"], rid, reach_ids,
                                  shift=args.rof_shift)
        have.append(c)
    if not have:
        sys.exit("No mizuRoute output found for any configuration.")
    configs = have
    if ref not in configs:
        ref = configs[0]
        print(f"  baseline falls back to '{ref}'")

    # Metrics use the months common to observations AND every configuration,
    # so configurations are scored on identical samples.
    common = obs.index
    for c in configs:
        common = common.intersection(mod[c].index)
    print(f"Common months across obs + {len(configs)} config(s): {len(common)}")

    # ---------------------------------------------------- basin means
    wanted = (list(ub.H0_VARS) if args.vars == "all"
              else [v.strip() for v in args.vars.split(",")] if args.vars
              else list(ub.DEFAULT_VARS))
    bclim, var_cfgs = {}, {}
    if W is not None:
        for c in configs:
            hf = h0_files(c)
            if not hf:
                print(f"  !! no h0 for '{c}' -- no basin means")
                continue
            print(f"Basin-averaging [{c}] ...")
            dsh = lio.open_land_hist(hf, wanted, parallel=args.parallel)
            vc = usable_vars(dsh, wanted)
            print(f"    {len(vc)}: {' '.join(vc)}")
            idx = lio.monthly_index(dsh["time"].values)
            cl = {}
            for v, cfg in vc.items():
                arr = ub.basin_average(W["A"], dsh, v, scale=cfg.get("scale", 1.0),
                                       offset=cfg.get("offset", 0.0))
                dd = pd.DataFrame(arr.T, index=idx, columns=W["ids"]).reindex(common)
                # reduce to (12, n_gauges) immediately to keep memory flat
                cl[v] = np.stack([dd[dd.index.month == m].mean().values
                                  for m in range(1, 13)])
                var_cfgs.setdefault(v, []).append(c)
                del arr, dd
            bclim[c] = cl
            dsh.close()

    # ---------------------------------------------------- assemble
    print("Assembling ...")
    months_axis = [str(p) for p in common]
    pos_of = {p: k for k, p in enumerate(common)}
    gauges, series = [], {}

    for _, row in df.iterrows():
        rid, sid = int(row["merit_reach_id"]), row["Station ID"]
        try:
            gid = int(row["GAGE_ID"])
        except (ValueError, TypeError):
            continue
        if gid not in obs.columns:
            continue
        cols = [c for c in configs if rid in mod[c].columns]
        if not cols:
            continue

        frame = pd.DataFrame({"o": obs.loc[common, gid]})
        for c in cols:
            frame[c] = mod[c].loc[common, rid]
        frame = frame.dropna()
        if len(frame) < metrics.MIN_MONTHS:
            continue

        o = frame["o"]
        # all configs of this gauge at once, on the same months (lib/metrics.py
        # returns NaN where the observed record cannot support a metric)
        sk = metrics.nse_kge_pbias(np.repeat(o.values[:, None], len(cols), axis=1),
                                   frame[cols].values)
        m_out, s_out, sc_out = {}, {}, {}
        for j, c in enumerate(cols):
            s = frame[c]
            nse, kge, pb = sk["nse"][j], sk["kge"][j], sk["pbias"][j]
            if not np.isfinite(nse) or abs(nse) > 50:
                nse = max(-50, min(1, nse)) if np.isfinite(nse) else -50
            # KGE is unbounded below; clamp it the same way as NSE so one bad
            # gauge cannot dominate a colour range or a summary.
            if np.isfinite(kge) and kge < -50:
                kge = -50.0
            m_out[c] = {"nse": sig(nse), "kge": sig(kge), "pbias": sig(pb),
                        "q": sig(s.mean()), "n": int(len(frame))}
            if c in keep_series:
                s_out[c] = [sig(x) for x in s.values]
            sc_out[c] = [sig(s[s.index.month == m].mean()) for m in range(1, 13)]

        k = row_of.get(sid) if row_of else None
        b_out = {}
        if k is not None:
            for c in bclim:
                d = {v: [sig(x) for x in bclim[c][v][:, k]] for v in bclim[c]}
                for name, spec in ub.DERIVED.items():
                    if all(p in d for p, _ in spec["parts"]):
                        d[name] = [
                            None if any(d[p][m] is None for p, _ in spec["parts"])
                            else sig(sum(sgn * d[p][m] for p, sgn in spec["parts"]))
                            for m in range(12)]
                b_out[c] = d

        gauges.append({
            # 15 crosswalk rows have no Long_Name (NaN): use the Station ID instead
            "id": sid, "name": row["Long_Name"] if pd.notna(row.get("Long_Name")) else str(sid),
            "lat": float(row["Latitude"]), "lon": float(row["Longitude"]),
            "area_km2": round(float(W["area_km2"][k]), 1) if k is not None else 0.0,
            "n_hru": int(W["n_hru"][k]) if k is not None else 0,
            "n_cells": int(W["n_cells"][k]) if k is not None else 0,
            "bbox": [round(float(x), 3) for x in W["bbox"][k]] if k is not None else None,
            "area_err": round(float(W["area_err"][k]), 5)
                        if k is not None and np.isfinite(W["area_err"][k]) else None,
            "m": m_out, "b": b_out or None,
        })
        series[sid] = {
            "mi": [pos_of[p] for p in frame.index],
            "obs": [sig(x) for x in o.values],
            "sim": s_out,
            "obs_clim": [sig(o[o.index.month == m].mean()) for m in range(1, 13)],
            "sim_clim": sc_out,
        }

    # variable menu: derived first, then raw, each tagged with the configs
    # that have it so a config-specific field is obviously config-specific
    vars_meta = []
    for name, spec in ub.DERIVED.items():
        who = [c for c in configs
               if c in bclim and all(p in bclim[c] for p, _ in spec["parts"])]
        if who:
            vars_meta.append({"key": name, "label": spec["label"],
                              "unit": spec["unit"], "cfgs": who})
    for v, who in sorted(var_cfgs.items(),
                         key=lambda kv: ub.H0_VARS[kv[0]]["label"]):
        vars_meta.append({"key": v, "label": ub.H0_VARS[v]["label"],
                          "unit": ub.H0_VARS[v]["unit"], "cfgs": who})

    cfg_meta = [{"key": c,
                 "label": CONFIG_LABELS.get(c, c.replace("_", " ").title()),
                 "color": CONFIG_COLORS[i % len(CONFIG_COLORS)],
                 "init": init_date(args.run_root, c)}
                for i, c in enumerate(configs)]

    inits = {m["init"] for m in cfg_meta if m["init"]}
    print(f"\n{len(gauges)} gauges | {len(configs)} configs | "
          f"{len(vars_meta)} variables | {len(months_axis)} months")
    for m in cfg_meta:
        print(f"  {m['label']:<24} init {m['init'] or 'unknown'}")
    if len(inits) > 1:
        print("  NOTE: configurations start from different restarts; the "
              "first years of the\n  time series are shaded in the dashboard.")

    panels = [p for p in DEFAULT_PANELS
              if any(p == v["key"] for v in vars_meta)]
    while len(panels) < 5 and len(panels) < len(vars_meta):
        for v in vars_meta:
            if v["key"] not in panels:
                panels.append(v["key"])
                break

    name = args.out_name or (f"{ref}_plus{len(configs)-1}" if len(configs) > 1
                             else ref)
    tag = "_test" if (args.test_basins or args.test_sample) else ""
    out = os.path.join(args.outdir, f"{name}{tag}_dashboard.html")
    build_html({"configs": cfg_meta, "ref": ref, "vars": vars_meta,
                "panels": panels, "months": months_axis,
                "spinup_years": args.spinup_years,
                "stable_min_months": metrics.STABLE_MIN_MONTHS,
                "gauges": gauges, "series": series}, out)
    mb = os.path.getsize(out) / 1e6
    print(f"Saved -> {out} ({mb:.1f} MB)")
    if mb > 45:
        print("  Large. Options: --series-configs for fewer full monthly "
              "series,\n  --vars for fewer fields, or gzip on the web server "
              "(~5x).")


if __name__ == "__main__":
    main()
