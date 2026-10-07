(case-hillslope)=
# hillslope

Hillslope roughly doubles the median NSE (0.098 to 0.215) and raises median KGE from 0.246 to 0.349 and median correlation from 0.638 to 0.711. Details: [Results](#results) (Configuration sensitivities).

## Case card

| Item | Value |
|---|---|
| Baseline | see the contrast table in [Results](#results) (Configuration sensitivities) |
| Configuration | [Common setup](#common-setup) (Configuration summary, and the PE layout row of the shared setup table) |
| Setup scripts | setup_hillslope_spinup.sh and setup_hillslope_eval.sh, see [Code and data](#code-and-data) (Scripts) |
| Spinup case | hillslope_on |
| Spinup start | 1980-10-01 |
| Spinup length | 24 yr in 6-yr chunks (STOP_N=6, REST_N=2) |
| Spinup final restart | 2004-10-01 |
| Evaluation run | hillslope_eval |
| RUN_REFCASE / RUN_REFDATE | hillslope_on / 2004-10-01 |
| CTSM finidat | hillslope_on.clm2.r.2004-10-01 |
| mizuRoute fname_state_in | hillslope_on.mizuroute.r.2004-10-01-00000.nc |
| Extra output | QLATFLOWOUT |

## Spinup

**Adequacy checks**

- **Hillslope, last 10 years:** TWS, TOTSOILLIQ and TOTSOILICE drift at 1.0-1.3 times their interannual noise; snow and water table depth converged. The residual soil-moisture drift was accepted.
- **Restart boundaries:** a TOTSOILICE jump at the 1998-10 hillslope segment boundary (+0.56) is far below the median month-to-month change (13.7); it is the freeze-thaw cycle, not a restart artifact.

## Evaluation run

- hillslope_eval: a separate case from hillslope_on, with the restart set copied in, so the spinup case stays untouched; run as STOP_N=6, REST_N=6, RESUBMIT=6, with NTASKS_ROF=-14 (1,792 tasks) (see Issues and fixes).

## Issues and fixes

Note: I forgot to change NTASKS_ROF to -5 for hillslope case. After spinup run, I tried to change it but as mizuRoute restarts record the task count, so hillslope_eval failed to read the hillslope_on restart with NTASKS_ROF=-5 and was rerun with -14 , used the same mizuRoute task count as its spinup.

- The hillslope spinup lost ~6-7 simulated years because REST_N was left unset and defaulted to STOP_N (see [Lessons, caveats and future work](#lessons)).
- **Hillslope with use_init_interp** triggers a build-namelist warning that surfaces as a Perl error; add -ignore_warnings to CLM_BLDNML_OPTS.
- **QLATFLOWOUT exists only with use_hillslope=.true..** Requesting it in other configurations fails.
