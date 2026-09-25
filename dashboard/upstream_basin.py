#!/usr/bin/env python
"""
Upstream-basin averaging of CTSM fields per gauge (Naoki's mapping)
===================================================================
SIF-T FY26 (Farahani)

    build_weights()   slow, run once -> cached .npz.  Depends only on the
                      topology and the gauge set, so all five configurations
                      reuse one cache.
    basin_average()   sparse matmul, per config / per variable

Method
------
Upstream segments come from the AUGMENTED topology's precomputed ragged
arrays (`allUpSegIndices` with `upAll_start`/`upAll_count`), so there is no
network traversal, and `totalArea(seg)` gives an authoritative area to check
each gauge against.

HRU -> grid weights come from the spatialweights file, using the same
convention as Naoki's remap: records are contiguous in `polyid` order via
`cumsum(overlaps)`, `weight` is the fraction of the HRU polygon covered by
each cell, normalized per HRU so each row sums to 1, and `i_index`/`j_index`
are one-based from the LL corner (so `j-1` indexes an ascending lat axis
directly).

This reproduces Naoki's reference implementation to four decimal places, and
independently agrees with the coupler's own lnd2rof ESMF weights.

Adding a variable
-----------------
Add an entry to H0_VARS. It is averaged, stored, and offered in the
dashboard's variable picker automatically.
"""

import hashlib
import os
import sys
from pathlib import Path

import numpy as np
import scipy.sparse as sp
import xarray as xr

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "analysis", "config"))
import paths  # analysis/config/paths.py

# Each can be overridden with an environment variable of the same name.
CACHE_DIR = Path(os.environ.get("CACHE_DIR", paths.UPSTREAM_CACHE))
NTOPO = os.environ.get("NTOPO", paths.NTOPO)
WEIGHTS = os.environ.get("WEIGHTS", paths.WEIGHTS)

AREA_TOL = 0.02          # traversed vs totalArea agreement required

# CTSM h0 fields available for basin averaging.
#   scale   multiply the raw field by this
#   offset  added after scaling (K -> degC)
#   unit    axis label; one variable per panel, so units never mix
# Layered fields (SOILLIQ, SOILICE, TSOI, H2OSOI) are deliberately absent:
# basin_average assumes (time, lat, lon). Column totals TOTSOILLIQ/TOTSOILICE
# cover the soil-water case. Anything whose dims are not (time, lat, lon) is
# skipped at run time with a message, so listing one here is harmless.
MMDAY = 86400.0          # kg/m2/s -> mm/day
GCDAY = 86400.0          # gC/m2/s -> gC/m2/day

H0_VARS = {
    # --- water fluxes -------------------------------------------------
    "RAIN":            dict(label="Rain",              scale=MMDAY, unit="mm/day"),
    "SNOW":            dict(label="Snowfall",          scale=MMDAY, unit="mm/day"),
    "QRUNOFF":         dict(label="Total runoff",      scale=MMDAY, unit="mm/day"),
    "QOVER":           dict(label="Surface runoff",    scale=MMDAY, unit="mm/day"),
    "QDRAI":           dict(label="Drainage",          scale=MMDAY, unit="mm/day"),
    "QDRAI_PERCH":     dict(label="Perched drainage",  scale=MMDAY, unit="mm/day"),
    "QH2OSFC":         dict(label="Surface water runoff", scale=MMDAY, unit="mm/day"),
    "QFLX_EVAP_TOT":   dict(label="ET",                scale=MMDAY, unit="mm/day"),
    "QSOIL":           dict(label="Soil evaporation",  scale=MMDAY, unit="mm/day"),
    "QVEGE":           dict(label="Canopy evaporation", scale=MMDAY, unit="mm/day"),
    "QVEGT":           dict(label="Transpiration",     scale=MMDAY, unit="mm/day"),
    "QFLX_SNOW_DRAIN": dict(label="Snowmelt drainage", scale=MMDAY, unit="mm/day"),
    # --- storage ------------------------------------------------------
    "H2OSNO":          dict(label="SWE",               scale=1.0, unit="mm"),
    "H2OSFC":          dict(label="Surface water",     scale=1.0, unit="mm"),
    "TOTSOILLIQ":      dict(label="Soil liquid (column)", scale=1.0, unit="mm"),
    "TOTSOILICE":      dict(label="Soil ice (column)", scale=1.0, unit="mm"),
    "TWS":             dict(label="Total water storage", scale=1.0, unit="mm"),
    # --- depths -------------------------------------------------------
    "SNOWDP":          dict(label="Snow depth",        scale=1.0, unit="m"),
    "ZWT":             dict(label="Water table depth", scale=1.0, unit="m"),
    "ZWT_PERCH":       dict(label="Perched water table", scale=1.0, unit="m"),
    "FROST_TABLE":     dict(label="Frost table depth", scale=1.0, unit="m"),
    "ALT":             dict(label="Active layer thickness", scale=1.0, unit="m"),
    # --- energy -------------------------------------------------------
    "EFLX_LH_TOT":     dict(label="Latent heat flux",  scale=1.0, unit="W/m2"),
    "FSH":             dict(label="Sensible heat flux", scale=1.0, unit="W/m2"),
    "FIRA":            dict(label="Net longwave",      scale=1.0, unit="W/m2"),
    "FSDS":            dict(label="Incident shortwave", scale=1.0, unit="W/m2"),
    "EFLX_SOIL_GRND":  dict(label="Ground heat flux",  scale=1.0, unit="W/m2"),
    # --- temperatures -------------------------------------------------
    "TSA":             dict(label="2 m air temp",      scale=1.0, offset=-273.15, unit="degC"),
    "TBOT":            dict(label="Forcing air temp",  scale=1.0, offset=-273.15, unit="degC"),
    "TG":              dict(label="Ground temp",       scale=1.0, offset=-273.15, unit="degC"),
    "TV":              dict(label="Vegetation temp",   scale=1.0, offset=-273.15, unit="degC"),
    "TSKIN":           dict(label="Skin temp",         scale=1.0, offset=-273.15, unit="degC"),
    # --- vegetation / surface ----------------------------------------
    "TLAI":            dict(label="Leaf area index",   scale=1.0, unit="m2/m2"),
    "FSNO":            dict(label="Snow cover fraction", scale=1.0, unit="-"),
    "FH2OSFC":         dict(label="Surface water fraction", scale=1.0, unit="-"),
    "BTRANMN":         dict(label="Soil moisture stress", scale=1.0, unit="-"),
    "FPSN":            dict(label="Photosynthesis",    scale=1.0, unit="umol/m2/s"),
    # --- irrigation (irrigation_on only) ------------------------------
    "QIRRIG_DEMAND":            dict(label="Irrigation demand", scale=MMDAY, unit="mm/day"),
    "QIRRIG_FROM_SURFACE":      dict(label="Irrigation from surface", scale=MMDAY, unit="mm/day"),
    "QIRRIG_FROM_GW_UNCONFINED": dict(label="Irrigation from unconfined GW", scale=MMDAY, unit="mm/day"),
    "QIRRIG_FROM_GW_CONFINED":  dict(label="Irrigation from confined GW", scale=MMDAY, unit="mm/day"),
    "QIRRIG_DRIP":              dict(label="Irrigation, drip", scale=MMDAY, unit="mm/day"),
    "QIRRIG_SPRINKLER":         dict(label="Irrigation, sprinkler", scale=MMDAY, unit="mm/day"),
    # --- hillslope only ----------------------------------------------
    "QLATFLOWOUT":     dict(label="Lateral subsurface outflow", scale=MMDAY, unit="mm/day"),
    # --- BGC / prognostic phenology only ------------------------------
    "GPP":             dict(label="GPP",  scale=GCDAY, unit="gC/m2/day"),
    "NPP":             dict(label="NPP",  scale=GCDAY, unit="gC/m2/day"),
    "NEE":             dict(label="NEE",  scale=GCDAY, unit="gC/m2/day"),
    "AR":              dict(label="Autotrophic respiration", scale=GCDAY, unit="gC/m2/day"),
    "HR":              dict(label="Heterotrophic respiration", scale=GCDAY, unit="gC/m2/day"),
    "TOTVEGC":         dict(label="Vegetation carbon", scale=1.0, unit="gC/m2"),
    "TOTSOMC":         dict(label="Soil organic matter C", scale=1.0, unit="gC/m2"),
    "TOTECOSYSC":      dict(label="Ecosystem carbon", scale=1.0, unit="gC/m2"),
}

# Computed in the dashboard from fields above. `parts` are (var, sign).
DERIVED = {
    "PRECIP":    dict(label="Precipitation", unit="mm/day",
                      parts=(("RAIN", +1), ("SNOW", +1))),
    "SOILMOIST": dict(label="Soil moisture (column)", unit="mm",
                      parts=(("TOTSOILLIQ", +1), ("TOTSOILICE", +1))),
    "WBAL":      dict(label="P \u2212 ET \u2212 runoff", unit="mm/day",
                      parts=(("RAIN", +1), ("SNOW", +1),
                             ("QFLX_EVAP_TOT", -1), ("QRUNOFF", -1))),
}

# Averaged unless --vars overrides. Keeps the payload to a sensible size while
# covering the six default panels plus the obvious follow-ups; config-specific
# fields are appended automatically when a configuration has them.
DEFAULT_VARS = [
    "RAIN", "SNOW", "QRUNOFF", "QOVER", "QDRAI", "QFLX_EVAP_TOT", "QVEGT",
    "QSOIL", "H2OSNO", "SNOWDP", "TOTSOILLIQ", "TOTSOILICE", "TWS", "ZWT",
    "EFLX_LH_TOT", "FSH", "TSA", "TLAI", "FSNO",
    "QIRRIG_DEMAND", "QIRRIG_FROM_SURFACE", "QIRRIG_FROM_GW_UNCONFINED",
    "QIRRIG_FROM_GW_CONFINED", "QLATFLOWOUT",
    "GPP", "NPP", "NEE", "TOTVEGC",
]

# ------------------------------------------------------------------ topology
def open_topo(path=None, verbose=True):
    """Load the augmented topology arrays needed for upstream lookups."""
    path = path or NTOPO
    if verbose:
        print(f"Reading topology <- {path}")
    nt = xr.open_dataset(path)
    need = ["seg_id", "hruid", "hruSegIndex", "Basin_Area",
            "upAll_start", "upAll_count", "allUpSegIndices", "totalArea"]
    missing = [v for v in need if v not in nt.variables]
    if missing:
        raise KeyError(f"{path} is missing {missing}. This must be the "
                       f"AUGMENTED topology (ntopo_*_aug.nc).")
    return {v: nt[v].values for v in need}


def _hrus_by_seg(topo):
    """Ragged grouping of HRU positions by segment position, built once."""
    seg_pos = topo["hruSegIndex"].astype(np.int64) - 1     # 1-based -> 0-based
    order = np.argsort(seg_pos, kind="stable")
    sorted_seg = seg_pos[order]
    starts = np.searchsorted(sorted_seg, np.arange(topo["seg_id"].size),
                             side="left")
    ends = np.searchsorted(sorted_seg, np.arange(topo["seg_id"].size),
                           side="right")
    return order, starts, ends


def upstream_hrus(topo, grouping, seg_pos):
    """HRU positions draining to one segment position (itself included)."""
    order, starts, ends = grouping
    s = int(topo["upAll_start"][seg_pos]) - 1        # 1-based ragged offset
    c = int(topo["upAll_count"][seg_pos])
    up = topo["allUpSegIndices"][s:s + c].astype(np.int64) - 1
    up = np.append(up, seg_pos)
    up = np.unique(up[(up >= 0) & (up < topo["seg_id"].size)])
    return np.concatenate([order[starts[p]:ends[p]] for p in up]) \
        if up.size else np.array([], dtype=np.int64)


# ------------------------------------------------------------- grid weights
def hru_to_grid(hru_ids, nlat, nlon, path=None, verbose=True):
    """Sparse (n_hru, nlat*nlon) with each row summing to 1.

    Row k corresponds to hru_ids[k] (topology order). Uses the contiguous
    cumsum(overlaps) convention, as Naoki's subset_mapping does.
    """
    path = path or WEIGHTS
    if verbose:
        print(f"Reading spatial weights <- {path}")
    sw = xr.open_dataset(path)
    poly = sw["polyid"].values.astype(np.int64)
    ov = sw["overlaps"].values.astype(np.int64)
    w = sw["weight"].values.astype(np.float64)
    ii = sw["i_index"].values
    jj = sw["j_index"].values

    if w.size != ov.sum():
        raise ValueError(
            f"data dim ({w.size}) != sum of overlaps ({ov.sum()}); the "
            f"records are not contiguous and this convention does not hold")

    rec_poly = np.repeat(poly, ov)                  # polyid owning each record
    ok = np.isfinite(w) & np.isfinite(ii) & np.isfinite(jj) & (w > 0)
    flat = np.full(w.size, -1, dtype=np.int64)
    flat[ok] = ((jj[ok].astype(np.int64) - 1) * nlon
                + (ii[ok].astype(np.int64) - 1))     # 1-based from LL corner
    ok &= (flat >= 0) & (flat < nlat * nlon)

    pos_of = {p: k for k, p in enumerate(hru_ids)}
    rows = np.array([pos_of.get(p, -1) for p in rec_poly])
    ok &= rows >= 0

    G = sp.csr_matrix((w[ok], (rows[ok], flat[ok])),
                      shape=(hru_ids.size, nlat * nlon))
    rs = np.asarray(G.sum(axis=1)).ravel()
    inv = np.where(rs > 0, 1.0 / np.maximum(rs, 1e-300), 0.0)
    if verbose:
        print(f"  {int(ok.sum()):,} weights, {(rs > 0).sum():,} of "
              f"{hru_ids.size:,} HRUs covered; row sums before normalizing: "
              f"min {rs[rs > 0].min():.4f} max {rs.max():.4f}")
    return (sp.diags(inv) @ G).tocsr(), rs


# ------------------------------------------------------------------ weights
def _fingerprint(gauge_outlets, nlat, nlon):
    items = ";".join(f"{k}:{v}" for k, v in sorted(gauge_outlets.items(),
                                                   key=lambda kv: str(kv[0])))
    h = hashlib.md5((items + f"|{NTOPO}|{WEIGHTS}").encode()).hexdigest()[:10]
    return f"naoki_{nlat}x{nlon}_n{len(gauge_outlets)}_{h}"


def build_weights(gauge_outlets, glat, glon, use_cache=True, verbose=True):
    """
    gauge_outlets : {station_id -> outlet reach id (seg_id)}
    glat, glon    : 1-D h0 coordinate arrays (lat must ascend)

    Returns dict:
      A         csr (n_gauges, nlat*nlon) float32, rows sum to 1
      ids       station_ids in row order
      area_km2  upstream contributing area
      n_hru     upstream HRU count
      n_cells   contributing grid cells
      bbox      (n_gauges, 4) lat_min, lat_max, lon_min, lon_max of the cells
      area_err  (traversed - totalArea) / totalArea
    """
    nlat, nlon = glat.size, glon.size
    if glat[1] <= glat[0]:
        raise ValueError("h0 lat must ascend: j_index counts from the LL "
                         "corner, so a descending axis would mirror every "
                         "basin north-south")

    tag = _fingerprint(gauge_outlets, nlat, nlon)
    mpath = CACHE_DIR / f"{tag}.matrix.npz"
    kpath = CACHE_DIR / f"{tag}.meta.npz"
    if use_cache and mpath.exists() and kpath.exists():
        if verbose:
            print(f"Loading cached weights <- {mpath.name}")
        m = np.load(kpath, allow_pickle=True)
        return {"A": sp.load_npz(mpath), "ids": list(m["ids"]),
                "area_km2": m["area_km2"], "n_hru": m["n_hru"],
                "n_cells": m["n_cells"], "bbox": m["bbox"],
                "area_err": m["area_err"]}

    topo = open_topo(verbose=verbose)
    grouping = _hrus_by_seg(topo)
    seg_id = topo["seg_id"].astype(np.int64)
    hru_ids = topo["hruid"].astype(np.int64)
    area = topo["Basin_Area"].astype(np.float64)
    pos_of_seg = {s: k for k, s in enumerate(seg_id)}

    G, _ = hru_to_grid(hru_ids, nlat, nlon, verbose=verbose)

    if verbose:
        print(f"Collecting upstream HRUs for {len(gauge_outlets)} gauge(s) ...")
    rows, cols, vals, ids, aerr, nhru = [], [], [], [], [], []
    n_miss = n_bad = 0
    for sid, reach in sorted(gauge_outlets.items(), key=lambda kv: str(kv[0])):
        sp_ = pos_of_seg.get(int(reach))
        if sp_ is None:
            n_miss += 1
            continue
        hp = upstream_hrus(topo, grouping, sp_)
        if hp.size == 0:
            n_miss += 1
            continue
        got = area[hp].sum()
        rep = float(topo["totalArea"][sp_])
        e = (got - rep) / rep if rep > 0 else np.nan
        if np.isfinite(e) and abs(e) > AREA_TOL:
            n_bad += 1
        r = len(ids)
        rows.append(np.full(hp.size, r, dtype=np.int64))
        cols.append(hp)
        vals.append(area[hp])
        ids.append(sid)
        aerr.append(e)
        nhru.append(hp.size)

    if verbose:
        if n_miss:
            print(f"  !! {n_miss} gauge(s) skipped: reach id not in the "
                  f"topology")
        if n_bad:
            print(f"  !! {n_bad} gauge(s) disagree with totalArea by "
                  f">{AREA_TOL:.0%}")
    if not ids:
        raise RuntimeError("No gauges resolved. Do the crosswalk reach ids "
                           "match seg_id in the topology?")

    H = sp.csr_matrix((np.concatenate(vals),
                       (np.concatenate(rows), np.concatenate(cols))),
                      shape=(len(ids), hru_ids.size))
    area_m2 = np.asarray(H.sum(axis=1)).ravel()

    A = (H @ G).tocsr()                    # rows sum to the basin area
    rs = np.asarray(A.sum(axis=1)).ravel()
    A = (sp.diags(np.where(rs > 0, 1.0 / np.maximum(rs, 1e-300), 0.0))
         @ A).tocsr()
    A.data = A.data.astype(np.float32)
    A.eliminate_zeros()

    # bounding box of each basin's contributing cells, for the map footprint
    bbox = np.zeros((len(ids), 4))
    for r in range(A.shape[0]):
        c = A.indices[A.indptr[r]:A.indptr[r + 1]]
        if c.size == 0:
            continue
        j, i = np.divmod(c, nlon)
        bbox[r] = [glat[j].min(), glat[j].max(), glon[i].min(), glon[i].max()]

    if verbose:
        print(f"  matrix: {A.shape[0]} gauges x {A.shape[1]} cells, "
              f"{A.nnz:,} nonzeros ({A.data.nbytes / 1e6:.0f} MB)")

    out = {"A": A, "ids": ids, "area_km2": area_m2 / 1e6,
           "n_hru": np.array(nhru), "n_cells": A.getnnz(axis=1),
           "bbox": bbox, "area_err": np.array(aerr)}
    if use_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        sp.save_npz(mpath, A)
        np.savez(kpath, ids=np.array(ids, dtype=object),
                 area_km2=out["area_km2"], n_hru=out["n_hru"],
                 n_cells=out["n_cells"], bbox=bbox, area_err=out["area_err"])
        if verbose:
            print(f"Cached -> {mpath}")
    return out


def summarize(W):
    print(f"\n{len(W['ids'])} gauges mapped")
    print(f"  area          : {W['area_km2'].min():,.0f} - "
          f"{W['area_km2'].max():,.0f} km2")
    print(f"  HRUs/basin    : median {int(np.median(W['n_hru']))}, "
          f"max {int(W['n_hru'].max())}")
    print(f"  cells/basin   : median {int(np.median(W['n_cells']))}, "
          f"max {int(W['n_cells'].max())}")
    e = np.abs(W["area_err"][np.isfinite(W["area_err"])])
    if e.size:
        print(f"  vs totalArea  : max |error| {100 * e.max():.3f}%, "
              f"{int((e > AREA_TOL).sum())} gauge(s) over {AREA_TOL:.0%}")


# ---------------------------------------------------------------- averaging
def basin_average(A, ds_h0, varname, scale=1.0, offset=0.0):
    """Area-weighted basin mean of one h0 field, (time, lat, lon) ->
    (n_gauges, n_time). NaN cells contribute zero."""
    f = ds_h0[varname].values
    ntime = f.shape[0]
    f = np.ascontiguousarray(f.reshape(ntime, -1), dtype=np.float32)
    np.nan_to_num(f, copy=False)
    out = (A @ f.T) * scale + offset
    del f
    return out
