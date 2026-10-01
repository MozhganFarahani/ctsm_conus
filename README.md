# CTSM-CONUS: high-resolution CTSM/mizuRoute simulations over CONUS

Five CTSM configurations run at 0.125° (~12 km) over the contiguous US with NLDAS2 forcing (water years 1981–2018), each routed with mizuRoute on the MERIT-Hydro network and evaluated against ~2,300 stream gauges. The experiments change one option at a time from a control: irrigation, evolving land cover, hillslope hydrology, and prognostic phenology.

This repository archives the setup scripts, the complete CIME case folders, and the analysis and dashboard code. It does not contain model source code or model output.

Project: CGD SIF-T FY26, NSF NCAR Terrestrial Sciences Section.
Dashboard: <https://project.cgd.ucar.edu/projects/ctsm-conus/>

> **Status:** work in progress. The analysis code has been reorganized and all GLADE paths are collected in `analysis/config/paths.py`; methods and results are unchanged.

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
analysis/qc/            control QC and water-balance checks
analysis/spinup/        spinup drift and restart-boundary checks
analysis/streamflow/    streamflow evaluation against observed flow
analysis/climatology/   monthly climatology maps
analysis/diagnostics/   time-alignment check and input-data reference
analysis/animation/     CONUS discharge animation
dashboard/              multi-config streamflow dashboard: builder, template, PBS job, web/ landing page
tools/                  scripts that maintain this repository
```

### `setup/`

All scripts source `ctsm.env` (project, compiler, driver, resolution, queue, machine, compsets). Run them on Derecho; `create_newcase` does not work from Casper.

| File | Purpose |
|---|---|
| `ctsm.env` | shared settings |
| `setup_control.sh` | control spinup and eval |
| `setup_irrigation.sh` | irrigation_on |
| `setup_landcover.sh` | evolving_landcover |
| `setup_hillslope_spinup.sh`, `setup_hillslope_eval.sh` | hillslope spinup (`hillslope_on`) and eval (`hillslope_eval`) |
| `setup_proghenol.sh` | prog_phenology |
| `check_landcover_irrigate.sh` | diagnostic: shows which `irrigate` value build-namelist picks for the land-cover setup |

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

Run everything with the `npl-2026a` conda environment on Casper (`module load conda && conda activate npl-2026a`). Light checks can run on a login node; full builds and all-gauge runs go to PBS (`-q casper -A P93300041`; from a Derecho login node, `qsub -q casper@casper-pbs`).

Every GLADE path (model output, observations, routing network, CESM input data, output folder) is defined once in `analysis/config/paths.py`. Scripts, notebooks and the dashboard import it; edit paths there, nowhere else. The one notebook (animation) expects to be run from its own folder.

Outputs that are not part of the repository (climatology maps and cache, the dashboard build and its weight cache, `case_inputs.csv`) are written to `/glade/work/mozhgana/ctsm_conus_output/`. Scripts with an `--outdir` option write to the current folder by default.

| File | Purpose |
|---|---|
| `config/paths.py` | every GLADE path used by the analysis code |
| `qc/ctsm_control_explore.py` | file inventory, time gaps, domain water balance, mizuRoute screen |
| `qc/ctsm_spatial_water_balance.py` | per-cell water-balance residual maps |
| `spinup/check_hillslope_spinup.py` | yearly domain-mean drift vs interannual noise for a spinup |
| `spinup/check_restart_discontinuity.py` | tests for a jump in a domain mean at a restart date |
| `spinup/check_spinup_drift.py` | spinup drift: domain water-year means and daily checks at three sites; `run_spinup_drift.pbs` runs it on Casper |
| `streamflow/ctsm_streamflow_eval.py` | NSE, KGE, PBIAS and correlation against observed monthly flow, all gauges, one config (`--config`) |
| `climatology/` | monthly climatology maps (see its own README); `run_ctsm_climatology.pbs` rebuilds the cache on Casper |
| `diagnostics/check_time_align.py` | tests month offsets between land output and mizuRoute records for one gauge |
| `diagnostics/describe_inputs.py` | prints the contents of representative input files (forcing, meshes, maps, topology, surface data, initial condition) |
| `animation/discharge_map_animation_conus.ipynb` | CONUS maps of `QRUNOFF`, `basRunoff` and `RoutedRunoff`, and an animation (short notebook on `analysis/lib`) |

### `dashboard/`

| File | Purpose |
|---|---|
| `upstream_basin.py` | gauge-to-grid upstream weights and basin averaging (Naoki Mizukami's mapping; within 0.000% of `totalArea` for all 2,311 gauges) |
| `build_streamflow_dashboard.py` | builds one self-contained HTML dashboard for several configs |
| `dashboard_template.py` | the HTML/CSS/JS template the builder fills in |
| `run_dashboard.pbs` | Casper job that builds the dashboard for all five configs; submit from this folder |
| `web/index.html`, `web/assets/hero.png` | the landing page |

`run_dashboard.pbs` writes `<name>_dashboard.html` to `ctsm_conus_output/dashboard/` (run by hand, the builder writes to `--outdir`, default `./dashboard`). To deploy, copy it as `dashboard.html`, together with `web/index.html` and `web/assets/`, with `scp` from `data-access.ucar.edu` to goldhill, `/project/webshare/projects/ctsm-conus`.

### `tools/`

| File | Purpose |
|---|---|
| `capture_cases.sh` | copies each CIME case folder into `cases/` and saves its per-case git log |
| `list_case_inputs.py` | lists every input file each case needs (from `Buildconf/*.input_data_list`, `CaseDocs/lnd_in`, `CaseDocs/mizuRoute.control` and `user_nl_*`), reports whether it exists, flags files on `/glade/derecho/scratch` (purge risk), and points to archived copies of missing restarts |

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

## Planned work

- Add a license before the repository is made public.

## Contributors

Mozhgan Farahani (NSF NCAR), with Andy Wood, Sean Swenson and Naoki Mizukami.

Contact: mozhgana@ucar.edu
