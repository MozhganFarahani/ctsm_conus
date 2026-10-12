(code-and-data)=
# Code and data

The dashboard is public on the CGD project site, the code is in a GitHub repository, and all model output and restarts are archived on Campaign storage.

## Repository layout

[github.com/MozhganFarahani/ctsm_conus](https://github.com/MozhganFarahani/ctsm_conus).

```
setup/                  case-creation scripts, one per config, each with spinup and eval modes
cases/                  the six CIME case folders, complete (archive; never edited by hand)
analysis/config/        paths.py: every GLADE path the analysis code uses, and the evaluation period
analysis/lib/           shared helpers: reading output and observations, metrics, basin averaging, map style
analysis/qc/            control QC and water-balance checks
analysis/spinup/        spinup drift and restart-boundary checks
analysis/streamflow/    streamflow evaluation against observed flow, HUC02 report figures
analysis/climatology/   monthly climatology maps
analysis/diagnostics/   time-alignment check and input-data reference
analysis/animation/     CONUS discharge animation
dashboard/              multi-config streamflow dashboard: builder, template, PBS job, web/ landing page
docs/                   technical note source (Jupyter Book 2 / MyST), served at the project page's note/
tools/                  scripts that maintain and test this repository
environment.yml         the Python packages the code imports, at the npl-2026a versions
```

The repository holds no model source and no model output.

## Scripts

**Setup scripts** (setup/; run on Derecho from the CIME scripts folder, \$CIME_SCRIPTS)

| Script | Case | Arguments |
|---|---|---|
| setup_control.sh | control | spinup, eval &lt;refdate&gt; |
| setup_irrigation.sh | irrigation_on | spinup, eval &lt;refdate&gt; |
| setup_landcover.sh | evolving_landcover | spinup, eval &lt;refdate&gt; |
| setup_hillslope_spinup.sh | hillslope_on | none |
| setup_hillslope_eval.sh | hillslope_eval | &lt;refdate&gt; of the hillslope_on restart |
| setup_proghenol.sh | prog_phenology | spinup, eval &lt;refdate&gt; |

Every script takes --help and --dry-run. A dry run writes only the case's final user_nl_clm to \$DRY_RUN_DIR/&lt;case&gt;/ and runs no CIME command; all six match their archived cases/&lt;case&gt;/user_nl_clm once comments and whitespace are ignored.

```
bash setup/setup_control.sh spinup            # create and configure the spinup case
bash setup/setup_control.sh eval 2002-01-01   # switch it to the eval run from that restart date
```

## Paths

**Paths and settings.** Every path is defined once: in analysis/config/paths.py for Python, in setup/ctsm.env for shell. ctsm.env repeats four of them (SCRATCH, ARCHIVE, OUTPUT_ROOT, and CIME_SCRIPTS, which is CASES_ROOT in paths.py): keep the two files in sync. Observed streamflow and gauge metadata are not yet public (Zenodo resource TBA): paths.py holds placeholders for OBS_DIR and CALIB_CONUS, and the real values go in an untracked analysis/config/paths_local.py that defines those two names.

**Output root.** Every script writes under /glade/work/mozhgana/ctsm_conus_output/ by default: qc/&lt;config&gt;/, spinup/&lt;case&gt;/, streamflow/, report/, climatology/, dashboard/ (with its weight cache), animation/ and case_inputs.csv. --outdir overrides it.

## PBS submission

`environment.yml` lists the packages and versions for use elsewhere.

**Submitting jobs.** PBS scripts carry no #PBS -A or #PBS -o line; the account and log folder come from ctsm.env at submit time. Analysis jobs run on Casper (from a Derecho login node, add -q casper@casper-pbs).

```
source setup/ctsm.env   # from the repo root: sets $PROJECT and $OUTPUT_ROOT
cd dashboard && qsub -A "$PROJECT" -o "$OUTPUT_ROOT/dashboard/" run_dashboard.pbs
```

## Smoke test

**Smoke test.** bash tools/smoke_test.sh runs every script on its smallest input (one year, one gauge), the six setup dry runs and a PBS syntax check, and reports PASS/FAIL per test. All 22 tests passed. It writes only under &lt;output root&gt;/smoke_test/.

## Directories

| Purpose | Path |
|---|---|
| CTSM clone (all cases) | /glade/work/mozhgana/ctsm_conus |
| Case directories | /glade/work/mozhgana/ctsm_conus/cime/scripts/&lt;case&gt; |
| Build and run | /glade/derecho/scratch/mozhgana/&lt;case&gt;/{bld,run} |
| Short-term archive (scratch) | /glade/derecho/scratch/mozhgana/archive/&lt;case&gt;/{lnd/hist,rof/hist,rest} |
| Analysis output, built dashboard, weight cache | output root (see Paths) |

## Data availability

| Item | Location | Access |
|---|---|---|
| Project page | [project.cgd.ucar.edu/projects/ctsm-conus](https://project.cgd.ucar.edu/projects/ctsm-conus/) | public |
| Dashboard | [project.cgd.ucar.edu/projects/ctsm-conus/dashboard.html](https://project.cgd.ucar.edu/projects/ctsm-conus/dashboard.html) | public |
| Setup scripts, case directories, analysis and dashboard code | [github.com/MozhganFarahani/ctsm_conus](https://github.com/MozhganFarahani/ctsm_conus) | private for now |
| CTSM source | [github.com/ESCOMP/CTSM](https://github.com/ESCOMP/CTSM), tag ctsm5.4.049 | public |
| Model output (land and routing history, restarts), all five evaluations and spinups | /glade/campaign/cgd/tss/people/mozhgana/projects/ctsm_conus_runs_archive/&lt;case&gt;/ | NCAR users |
| Analysis output (QC, streamflow metrics, built dashboard, weight cache, case_inputs.csv) | /glade/work/mozhgana/ctsm_conus_output/ | NCAR users |
| streamflow timeseries and routing model crosswalk | Zenodo resource TBA | contact Andy Wood |
| MERIT topology and spatial weights | /glade/work/mizukami/test_mizuRoute/MERIT_basin_nldas/ancillary_data/ntopo_MERIT_Hydro_v1_aug.nc, /glade/work/mizukami/py_mapping/MERIT_Hydro/mapping_v1/spatialweights_nldas0.125_to_merit_nldas.nc | NCAR users |
| Land-use and hillslope inputs | Sean Swenson, /glade/derecho/scratch/swensosc/for_mozhgan/ (scratch); backup copy in /glade/u/home/mozhgana/mywork/ctsm_conus_setup/for_mozhgan/ | NCAR users |
