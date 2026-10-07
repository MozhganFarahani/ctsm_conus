(case-irrigation-on)=
# irrigation_on

Irrigation lowers the median NSE slightly (0.098 to 0.095) and raises the median PBIAS from +13.9% to +15.2%. Details: [Results](#results) (Configuration sensitivities).

## Case card

| Item | Value |
|---|---|
| Baseline | see the contrast table in [Results](#results) (Configuration sensitivities) |
| Configuration | [Common setup](#common-setup) (Configuration summary, and the Irrigation options row of the shared setup table) |
| Setup script | setup_irrigation.sh, see [Code and data](#code-and-data) (Scripts) |
| Spinup start | 1980-01-01 |
| Spinup length | 22 yr |
| Spinup final restart | 2002-01-01 |
| Evaluation run | irrigation_on |
| RUN_REFCASE / RUN_REFDATE | irrigation_on / 2002-01-01 |
| CTSM finidat | irrigation_on.clm2.r.2002-01-01 |
| mizuRoute fname_state_in | irrigation_on.mizuroute.r.2002-01-01-00000.nc |
| Extra output | QIRRIG_\* |

## Issues and fixes

- **-irrig on in CLM_BLDNML_OPTS is rejected** ("Unknown option: irrig"). Set irrigate=.true. in user_nl_clm instead.
