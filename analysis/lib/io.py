"""Reading model output, observations and the gauge crosswalk; monthly time alignment.

Shared by the streamflow evaluation, the dashboard builder, the diagnostics and the
spinup checks. Code extracted from those scripts (Step 1 of the finalization pass).

Import it as part of the lib package, with analysis/ on sys.path:
    from lib import io as lio
Do not put analysis/lib itself on sys.path: this file would then shadow the stdlib io.
"""

import glob
import os
import re
import sys

import numpy as np
import pandas as pd
import xarray as xr

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config"))
from paths import EVAL_START, EVAL_END  # evaluation period, set in analysis/config/paths.py


# ---------------------------------------------------------------- file lists
def lnd_h0_files(archive_root, case):
    """Monthly CTSM history files (h0a) of a case, sorted."""
    return sorted(glob.glob(os.path.join(archive_root, case, "lnd", "hist", "*.h0a.*.nc")))


def rof_files(archive_root, case):
    """Monthly mizuRoute history files of a case, sorted."""
    return sorted(glob.glob(os.path.join(archive_root, case, "rof", "hist", "*.nc")))


_MONTH_RE = re.compile(r"\.(\d{4})-(\d{2})\.nc$")


def hist_file_month(path):
    """'YYYY-MM' from a monthly history file name (<case>.<...>.YYYY-MM.nc), else None."""
    m = _MONTH_RE.search(os.path.basename(path))
    return f"{m.group(1)}-{m.group(2)}" if m else None


def eval_period_files(files):
    """Monthly history files whose YYYY-MM lies in EVAL_START..EVAL_END.
    Drops spinup months left in an archive (irrigation_on holds 1980-01..09)."""
    first, last = EVAL_START[:7], EVAL_END[:7]
    return [f for f in files if first <= (hist_file_month(f) or "") <= last]


# ---------------------------------------------------------------- opening
def open_land_hist(files, varnames, parallel=False):
    """Open CTSM history files along time, keeping only the listed variables that exist.
    Static fields (landfrac, area) still carry a time dim: use isel(time=0)."""
    return xr.open_mfdataset(files, combine="nested", concat_dim="time",
                             decode_times=True, engine="netcdf4",
                             parallel=parallel, data_vars="all",
                             preprocess=lambda d: d[[v for v in varnames
                                                     if v in d.variables]])


def open_mizuroute(files, varnames, id_var="reachID", parallel=False):
    """Open mizuRoute history files along time. Returns (ds, ids): ids (reachID or
    basinID) carry a spurious time dim, so they are read from the first record."""
    keep = list(varnames) + [id_var]
    ds = xr.open_mfdataset(files, combine="nested", concat_dim="time",
                           decode_times=True, engine="netcdf4",
                           parallel=parallel, data_vars="all",
                           preprocess=lambda d: d[[v for v in keep if v in d.variables]])
    ids = list(ds[id_var].isel(time=0).compute().values.astype(int))
    return ds, ids


def open_obs_daily(path):
    """Naoki's daily multi-agency flow file. Returns (ds, flow_var, site ids)."""
    ds = xr.open_dataset(path, decode_times=True, engine="netcdf4")
    fv = next((v for v in ds.data_vars
               if v.lower() in ("streamflow", "flow", "discharge", "q")),
              next(v for v in ds.data_vars if "site" in ds[v].dims))
    return ds, fv, list(ds["site"].values.astype(int))


def read_crosswalk(path, dedupe=False, **read_csv_kw):
    """Gauge metadata with merit_reach_id (flow_multi_agency_all_meta.csv).
    dedupe=True keeps the first row of any duplicated Station ID."""
    df = pd.read_csv(path, **read_csv_kw)
    if dedupe:
        dup = int(df["Station ID"].duplicated().sum())
        if dup:
            print(f"NOTE: {dup} duplicate Station ID row(s); keeping the first.")
            df = df.drop_duplicates(subset="Station ID", keep="first")
    return df


def domain_mean(da, ds):
    """Mean of da over all non-time dims, weighted by ds's landfrac (else area);
    unweighted if neither is present. From qc/ctsm_control_explore.py."""
    weight = None
    for wname in ["landfrac", "area"]:
        if wname in ds:
            weight = ds[wname]
            break
    spatial_dims = [d for d in da.dims if d != "time"]
    if weight is not None:
        # static fields carry a time dim; without isel(time=0), weight.sum()
        # would also collapse time and corrupt the weighted mean.
        if "time" in weight.dims:
            weight = weight.isel(time=0)
        return (da * weight).sum(dim=spatial_dims) / weight.sum(dim=spatial_dims)
    return da.mean(dim=spatial_dims)


# ---------------------------------------------------------------- time alignment
def monthly_index(tv):
    """Monthly PeriodIndex from year and month. mizuRoute stamps day 16, obs are
    month-start, and model time is cftime DatetimeNoLeap, which pd.to_datetime
    cannot convert; year/month alignment works for all of them."""
    if isinstance(tv[0], np.datetime64):
        return pd.PeriodIndex(pd.to_datetime(tv), freq="M")
    return pd.PeriodIndex([f"{t.year}-{t.month:02d}" for t in tv], freq="M")


def bulk_extract(da, ids_present, wanted_ids, resample=None, shift=0):
    """One indexed read for all wanted_ids at once, as a DataFrame on a monthly
    PeriodIndex. `da` has a 'seg' dim (positions = ids_present, mizuRoute) or a
    'site' dim (labels, obs). resample="MS" turns daily obs into monthly means
    (obs calendar is standard, so pd.to_datetime is fine there). shift moves the
    index by whole months."""
    dim = "seg" if "seg" in da.dims else "site"
    # position of each id (first occurrence, as list.index); a dict avoids
    # scanning the 227k-reach list once per gauge
    pos = {}
    for k, i in enumerate(ids_present):
        pos.setdefault(i, k)
    valid = [i for i in wanted_ids if i in pos]
    if not valid:
        return pd.DataFrame()
    # The obs file stores flow(time, site) contiguously: selecting a list of
    # sites from disk reads them one by one (~1.5 s per site, ~1 h for all
    # gauges). Loading the time slice first (~1 s, 0.26 GB) and selecting in
    # memory gives the same values.
    sub = da.load().sel({dim: valid}) if dim == "site" else \
          da.isel({dim: [pos[i] for i in valid]}).compute()
    tv = sub["time"].values
    if resample:
        df = pd.DataFrame(sub.values, index=pd.to_datetime(tv),
                          columns=valid).resample(resample).mean()
        df.index = pd.PeriodIndex(df.index, freq="M")
    else:
        df = pd.DataFrame(sub.values, index=monthly_index(tv), columns=valid)
    if shift:
        df.index = df.index + shift
    return df
