(case-control)=
# control

The control reaches a median monthly NSE of 0.106 across 2,257 gauges, with the best regional skill in the Southeast and the Ohio, Tennessee and Arkansas-White-Red basins and large over-prediction in the Missouri basin. Details: [Results](#results) (Control baseline).

## Case card

| Item | Value |
|---|---|
| Configuration | [Common setup](#common-setup) (Configuration summary) |
| Setup script | setup_control.sh, see [Code and data](#code-and-data) (Scripts) |
| Spinup start | 1980-01-01 |
| Spinup length | 22 yr (3 x 4-yr chunks + 10-yr continuation) |
| Spinup final restart | 2002-01-01 |
| Spinup notes | startup run; finidat ctsm5.4.CMIP7_ciso_ctsm5.3.075_SP_f09_127_HIST.clm2.r.2000-01-01-00000.nc (SP) |
| Pass 1 (extended spinup) | 1980-10-01, 38 yr, final restart 2018-10-01; hybrid from the 2002-01-01 restart; kept in control_eval_run1_backup; its end restart starts pass 2 |
| Evaluation run | control (pass 2) |
| RUN_REFCASE / RUN_REFDATE | control / 2018-10-01 |
| CTSM finidat | control.clm2.r.2018-10-01 |
| mizuRoute fname_state_in | control.mizuroute.r.2018-10-01-00000\.nc |
| Extra output | the 44 control fields, see [Common setup](#common-setup) (History output common to all cases) |

## Spinup

Control was run in three steps. As I started with this case, I wasn't sure if the spinup was enough or not, so pass 1 became extra spinup:

1. **Spinup:** 22 years, 1980-01-01 to 2002-01-01, ending in the 2002-01-01 restart.
2. **Pass 1:** a 38-year hybrid evaluation (1980-10-01 to 2018-10-01) started from that 2002-01-01 restart; kept in control_eval_run1_backup and not used.
3. **Pass 2:** the same 38 years again, started from pass 1's 2018-10-01 restart. This is the control used in this note and the dashboard; its initial state has 60 years of NLDAS2 forcing behind it (22 + 38).

**Adequacy checks**

- **Domain mean:** across eight water-year fields, soil temperature changed least (0.02%) over the final years of the control spinup.
- **Site drift, control** (mean of the last 2 years vs the 2 before): TOTSOILLIQ −0.12% (south Florida), −4.56% (Yuma, AZ), −1.92% (Pacific Northwest); water table depth +5.42% in the Pacific Northwest.
- **Interior wetland check** (Atchafalaya, 30.5°N, 268.5°E): TOTSOILLIQ stays within ~3,100-3,850 kg/m² with no trend over the evaluation run; drift +1.25%.

**A forcing artifact, not slow equilibration.** The south Florida site looked slow to equilibrate, with its water table pinned at the 8.6 m floor. It is an isolated coastal land cell where NLDAS2 precipitation is near zero (~1.8e-09 mm/s in June 1985), so it was replaced by the Atchafalaya site as the wetland test.
