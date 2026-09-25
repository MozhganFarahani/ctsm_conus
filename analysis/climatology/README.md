# CTSM CONUS Climatology Maps

Monthly climatology maps for every field in the CTSM control-run history output,
over CONUS, 1981-10 to 2018-10 (37 years, spin-up year excluded).

Part of the SIF-T control-run QC pipeline. Takes CTSM `h0a` monthly history files
and produces a cached climatology plus three figure sets per variable.

---

## How it works

The script runs in two stages, and the split is the whole point of the design.

**Stage 1 — build the cache.** Reads all 445 monthly `h0a` files once, collapses
soil-level dimensions, averages by calendar month, and writes a single NetCDF:
12 x lat x lon per variable. Expensive (tens of minutes, needs a batch job).
Runs once.

**Stage 2 — plot from the cache.** Every figure is drawn from that NetCDF, so
re-styling takes seconds and needs no job. Iterate on colour scales, add
variables to a figure, change the map extent — all without re-reading the
archive.

Two things worth knowing about the approach:

- **Monthly files only.** For a monthly climatology the daily `h1a` files add
  nothing at ~30x the I/O. Save those for extremes and percentile diagnostics.
- **Month labels come from filenames, not the `time` coordinate.** CTSM stamps
  monthly output at the *end* of the averaging period, so `1981-10` decodes to
  `1981-11-01`. Parsing `????-??` from the filename avoids that off-by-one and
  the `cftime` noleap handling entirely.

Because the calendar is noleap, every instance of a given month has identical
length, so the unweighted across-year mean is exact — no day weighting needed.

---

## Requirements

- NCAR Casper (or Derecho)
- `npl-2026a` conda environment: `xarray`, `dask`, `netCDF4`, `cartopy`,
  `matplotlib`, `pandas`, `numpy`
- `ctsm_control_history_fields.csv` — the field list, used for units and
  definitions

---

## Setup

### 1. Paths

`DEFAULT_PATHS` at the top of `ctsm_climatology_maps.py` takes its paths from
`analysis/config/paths.py`; change them there, not in the script:

| Key | Default |
|---|---|
| `ctsm_hist_dir` | `paths.lnd_hist("control")`: `/glade/derecho/scratch/mozhgana/archive/control/lnd/hist/` |
| `fields_csv` | `ctsm_control_history_fields.csv` next to the script |
| `out_dir` | `paths.CLIM_OUT`: `/glade/work/mozhgana/ctsm_conus_output/climatology/maps` |
| `cache_nc` | `paths.CLIM_CACHE`: `/glade/work/mozhgana/ctsm_conus_output/climatology/ctsm_monthly_climatology.nc` |

The output sits outside the repository: three figure sets for 44 variables is a
few hundred MB of PNGs.

### 2. Warm the cartopy cache (do this once, on a login node)

Compute nodes have no outbound network, so cartopy will fail trying to download
Natural Earth shapefiles mid-job. Cache them from a login node first; they land
in `~/.local/share/cartopy` and every later job reads from there.

```bash
module load conda && conda activate npl-2026a
python -c "
import cartopy.feature as cf
for f in (cf.LAND, cf.OCEAN, cf.STATES, cf.BORDERS, cf.COASTLINE):
    list(f.geometries())
print('cartopy data cached')
"
```

### 3. Smoke-test two variables before committing to all 44

```bash
qsub -I -A P93300041 -q casper -l select=1:ncpus=4:mem=20GB -l walltime=01:00:00
module load conda && conda activate npl-2026a
cd <repo>/analysis/climatology

python ctsm_climatology_maps.py --rebuild --vars QRUNOFF TSA --monthly
```

Check that the file count prints as **445**, that the figures look plausible, and
that the caption numbers are sane. Then delete the cache — it only holds those
two variables, and `--rebuild` overwrites rather than merges.

### 4. Full run as a batch job

```bash
cd <repo>/analysis/climatology && qsub run_ctsm_climatology.pbs
```

Submit from this folder: the job runs the script from the folder it was
submitted from, and writes its log to `ctsm_conus_output/climatology/ctsm_clim.log`.
From a Derecho login node use `qsub -q casper@casper-pbs`. It requests
8 cpus / 80 GB / 3 h, which is deliberately generous — the level-collapse has to
materialise each file's soil levels before reducing them, and a three-hour job
dying at the write step is worse than over-requesting. Cut to 40 GB once you
know it fits.

---

## Command reference

Six flags. If no stage flag is given, all three figure sets are produced.

| Flag | Effect |
|---|---|
| `--rebuild` | recompute the stage-1 cache (otherwise reused if present) |
| `--monthly` | 12-panel maps, one per calendar month |
| `--seasonal` | 4-panel maps, DJF / MAM / JJA / SON |
| `--summary` | one page of domain-mean seasonal cycles, all variables |
| `--vars A B C` | restrict to these base field names |
| `--limits fixed\|pct\|minmax` | how the colour limits are chosen (default `minmax`). Does **not** affect the log/lin/div scale type |

### Fresh start

```bash
# cache + all three figure sets
python ctsm_climatology_maps.py --rebuild

# cache two variables only, as a smoke test
python ctsm_climatology_maps.py --rebuild --vars QRUNOFF TSA --monthly
```

### Re-plot from an existing cache (seconds, no job needed)

```bash
python ctsm_climatology_maps.py --monthly
python ctsm_climatology_maps.py --seasonal
python ctsm_climatology_maps.py --summary
python ctsm_climatology_maps.py --monthly --seasonal    # combine any of them
python ctsm_climatology_maps.py                         # all three
```

### Variations

```bash
# actual data range is now the default -- no flag needed
python ctsm_climatology_maps.py --monthly

# robust 2-98th percentile, when a few bad gridcells are drowning the map
python ctsm_climatology_maps.py --monthly --limits pct

# pinned VAR_NORM numbers, for control-vs-experiment comparisons
python ctsm_climatology_maps.py --monthly --limits fixed

# one variable, both map styles
python ctsm_climatology_maps.py --monthly --seasonal --vars QRUNOFF

# water-balance group
python ctsm_climatology_maps.py --monthly --vars QRUNOFF QOVER QDRAI QVEGT QVEGE QSOIL RAIN SNOW

# soil state
python ctsm_climatology_maps.py --monthly --vars SOILLIQ SOILICE TSOI ZWT
```

### Two behaviours that catch people out

- **`--vars` means different things with and without `--rebuild`.** With it,
  you're choosing what goes *into* the cache. Without it, you're only filtering
  which figures get drawn from whatever the cache already holds.
- **`--rebuild` overwrites the cache, it does not merge.** A second
  `--rebuild --vars` run discards the first run's variables. To build in
  batches, write to different `cache_nc` paths.

---

## Output layout

```
/glade/work/mozhgana/ctsm_conus_output/climatology/
├── ctsm_monthly_climatology.nc      # stage-1 cache: 12 x lat x lon per variable
├── ctsm_clim.log                    # batch log
└── maps/
    ├── monthly/
    │   ├── QRUNOFF.png              # 12 panels, shared colour scale
    │   ├── TSA.png
    │   └── ...
    ├── seasonal/
    │   ├── QRUNOFF.png              # 4 panels, day-weighted seasonal means
    │   └── ...
    └── seasonal_cycle_summary.png   # all variables, area-weighted domain means
```

Multi-level fields get a suffix, set by `LEVELS`:

| Output name | Source |
|---|---|
| `SOILLIQ_total`, `SOILICE_total` | summed over `levsoi` (column total) |
| `TSOI_L1`, `TSOI_L5`, `TSOI_L10` | levels 1, 5, 10 of `levgrnd` |
| `QIN_L1`, `QOUT_L1` | top soil layer only |

Fields listed in the CSV but absent from the output files are reported at the
start of stage 1 and skipped — no need to prune the CSV.

---

## Reading the figures

All panels in a figure share one colour scale. This is deliberate: per-panel
autoscaling would make the months non-comparable, which is the most common way
these figures mislead.

Under each colourbar is a caption line. On the default (`minmax`) settings:

```
color scale: log, 0.00169 to 7.04 (actual range)     actual data range: -0.4 to 7.04 mm/day
0.65% <= 0, masked
```

| Field | Meaning |
|---|---|
| `color scale` | norm type and limits. `(actual range)` = full data range (the default), `(2-98th pct)` = robust percentile, `(fixed)` = numbers from `VAR_NORM` |
| `actual data range` | true min/max, **including anything the colourbar clips** |
| `saturated` | percent of cells beyond each end of the scale. Absent under `minmax`, since nothing is clipped |
| `<= 0, masked` | on a log scale, non-positive cells are masked; this is the fraction |

Under `pct` or `fixed` a `saturated:` field appears — that is the feedback loop
for tuning limits. Above roughly 5–10% saturated at the top means the limits are
too tight and real structure is hidden; a nearly uniform map means they are too
wide.

### Note on negative runoff over lakes

QRUNOFF is slightly negative over lake gridcells — real model output, not a
plotting artefact, since CTSM's lake landunit does not produce runoff the way the
vegetated landunit does. On log scales those cells are masked (white) and
reported in the caption. Worth confirming they are handled sensibly in the
water-balance sums too, not just the maps.

---

## Configuration

Not on the CLI; edit at the top of the script.

| Constant | Controls |
|---|---|
| `START_YM`, `END_YM` | analysis window; currently `1981-10` to `2018-10` |
| `VAR_NORM` | fixed per-variable colour scale, `("log"\|"lin"\|"div", vmin, vmax)` |
| `LIMITS` | default limits mode (`fixed`/`pct`/`minmax`), overridden by `--limits` |
| `LOG_VARS` | fields given an automatic log scale when not in `VAR_NORM` |
| `LEVELS` | how each soil-level field is collapsed (`"sum"` or a list of indices) |
| `EXTENT` | map bounds, 0–360 lon |
| `CMAP_BY_UNIT`, `PIVOT_UNITS` | colormap per unit; which units pivot at zero |
| `CONVERT` | unit conversion by unit string (mm/s → mm/day, K → degC) |
| `DPI` | figure resolution, currently 130 |

### VAR_NORM

Keys are **base** field names, so `TSOI` covers `TSOI_L1/L5/L10` and `SOILLIQ`
covers `SOILLIQ_total`. Each entry is `(kind, vmin, vmax)`, and the two parts are
used independently:

- **`kind`** (`"log"`/`"lin"`/`"div"`) is always honoured, in every limits mode.
  This is the important half — see *Two independent decisions* below.
- **`vmin`/`vmax`** are used only under `--limits fixed`; `pct` and `minmax`
  keep the kind and derive their own numbers.

So you do not need to edit this table at all for everyday use — the default
`minmax` mode ignores these numbers. All 44 CSV fields have a starting entry; the
numbers are priors from typical CTSM CONUS output, **not measured from this run**,
and only come into play under `--limits fixed`.

**Gotcha:** for `"div"`, °C limits are honoured as written and the scale pivots
at 0. For every other unit the scale is forced *symmetric* using
`max(|vmin|, |vmax|)`. Write non-temperature diverging entries symmetrically or
the scale will not be what you typed.

Least certain entries, check these first:

- `TWS` — absolute magnitude depends on how the aquifer term is counted
- `ZWT` — can reach ~80 m in arid cells; currently capped at 25 m
- `FIRA` — sign convention assumed positive = net loss. If your output is
  negative, switch to `("div", -110, 110)`
- `ALT` — mostly NaN over CONUS, may come out near-empty

### Two independent decisions

Colour scaling splits into two choices that are easy to conflate:

**1. The scale type — log, linear, or diverging. Not a matter of taste.** It is
set by the field's distribution and sign, and getting it wrong makes the map
unreadable regardless of the limits. Runoff over CONUS spans four decades
(median ~0.3, max a few hundred mm/day). On a realistic field:

| Scale, same min–max limits | Cells in the bottom 1% of the colourbar |
|---|---|
| linear | 95% |
| log | 9% |

Linear min–max renders that field as one flat colour with a few bright dots.
Temperature, by contrast, changes sign, so it needs a scale that pivots at 0 —
a sequential map there hides the freezing line. This is why `VAR_NORM` carries a
kind for every field, and why `--limits` never overrides it.

**2. The limit numbers. This one is genuinely optional**, and `--limits` chooses:

| Mode | Limits | Use it for |
|---|---|---|
| `minmax` | actual data range | QC and everyday browsing. Honest, no configuration, nothing hidden |
| `pct` | 2–98th percentile | when a few pathological gridcells are drowning the map |
| `fixed` | the numbers in `VAR_NORM` | control-vs-experiment comparisons only |

**This is the default** (`LIMITS = "minmax"` at the top of the script), so a bare
run gives you actual-range figures with no flags. It requires no per-variable
judgement, hides nothing, and on a correctly chosen scale type it reads perfectly
well. Percentile limits clip ~4% of cells by construction, which is backwards for
QC work where the outliers *are* the signal.

`pct` exists because min–max limits are hostage to single bad gridcells — one
cell at 500 mm/day can pull the scale out from under everything else. That
matters much less on a log scale than a linear one, which is most of why the
scale type is the more important of the two decisions.

`minmax` is not *quite* "nothing hidden" on a log scale: the floor is capped at
`vmax/1e4`, so a single near-zero cell cannot stretch the scale over ten decades
and squeeze all the real variation into a narrow band. That is a floor on
near-zero values, not a ceiling hiding large ones, so nothing important is lost.
On linear scales it shows the true full range.

### When `fixed` is required

Exactly one job: comparing the four sensitivity experiments against control.

Under `minmax` or `pct` each figure autoscales to its own data, so control and
irrigation-off end up with different colourbars and **a colormap difference reads
as a physical difference.** Pin the limits in `VAR_NORM` from the control run,
freeze them, and pass `--limits fixed`.

Since `minmax` is the default, `fixed` has to be requested explicitly — easy to
forget on the run that matters most. The `(fixed)` tag in every caption is the
check: if a comparison figure says `(actual range)`, the flag was missed and the
two figures are not comparable.

Derive those numbers from a default (`minmax`) pass on the control run rather than
trusting the starting values shipped in `VAR_NORM`.

---

## Troubleshooting

**`urllib.error.HTTPError: 403` from cartopy, or a hang on `shapereader`**
Natural Earth data is not cached and the compute node has no network. Run the
step-2 warm-up on a login node.

**Job killed / out of memory in stage 1**
The soil-level collapse materialises each file's levels before reducing. Lower
`chunks={"time": 12}` to `{"time": 4}` in `build_cache`, or split the run: 2D
fields first, then soil fields, writing to **different** `cache_nc` paths (see
the `--rebuild` note above).

**`ValueError: vmin, vcenter, and vmax must be in ascending order`**
An old copy of the script with the `TwoSlopeNorm` argument-order bug. It crashes
in stage 2, *after* the cache is written, so the expensive work is safe — update
the script and re-run the plotting stage only.

**Colour scale is not the type you specified**
Check whether the field is under a base name or a suffixed one; `VAR_NORM` keys
are base names. Also check the `"div"` symmetry gotcha above.

**A field is missing from the figures**
Stage 1 prints which CSV fields were absent from the history files. Four fields
are marked `To add` in the CSV; if they are not in the output, they will be
listed there.

**Editing the script while a job is running**
Has no effect on that job — Python reads the source at import. `VAR_NORM` and
everything else in stage 2 only affects plotting, never the cache, so a cache
built by any version is valid.

---

## Files

| File | Purpose |
|---|---|
| `ctsm_climatology_maps.py` | the tool |
| `run_ctsm_climatology.pbs` | Casper batch submission for the full run |
| `ctsm_control_history_fields.csv` | field list: names, definitions, units |
| `README.md` | this file |
