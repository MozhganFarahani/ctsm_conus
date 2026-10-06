(common-setup)=
# Common setup

## Shared model setup

All five configurations share one CTSM tag, grid, forcing and routing setup; they differ only in the options listed in the second table and in spinup length and start date (case cards).

**Shared simulation setup**

| Item | Value |
|---|---|
| Model | CTSM (CLM6.0), release tag [ctsm5.4.049](https://github.com/ESCOMP/CTSM/tree/ctsm5.4.049) cloned from ESCOMP/CTSM, coupled to mizuRoute |
| Driver / compiler / machine | NUOPC / Intel / Derecho; analysis on Casper |
| Resolution alias | nldas2_nldas2_rMERIT_mnldas2 |
| Land grid | NLDAS-2 0.125°, 464 x 224 (25-53°N, 235-293°E), 80,439 land cells |
| River network | MERIT-Hydro CONUS (r%MERIT_CONUSmz), 227,247 reaches and catchments |
| Forcing | NLDAS-2 0.125°, 1980-2018 (DATM_YR_START=1980, DATM_YR_END=2018, DATM_YR_ALIGN=1980) |
| Soil layers | 20 layers with a maximum depth of 8.5 m; 20SL_8.5m |
| Parameter tuning | LND_TUNING_MODE=clm6_0_NLDAS2 falls back to clm6_0_GSWP3v1 (no NLDAS-2 tuning exists) |
| Routing | mizuRoute, route_opt=5, topology ntopo_MERITmz_0.125nldas2_cdf5_fill_reorder_c20210625.nc |
| Routing options | bypass_routing_option=direct_to_outlet, qgwl_runoff_option=negative |
| Irrigation options (when on) | limit_irrigation_if_rof_enabled=.false., use_groundwater_irrigation=.false. |
| PE layout | 1,920 PEs. NTASKS_ROF=-5 (640 tasks) for control, irrigation_on, evolving_landcover and prog_phenology; NTASKS_ROF=-14 (1,792 tasks, the config_pes default) for hillslope |

## History output common to all cases

- h0 monthly and h1 daily, one year per file (hist_mfilt = 1,365, hist_nhtfrq = 0,-24).
- Control writes 44 fields: water and energy fluxes, states, and soil profiles (QRUNOFF, QOVER, QDRAI, QFLX_EVAP_TOT, H2OSNO, TOTSOILLIQ, TOTSOILICE, TWS, ZWT and others); H2OSOI is added from the evaluation start.
- 42 fields are common to all five.
- Monthly routed flow (RoutedRunoff, m³/s) and catchment runoff (basRunoff, mm/s) are written for every reach.

Configuration-specific fields: see the Extra output row of each case card under [Cases](#cases).

## Configuration summary

**Configurations**

| Configuration | Compset | Namelist changes from control | Surface data |
|---|---|---|---|
| [control](#case-control) | I2000Clm60SpMizGsNldas (2000_DATM%NLDAS2_CLM60%SP_SICE_SOCN_MIZUROUTE_SGLC_SWAV) | none; irrigate=.false. | default surfdata_0.125nldas2_hist_2000_78pfts_c251022.nc |
| [irrigation_on](#case-irrigation-on) | same as control | irrigate=.true. | same as control |
| [evolving_landcover](#case-evolving-landcover) | HIST_DATM%NLDAS2_CLM60%SP_SICE_SOCN_MIZUROUTE_SGLC_SWAV | flanduse_timeseries (1850-2023); irrigate=.true. (CTSM default with these files; see [evolving_landcover](#case-evolving-landcover)) | Sean Swenson's 1850 surfdata_..._c260813.nc |
| hillslope_eval ([hillslope](#case-hillslope)) | same as control | use_hillslope=.true., use_hillslope_routing=.true., hillslope_file=hillslope_geo_params_trapezoid_0.125nldas2_FAB.nc | same as control |
| [prog_phenology](#case-prog-phenology) | 2000_DATM%NLDAS2_CLM60%BGC_SICE_SOCN_MIZUROUTE_SGLC_SWAV (BGC, CN + methane) | none beyond the compset | same as control |

## Spinup approach

Each configuration was spun up with transient (not cycled) NLDAS2 forcing from an interpolated global restart.

**Method**

- **Initial state:** interpolated from global f09 CMIP7 historical CTSM restarts (use_init_interp=.true.), read from /glade/campaign/cesm/cesmdata/inputdata/lnd/clm2/initdata_esmf/ctsm5.4/. Control used the SP restart and prog_phenology the default BGC restart (see the case card in [control](#case-control) and [prog_phenology](#case-prog-phenology)).
- **Forcing:** the actual 1980-onward NLDAS-2 sequence rather than a repeated cycle.
- **Length:** started at 12 years and extended to 22 after drift checks; hillslope reached 24 years.

## Evaluation approach

Every evaluation is a 38-year hybrid run from 1980-10-01 to 2018-10-01, started from that configuration's spinup restart for both CTSM and mizuRoute.

- **Run type:** RUN_TYPE=hybrid, RUN_STARTDATE=1980-10-01 (water-year start), STOP_N=38 years.
- **Routing state:** mizuRoute reads its own spinup restart (fname_state_in) at the same date as the CTSM finidat. The archived CaseDocs/mizuRoute.control of every evaluation names that restart, so no evaluation was cold-started.
- **Output period:** 456 monthly h0 files (1980-10 to 2018-09) and 38 daily h1 files per configuration.

## Workflow

Each configuration is built by one standalone setup script that sources a shared ctsm.env and runs the standard CIME sequence; every configuration has a separate spinup case and evaluation run.

```{mermaid}
flowchart LR
A["ctsm.env<br/>shared settings"] --> B["setup_config.sh"]
B --> C["create_newcase<br/>xmlchange, user_nl_clm"]
C --> D["case.setup<br/>preview_namelists"]
D --> E["case.build"]
E --> F["case.submit<br/>spinup"]
F --> G["hybrid eval<br/>38 yr"]
G --> H["archive<br/>lnd, rof, rest"]
H --> I["analysis<br/>and dashboard"]
```

The setup script is the single source of truth for a case: it holds the compset, resolution, PE layout, run length, restart settings and the user_nl_clm contents, so a case can be rebuilt from it.
