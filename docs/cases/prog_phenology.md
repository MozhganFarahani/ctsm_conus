(case-prog-phenology)=
# prog_phenology

prog_phenology lowers skill on all three metrics: median NSE falls to 0.067, KGE to 0.215, and median PBIAS rises to +30.7%. Details: [Results](#results) (Configuration sensitivities).

## Case card

| Item | Value |
|---|---|
| Baseline | see the contrast table in [Results](#results) (Configuration sensitivities) |
| Configuration | [Common setup](#common-setup) (Configuration summary) |
| Setup script | setup_proghenol.sh, see [Code and data](#code-and-data) (Scripts) |
| Spinup start | 1980-10-01 |
| Spinup length | 22 yr |
| Spinup final restart | 2002-10-01 |
| Spinup notes | default finidat ctsm5.4.CMIP7_ciso_ctsm5.3.075_f09_124_HIST.clm2.r.2000-01-01-00000.nc |
| Evaluation run | prog_phenology |
| RUN_REFCASE / RUN_REFDATE | prog_phenology / 2002-10-01 |
| CTSM finidat | from its spinup |
| mizuRoute fname_state_in | prog_phenology.mizuroute.r.2002-10-01-00000.nc |
| Extra output | GPP, NPP, NEE, AR, HR, TOTVEGC, TOTSOMC, TOTECOSYSC |

## Spinup

Carbon pools in prog_phenology are not in equilibrium; Sean Swenson advised this is acceptable because carbon is not evaluated, provided fluxes and hydrology look reasonable.
