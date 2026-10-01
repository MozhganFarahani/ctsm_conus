# CTSM-CONUS: high-resolution CTSM/mizuRoute simulations over CONUS

Five CTSM configurations run at 0.125° (~12 km) over the contiguous US with NLDAS2 forcing (water years 1981–2018), each routed with mizuRoute on the MERIT-Hydro network and evaluated against ~2,300 stream gauges. The experiments change one option at a time from a control: irrigation, evolving land cover, hillslope hydrology, and prognostic phenology.

This repository archives the setup scripts, the complete CIME case folders, and the analysis and dashboard code. It does not contain model source code or model output.

Project: CGD SIF-T FY26, NSF NCAR Terrestrial Sciences Section.
Dashboard: <https://project.cgd.ucar.edu/projects/ctsm-conus/>

> **Status:** the code is final: shared helpers in `analysis/lib/`, every path in `analysis/config/paths.py` (Python) or `setup/ctsm.env` (shell), and a smoke test in `tools/smoke_test.sh`. Methods and results are unchanged from the original scripts. See the [pre-public checklist](#pre-public-checklist) before making the repository public.

## Model versions

CTSM is used unmodified: no source changes, and every case's `SourceMods/` is empty.

| Component | Version |
|---|---|
| CTSM | `ctsm5.4.049` (commit `a96fb3f83`), CLM6.0 physics |
| mizuRoute | `v3.1.1` |
| CIME | `cime6.2.2` |
| CMEPS / CDEPS | `cmeps1.1.47` / `cdeps1.0.96` |
| ccs_config | `ccs_config_cesm1.0.83` |
| PIO | `pio2_6_8` |

To get the same model code:

```bash
git clone https://github.com/ESCOMP/CTSM.git
cd CTSM
git checkout ctsm5.4.049
./bin/git-fleximod update
```

## Common setup

| Item | Value |
|---|---|
| Grid | `nldas2_nldas2_rMERIT_mnldas2`: 224 x 464 cells, 25–53°N, 235–293°E; 80,439 land cells; 227,247 MERIT-Hydro catchments for routing |
| Forcing | NLDAS2, 1980–2018 (`DATM_YR_START=1980`, `DATM_YR_END=2018`, `DATM_YR_ALIGN=1980`) |
| Compset (SP) | `I2000Clm60SpMizGsNldas` |
| Soil layers | `20SL_8.5m` |
| Tuning | `LND_TUNING_MODE=clm6_0_NLDAS2`, which falls back to `clm6_0_GSWP3v1` (no NLDAS2 tuning exists) |
| Spinup | transient NLDAS2 from 1980 (not cycled); length per config below |
| Evaluation run | `RUN_TYPE=hybrid` from the config's spinup restart, start 1980-10-01, 38 years (Oct 1980 – Sep 2018) |
| History | land: monthly (`h0a`) and daily (`h1a`); mizuRoute: monthly. Field lists differ by config (see each case's `user_nl_clm`) |
| Routing options | `bypass_routing_option = direct_to_outlet`, `qgwl_runoff_option = negative`, `limit_irrigation_if_rof_enabled = .false.` |
| Machine | Derecho (runs), Casper (analysis); nuopc driver, Intel compiler |

## Configurations

| Config | Differs from control | Spinup case | Eval case | Spinup | `NTASKS_ROF` |
|---|---|---|---|---|---|
| control | — | `control` | `control` | 22 yr, restart 2002-01-01 | -5 (640 tasks) |
| irrigation_on | `irrigate = .true.` | `irrigation_on` | `irrigation_on` | 22 yr, restart 2002-01-01 | -5 |
| evolving_landcover | HIST compset; 1850 surface dataset + land-use timeseries 1850–2023 | `evolving_landcover` | `evolving_landcover` | 22 yr, restart 2002-10-01 | -5 |
| hillslope | `use_hillslope = .true.`, `use_hillslope_routing = .true.`, `hillslope_file` | `hillslope_on` | `hillslope_eval` | 24 yr, restart 2004-10-01 | -14 (1792 tasks) |
| prog_phenology | BGC compset (`2000_DATM%NLDAS2_CLM60%BGC_SICE_SOCN_MIZUROUTE_SGLC_SWAV`) | `prog_phenology` | `prog_phenology` | 22 yr, restart 2002-10-01 | -5 |

Notes on the configurations:

- **control:** the eval used downstream is a second 38-year pass, started from the restart at the end of the first pass (2018-10-01).
- **irrigation_on:** irrigation is set with `irrigate = .true.` in `user_nl_clm`. The `-irrig on` build option is not recognized in this CTSM version.
- **evolving_landcover:** CTSM's build-namelist turns irrigation on by default with these land-use files, and it was kept on. The land-cover effect is therefore evolving_landcover minus irrigation_on, and the irrigation effect is irrigation_on minus control. The eval sets `check_finidat_year_consistency = .false.`.
- **hillslope:** spinup and eval are separate cases. `NTASKS_ROF=-14` matches the task count the spinup's mizuRoute restart was written with; the eval cannot read that restart with a different count. `CLM_BLDNML_OPTS` includes `-ignore_warnings` for the `use_hillslope` + `use_init_interp` warning.
- **prog_phenology:** initialized from the default global f09 CMIP7 restart (interpolated). Soil carbon is not in equilibrium, which is acceptable here because carbon is not evaluated.

## Repository layout

```
setup/                  case-creation scripts, one per config, each with spinup and eval modes
cases/                  the six CIME case folders, complete (archive; never edited by hand)
analysis/config/        paths.py: every GLADE path the analysis code uses
analysis/lib/           shared helpers: reading output and observations, metrics, basin averaging, map style
analysis/qc/            control QC and water-balance checks
analysis/spinup/        spinup drift and restart-boundary checks
analysis/streamflow/    streamflow evaluation against observed flow
analysis/climatology/   monthly climatology maps
analysis/diagnostics/   time-alignment check and input-data reference
analysis/animation/     CONUS discharge animation
dashboard/              multi-config streamflow dashboard: builder, template, PBS job, web/ landing page
tools/                  scripts that maintain and test this repository
environment.yml         the Python packages the code imports, at the npl-2026a versions
```

### `setup/`

All scripts source `ctsm.env` (project, compiler, driver, resolution, queue, machine, compsets, and every path the shell scripts use). Run them on Derecho, from the CIME scripts folder (`$CIME_SCRIPTS` in `ctsm.env`); `create_newcase` does not work from Casper. Each script prints its usage with `--help`.

`--dry-run` (first argument, from any folder) writes only the case's final `user_nl_clm` to `$DRY_RUN_DIR/<case>/` (default: a new temp folder). It creates no case and runs no CIME command. To check a script against the archived case:

```
DRY_RUN_DIR=$(mktemp -d) bash setup/setup_control.sh --dry-run
diff <dry-run folder>/control/user_nl_clm cases/control/user_nl_clm
```

The archived files also contain CIME's comment header, and they wrap lines differently. Compare them with comments and whitespace removed.

Usage (each script also takes `--dry-run`):

```bash
bash <repo>/setup/setup_control.sh spinup            # create + configure the spinup case
bash <repo>/setup/setup_control.sh eval 2002-01-01   # switch it to the eval run from that restart date
```

| File | Purpose |
|---|---|
| `ctsm.env` | shared settings, paths and the account code for shell scripts; also the history field list (`HIST_FIELDS_1`, `HIST_FIELDS_2`, `write_hist_nl`) that the setup scripts share |
| `setup_control.sh` | control spinup and eval: `spinup`, `eval <refdate>` |
| `setup_irrigation.sh` | irrigation_on: `spinup`, `eval <refdate>` |
| `setup_landcover.sh` | evolving_landcover: `spinup`, `eval <refdate>` |
| `setup_hillslope_spinup.sh` | hillslope spinup case `hillslope_on`: no argument |
| `setup_hillslope_eval.sh` | hillslope eval case `hillslope_eval`: `<refdate>` of the hillslope_on restart |
| `setup_proghenol.sh` | prog_phenology: `spinup`, `eval <refdate>` |

### `cases/`

Each folder is the full case directory from `cime/scripts/<case>/`. The files that define a case:

| File | What it records |
|---|---|
| `user_nl_clm`, `user_nl_mizuroute`, `user_nl_mizuroute_control`, `user_nl_datm*`, `user_nl_cpl` | namelist settings |
| `replay.sh` | the `create_newcase` and `xmlchange` commands, in order |
| `CaseStatus` | the same history with timestamps, plus every build and submit |
| `README.case` | the `create_newcase` command |
| `CaseDocs/` | resolved namelists as the model read them (`lnd_in`, `mizuRoute.control`, ...) |
| `Buildconf/*.input_data_list` | every input file the case reads, by component |
| `env_*.xml` | final case settings; `env_mach_pes.xml` holds the task layout |
| `run.*.o*`, `st_archive.*.o*`, `timing/` | batch logs and throughput for each submission |
| `case_git_log.txt` | the history of CIME's per-case git repo (its `.git` folder is not archived) |

Case files contain absolute GLADE paths. Symlinks such as `xmlchange` and `case.submit` point into the original CIME checkout and will not resolve elsewhere.

### `analysis/`

Run everything with the `npl-2026a` conda environment on Casper (`module load conda && conda activate npl-2026a`); `environment.yml` lists the packages and versions for use elsewhere. Light checks can run on a login node; full builds and all-gauge runs go to PBS on Casper (from a Derecho login node, add `-q casper@casper-pbs`). The PBS scripts carry no `#PBS -A` or `#PBS -o` line: the account and the log folder are passed at submit time, from `setup/ctsm.env`:

```bash
source setup/ctsm.env                      # from the repo root: sets $PROJECT and $OUTPUT_ROOT
cd dashboard && qsub -A "$PROJECT" -o "$OUTPUT_ROOT/dashboard/" run_dashboard.pbs
```

Each PBS script has its own submit line in its header.

Every GLADE path (model output, observations, routing network, CESM input data, output folder) is defined once in `analysis/config/paths.py`. Scripts, notebooks and the dashboard import it; edit paths there, nowhere else. The shell scripts take theirs from `setup/ctsm.env`, which repeats the output root: keep the two in sync. The one notebook (animation) expects to be run from its own folder; it writes to `<output root>/animation/`, or to `$OUT_DIR` if set.

Every script writes under the output root, `paths.OUTPUT_ROOT` (`/glade/work/mozhgana/ctsm_conus_output/`), by default: `qc/<config>/`, `spinup/<case>/`, `streamflow/`, `climatology/`, `dashboard/` (and its weight cache), `animation/`, `case_inputs.csv`. `--outdir` overrides it (`--csv` for `list_case_inputs.py`). Scripts that read one configuration take `--config` (archive folder name, default `control`); the spinup checks take `--case` (default `hillslope_on`). Every script prints its inputs, outputs and usage with `--help`.


| File | Purpose | Usage (from the file's folder) |
|---|---|---|
| `config/paths.py` | every GLADE path used by the analysis code, and the evaluation period (`EVAL_START`, `EVAL_END`: Oct 1980 – Sep 2018) | imported |
| `lib/io.py` | open land and mizuRoute history, observed flow and the gauge crosswalk; monthly time alignment | imported (`from lib import io as lio`) |
| `lib/metrics.py` | NSE, KGE, PBIAS and correlation for many gauges at once; `STABLE_MIN_MONTHS` for NSE_stable | imported |
| `lib/basins.py` | gauge-to-grid upstream weights and basin averaging (Naoki Mizukami's mapping; within 0.000% of `totalArea` for all 2,311 gauges); weights cached in `paths.UPSTREAM_CACHE` | imported |
| `lib/plotting.py` | CONUS extent, projection and basemap | imported |
| `qc/ctsm_control_explore.py` | file inventory, time gaps, domain water balance, mizuRoute screen | `python ctsm_control_explore.py --config control` |
| `qc/ctsm_spatial_water_balance.py` | per-cell water-balance residual maps | `python ctsm_spatial_water_balance.py --config control` |
| `spinup/check_hillslope_spinup.py` | yearly domain-mean drift vs interannual noise for a spinup | `python check_hillslope_spinup.py --case hillslope_on` |
| `spinup/check_restart_discontinuity.py` | tests for a jump in a domain mean at a restart date | `python check_restart_discontinuity.py --case hillslope_on --restart-date 1998-10-01` |
| `spinup/check_spinup_drift.py` | spinup drift: domain water-year means and daily checks at three sites | `python check_spinup_drift.py --case hillslope_on --years 1981 1984`; full run: `run_spinup_drift.pbs` |
| `streamflow/ctsm_streamflow_eval.py` | NSE, KGE, PBIAS and correlation against observed monthly flow, all gauges, one config | `python ctsm_streamflow_eval.py --config control --parallel`; all five configs: `run_streamflow_eval.pbs` |
| `climatology/ctsm_climatology_maps.py` | monthly climatology cache and maps (see `climatology/README.md`; field list in `ctsm_control_history_fields.csv`) | `python ctsm_climatology_maps.py --monthly`; rebuild the cache: `run_ctsm_climatology.pbs` |
| `diagnostics/check_time_align.py` | tests month offsets between land output and mizuRoute records for one gauge | `python check_time_align.py 09040000 --config control` |
| `diagnostics/describe_inputs.py` | prints the contents of representative input files (forcing, meshes, maps, topology, surface data, initial condition) | `python describe_inputs.py` |
| `animation/discharge_map_animation_conus.ipynb` | CONUS maps of `QRUNOFF`, `basRunoff` and `RoutedRunoff`, and an animation (short notebook on `analysis/lib`) | open in Jupyter |

### `dashboard/`

| File | Purpose |
|---|---|
| `build_streamflow_dashboard.py` | builds one self-contained HTML dashboard for several configs; basin averages come from `analysis/lib/basins.py` |
| `dashboard_template.py` | the HTML/CSS/JS template the builder fills in |
| `run_dashboard.pbs` | Casper job that builds the dashboard for all five configs; submit from this folder |
| `web/index.html`, `web/assets/hero.png` | the landing page |

Test on a few gauges first, then build all five on Casper:

```bash
python build_streamflow_dashboard.py --configs control,irrigation_on --test-basins 09040000
source ../setup/ctsm.env && qsub -A "$PROJECT" -o "$OUTPUT_ROOT/dashboard/" run_dashboard.pbs
```

The builder writes `<name>_dashboard.html` to `ctsm_conus_output/dashboard/` (`paths.DASHBOARD_OUT`; `--outdir` overrides it). To deploy, copy it as `dashboard.html`, together with `web/index.html` and `web/assets/`, with `scp` from `data-access.ucar.edu` to goldhill, `/project/webshare/projects/ctsm-conus`.

### `tools/`

| File | Purpose |
|---|---|
| `smoke_test.sh` | runs every script on its smallest input (one year, one gauge) and the six setup dry runs, and reports PASS/FAIL per test; each dry run must match `cases/<case>/user_nl_clm` (comments and whitespace ignored). Writes only under `<output root>/smoke_test/`. Run it after every change, from the repo root: `bash tools/smoke_test.sh`, or on Casper: `source setup/ctsm.env && qsub -A "$PROJECT" -o "$OUTPUT_ROOT/" tools/smoke_test.sh` |
| `capture_cases.sh` | copies each CIME case folder (from `$CIME_SCRIPTS` in `setup/ctsm.env`) into `cases/` and saves its per-case git log: `tools/capture_cases.sh . control` |
| `list_case_inputs.py` | lists every input file each case needs (from `Buildconf/*.input_data_list`, `CaseDocs/lnd_in`, `CaseDocs/mizuRoute.control` and `user_nl_*`), reports whether it exists, flags files on `/glade/derecho/scratch` (purge risk), and points to archived copies of missing restarts: `python tools/list_case_inputs.py control` |

## Input data (not in this repository)

| Data | Location |
|---|---|
| NLDAS2 forcing | `/glade/campaign/cesm/cesmdata/inputdata/atm/datm7/atm_forcing.datm7.NLDAS2.0.125d.v1/` |
| Land-use timeseries and 1850 surface dataset (evolving_landcover), hillslope parameters | generated by Sean Swenson: `/glade/derecho/scratch/swensosc/for_mozhgan/`; backup copy in `ctsm_conus_setup/for_mozhgan/` |
| mizuRoute topology (augmented) | `/glade/work/mizukami/test_mizuRoute/MERIT_basin_nldas/ancillary_data/ntopo_MERIT_Hydro_v1_aug.nc` |
| Grid-to-catchment weights | `/glade/work/mizukami/py_mapping/MERIT_Hydro/mapping_v1/spatialweights_nldas0.125_to_merit_nldas.nc` |
| Observed streamflow (daily, 2,311 gauges) | `<path_to_streamflow_tseries>/flow_multi_agency_1965-10-01_2024-09-30.nc` |
| Gauge crosswalk | `flow_multi_agency_all_meta.csv` (USGS/USACE, naturalized and observed) |
| Model output | `/glade/derecho/scratch/mozhgana/archive/<case>/` |

The full list of inputs for each case is in `cases/<case>/Buildconf/*.input_data_list`. `python tools/list_case_inputs.py` collects these with the namelist and `user_nl_*` references, and checks each file.

## Known caveats

- No NLDAS2-specific tuning exists; the GSWP3 tuning is used.
- evolving_landcover runs with irrigation on (see [Configurations](#configurations)).
- The hillslope spinup is 24 years; soil liquid water still drifts at about 1.1 times its interannual noise.
- Routed runoff received by mizuRoute (`basRunoff`) does not match basin-averaged `QRUNOFF` at some snow-dominated gauges; this is under investigation and is not a mapping error.

## Pre-public checklist

Before the repository is made public:

- [ ] Add a LICENSE.
- [ ] Get Naoki Mizukami's OK and credit him for the code adapted from his notebooks (at least the basin averaging in `analysis/lib/basins.py`, which follows his remapping).
- [ ] Review the account codes, usernames and internal hostnames left in `cases/` (the archive is kept as is).

## Contributors

Mozhgan Farahani (NSF NCAR), with Andy Wood, Sean Swenson and Naoki Mizukami.

Contact: mozhgana@ucar.edu
