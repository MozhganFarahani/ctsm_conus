#!/usr/bin/env python
"""Find the month offset between CTSM h0 and mizuRoute history records.
   python check_time_align.py 09040000 
   python check_time_align.py 09081600


basRunoff must equal remapped QRUNOFF for the SAME period. If mizuRoute
stamps a record at the end of its averaging window (or the file name refers
to a different month than the record), the two series are shifted and the
apparent error is largest where the seasonal cycle is sharpest -- which is
exactly the pattern across Troublesome / Umpqua / Hermann.

Builds both monthly series from their own timestamps and reports agreement
at lags -2..+2 months. The lag with ratio ~1 and the highest correlation is
the true alignment.
"""
import sys, glob, os
import numpy as np, pandas as pd, xarray as xr

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config"))
import paths  # analysis/config/paths.py

GAUGE = sys.argv[1]
NTOPO   = paths.NTOPO
WEIGHTS = paths.WEIGHTS
XW      = paths.CROSSWALK
ARCH    = paths.ARCHIVE
CONFIG  = "control"


def pidx(tv):
    if isinstance(tv[0], np.datetime64):
        return pd.PeriodIndex(pd.to_datetime(tv), freq="M")
    return pd.PeriodIndex([f"{t.year}-{t.month:02d}" for t in tv], freq="M")


g = pd.read_csv(XW, dtype={"Station ID": str}).query("`Station ID` == @GAUGE").iloc[0]
reach = int(g.merit_reach_id)
print(f"{g.Long_Name}  reach={reach}")

# ---- upstream HRUs
nt = xr.open_dataset(NTOPO)
sp_ = int(np.nonzero(nt.seg_id.values == reach)[0][0])
s = int(nt.upAll_start.values[sp_]) - 1
c = int(nt.upAll_count.values[sp_])
up = np.unique(np.append(
    nt.allUpSegIndices.isel(upAll=slice(s, s + c)).values.astype(int) - 1, sp_))
hp = np.nonzero(np.isin(nt.hruSegIndex.values.astype(int) - 1, up))[0]
hid, area = nt.hruid.values.astype(int), nt.Basin_Area.values
print(f"  {hp.size} HRUs, {area[hp].sum()/1e6:,.1f} km2")

# ---- h0: remap QRUNOFF to these HRUs, area-weight
h0f = sorted(glob.glob(f"{ARCH}/{CONFIG}/lnd/hist/*.h0a.*.nc"))
ds = xr.open_mfdataset(h0f, combine="nested", concat_dim="time",
                       engine="netcdf4", data_vars="all",
                       preprocess=lambda d: d[["QRUNOFF"]])
nlat, nlon = ds.lat.size, ds.lon.size
sw = xr.open_dataset(WEIGHTS).load()
ov = sw.overlaps.values.astype(int)
hrec = np.repeat(np.arange(ov.size), ov)
w = sw.weight.values
flat = ((sw.j_index.values.astype(int) - 1) * nlon
        + (sw.i_index.values.astype(int) - 1))
sel = np.isin(hrec, np.nonzero(np.isin(sw.polyid.values.astype(int), hid[hp]))[0])
a_of = dict(zip(hid[hp], area[hp]))
arec = np.array([a_of[k] for k in sw.polyid.values.astype(int)[hrec[sel]]])
cells, inv = np.unique(flat[sel], return_inverse=True)
wts = np.bincount(inv, weights=arec * w[sel]); wts /= wts.sum()
fld = np.nan_to_num(ds.QRUNOFF.values.reshape(ds.time.size, -1)[:, cells])
q = pd.Series((fld * wts).sum(1) * 86400., index=pidx(ds.time.values))

# ---- rof: basRunoff for the same HRUs
rf = sorted(glob.glob(f"{ARCH}/{CONFIG}/rof/hist/*.nc"))
dr = xr.open_mfdataset(rf, combine="nested", concat_dim="time",
                       engine="netcdf4", data_vars="all",
                       preprocess=lambda d: d[["basRunoff", "basinID"]])
bid = dr.basinID.isel(time=0).values.astype(int)
loc = {b: k for k, b in enumerate(bid)}
ix = np.array([loc[h] for h in hid[hp] if h in loc])
aa = np.array([a_of[h] for h in hid[hp] if h in loc])
brv = dr.basRunoff.isel({dr.basRunoff.dims[-1]: ix}).values
b = pd.Series((brv * aa).sum(1) / aa.sum() * 86400., index=pidx(dr.time.values))

print(f"\n  h0  first stamps: {[str(x) for x in ds.time.values[:3]]}")
print(f"  rof first stamps: {[str(x) for x in dr.time.values[:3]]}")
print(f"  h0  periods {q.index[0]}..{q.index[-1]} ({len(q)})")
print(f"  rof periods {b.index[0]}..{b.index[-1]} ({len(b)})")

print(f"\n  lag = months the rof series is shifted to match h0")
print(f"  {'lag':>4} {'n':>5} {'mean QRUNOFF':>13} {'mean basRunoff':>15} "
      f"{'ratio':>8} {'corr':>7}")
best = None
for lag in (-2, -1, 0, 1, 2):
    bs = b.copy()
    bs.index = bs.index + lag
    j = q.index.intersection(bs.index)
    if len(j) < 12:
        continue
    qq, bb = q.reindex(j), bs.reindex(j)
    ratio = qq.mean() / bb.mean() if bb.mean() else np.nan
    corr = qq.corr(bb)
    print(f"  {lag:>4} {len(j):5d} {qq.mean():13.4f} {bb.mean():15.4f} "
          f"{ratio:8.3f} {corr:7.4f}")
    # correlation discriminates; the ratio can be ~1 at every lag when the
    # series is merely shifted rather than scaled
    if best is None or (np.isfinite(corr) and corr > best[0]):
        best = (corr, lag, ratio, corr)

print(f"\n  best alignment: lag {best[1]:+d}  (corr {best[3]:.4f}, "
      f"ratio {best[2]:.3f})")
if best[1] == 0:
    print("  -> already aligned; the gap is NOT a timestamp offset")
else:
    print(f"  -> mizuRoute records are offset by {best[1]:+d} month(s) from "
          f"the h0 records\n     with the same nominal timestamp. Every "
          f"comparison so far has been\n     off by that much.")
