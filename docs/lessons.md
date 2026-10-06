(lessons)=
# Lessons, caveats and future work

## Lessons

Apart from the REST_N default below, most setup problems were one-line script or namelist fixes.

**Restarts and resubmission**

- **Set REST_N explicitly.** If it is left unset, it defaults to STOP_N. A 22-year segment killed at walltime then writes no restart. Use short segments (STOP_N=6) with REST_N no larger than STOP_N. Example: [hillslope](#case-hillslope) (Issues and fixes).
- **CESM3 restart pointers are dated.** There is no undated rpointer.lnd; DRV_RESTART_POINTER must name the dated file, e.g. rpointer.cpl.2004-10-01-00000.
- **Keep NTASKS_ROF identical between spinup and evaluation.** mizuRoute restarts record the task count, and a mismatch fails with "Number of MPI tasks on restart file is different from number using now". Example: [hillslope](#case-hillslope) (Issues and fixes).
- **Start evaluations on a water year** (RUN_STARTDATE=1980-10-01) so the record lines up with water-year analysis.

**Namelist and build**

- **History fields cannot change on a CONTINUE_RUN**, because the field count must match the restart. Add fields such as H2OSOI at the start of a new (hybrid) run.

**Case-specific lessons**

- -irrig on rejected: [irrigation_on](#case-irrigation-on) (Issues and fixes).
- Build-namelist defaults with flanduse_timeseries, and regional grids: [evolving_landcover](#case-evolving-landcover) (Issues and fixes).
- QLATFLOWOUT and hillslope with use_init_interp (Issues and fixes): [hillslope](#case-hillslope).

**Diagnosis**

- **Check the forcing before blaming the model.** Example: [control](#case-control) (Spinup).
- **Check seasonal signals before calling a restart bug.** Example: [hillslope](#case-hillslope) (Spinup).

## Caveats

The streamflow skill numbers stand as produced, but four known issues limit how far differences can be attributed to land processes.

- **No NLDAS2-specific parameter tuning.** See [Common setup](#common-setup) (Parameter tuning row of the shared setup table).
- **The land-cover run also has irrigation on.** See [evolving_landcover](#case-evolving-landcover) (case card, Baseline).
- **Spinup differs by configuration.** See [hillslope](#case-hillslope) (Spinup), [control](#case-control) (Spinup) and [prog_phenology](#case-prog-phenology) (Spinup).
- **Gauge types are mixed.** Some gauges report naturalized flows and others observed (regulated) flows; skill is not yet split by type.

**Near-zero-flow gauges:** arid gauges with near-zero flow can have extreme percent bias (North Concho River, TX: +16,293%) and are treated as unreliable tests of skill; this is a working judgment, not a tested criterion.

**Scope not yet covered:** snow, soil moisture and ET have not been evaluated against NLDAS or independent observations. Results are monthly only, because mizuRoute daily output was not written.

## Future work

With more time and funding, the next steps are a full non-streamflow evaluation, cleaner single-option contrasts, and publishing the runs as baseline datasets. These are candidates for a follow-on proposal, beyond the SIF-T scope; none is decided.

**Evaluation**

- Evaluate snow, soil moisture and ET against NLDAS and independent observations. The SIF-T application promised this, and it was not started.
- A gridded-layer dashboard: CONUS maps of SWE, QRUNOFF, soil moisture, ET, precipitation, T2M and LH/SH for each configuration and as differences from its baseline. Andy Wood asked for these fields; a version was tested on synthetic data only.
- Skill split by naturalized vs observed gauges and by water yield, with a gauge-type filter in the dashboard.

**Experiments**

- Rerun evolving land cover with irrigation off, for a clean land-cover contrast against control.
- Irrigation with limit_irrigation_if_rof_enabled = .true. (and optionally groundwater irrigation), so irrigated runs conserve basin water.
- A longer hillslope spinup, to remove the residual soil-moisture drift.
- A full carbon spinup for prog_phenology, so carbon fluxes can be evaluated too.
- Parameter tuning or calibration for NLDAS2 forcing.

**Products**

- Publish the five simulations as community baseline datasets with a DOI.
- Machine-learning emulators trained on the best-performing configurations.
