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

import numpy as np
import pandas as pd
import xarray as xr

# Evaluation period: Oct 1980 - Sep 2018 (456 months).
EVAL_START, EVAL_END = "1980-10-01", "2018-09-30"


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
    valid = [i for i in wanted_ids if i in ids_present]
    if not valid:
        return pd.DataFrame()
    sub = da.sel({dim: valid}).compute() if dim == "site" else \
          da.isel({dim: [ids_present.index(i) for i in valid]}).compute()
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
