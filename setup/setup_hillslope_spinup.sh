#!/bin/bash
# setup_hillslope_spinup.sh
#
# Consolidated hillslope SPINUP setup -- everything actually needed, based
# on troubleshooting during initial setup (Sep 2026). Each non-obvious
# setting below is commented with why it's there.
#
# Run this from: /glade/work/mozhgana/ctsm_conus/cime/scripts
#
# Usage:
#   bash /glade/u/home/mozhgana/mywork/ctsm_conus_setup/setup_hillslope_spinup.sh

set -e
source /glade/u/home/mozhgana/mywork/ctsm_conus_setup/ctsm.env

SEAN_FILES="/glade/u/home/mozhgana/mywork/ctsm_conus_setup/for_mozhgan"
hillslope_file="${SEAN_FILES}/hillslope_geo_params_trapezoid_0.125nldas2_FAB.nc"
casename="hillslope_on"

./create_newcase \
    --case "$casename" \
    --compset "$COMPSET_SP" \
    --driver "$DRIVER" \
    --compiler "$COMPILER" \
    --res "$RES" \
    --machine "$MACHINE" \
    --project "$PROJECT" \
    --run-unsupported

cd "$casename"

./xmlchange DATM_YR_START=1980
./xmlchange DATM_YR_END=2018
./xmlchange DATM_YR_ALIGN=1980
./xmlchange RUN_TYPE=startup
./xmlchange RUN_STARTDATE=1980-10-01   # water-year start -- matches control/irrigation/landcover.
                                        # (First attempt used 1980-01-01 -- wrong, fixed here.)
./xmlchange CONTINUE_RUN=FALSE
./xmlchange STOP_OPTION=nyears
./xmlchange STOP_N=6            # SEGMENT length, not the full 22yr target. Hillslope's
                                 # multi-column hydrology runs at ~6-7 sim-years per 8hr
                                 # walltime -- roughly 20-30x slower than control/irrigation/
                                 # landcover's ~140-165 sim-years/day. A single 22yr
                                 # submission will NOT finish in one job; don't set this to 22.
./xmlchange REST_OPTION=nyears
./xmlchange REST_N=2            # Checkpoint every 2 years. Do NOT leave this at its default
                                 # (which equals STOP_N) -- that means the ONLY restart
                                 # checkpoint is written at the very end of the segment, so a
                                 # walltime-killed job has nothing to resume from. This exact
                                 # mistake cost ~7 years of unrecoverable compute on the first
                                 # real attempt.
./xmlchange RESUBMIT=4           # 5 total submissions x 6yr = 30yr capacity -- comfortably
                                 # covers the 22yr target with margin (the equilibration check,
                                 # check_hillslope_spinup.py, may suggest running a bit past 22
                                 # if some state variables haven't fully settled). Raise this
                                 # if you want more automatic segments without checking in.
./xmlchange JOB_QUEUE=main --subgroup case.run
./xmlchange JOB_WALLCLOCK_TIME=08:00:00 --subgroup case.run
./xmlchange NTASKS_ROF=-5       # Matches irrigation/landcover configs -- this was missed on
                                 # the first hillslope attempt, adding it here for consistency.

# use_hillslope + use_init_interp together trigger a WARNING (not an error):
# all hillslope columns in a gridcell start from identical interpolated
# values. Expected for a fresh spinup -- the whole point of running it
# forward is to let columns differentiate -- but must be acknowledged or
# build-namelist fails outright.
./xmlchange --append CLM_BLDNML_OPTS="-ignore_warnings"

./case.setup

# hist_fincl1/2: control's full 44-variable list, PLUS QLATFLOWOUT (the one
# field Sean confirmed hillslope needs beyond control's set -- it's
# conditionally registered only when use_hillslope=.true.). QOUT/QIN/H2OSOI
# are control's fields, kept for apples-to-apples comparison -- these got
# accidentally dropped in an earlier draft and were restored.
cat >> user_nl_clm << EOF
hist_empty_htapes = .true.
hist_mfilt = 1,365
hist_nhtfrq = 0,-24
hist_fincl1 = 'BTRANMN','H2OSFC','H2OSNO','SNOWDP','ZWT','ZWT_PERCH','FROST_TABLE',
              'TWS','QDRAI','QOVER','QH2OSFC','QDRAI_PERCH','QVEGT','QVEGE','QSOIL',
              'QOUT','QIN','QLATFLOWOUT','QFLX_SNOW_DRAIN','SOILLIQ','SOILICE','TLAI',
              'TBOT','TSA','TG','TV','TSKIN','FPSN','FSH','EFLX_LH_TOT','EFLX_SOIL_GRND',
              'FGR12','FIRA','FIRE','FSNO','FH2OSFC','FSDS','RAIN','SNOW','TSOI','ALT',
              'QRUNOFF','TOTSOILLIQ','TOTSOILICE','QFLX_EVAP_TOT','H2OSOI'
hist_fincl2 = 'BTRANMN','H2OSFC','H2OSNO','SNOWDP','ZWT','ZWT_PERCH','FROST_TABLE',
              'TWS','QDRAI','QOVER','QH2OSFC','QDRAI_PERCH','QVEGT','QVEGE','QSOIL',
              'QOUT','QIN','QLATFLOWOUT','QFLX_SNOW_DRAIN','SOILLIQ','SOILICE','TLAI',
              'TBOT','TSA','TG','TV','TSKIN','FPSN','FSH','EFLX_LH_TOT','EFLX_SOIL_GRND',
              'FGR12','FIRA','FIRE','FSNO','FH2OSFC','FSDS','RAIN','SNOW','TSOI','ALT',
              'QRUNOFF','TOTSOILLIQ','TOTSOILICE','QFLX_EVAP_TOT','H2OSOI'

hillslope_file = '${hillslope_file}'
use_hillslope = .true.
use_hillslope_routing = .true.
EOF

echo ""
echo "=========================================================================="
echo "Case created and configured. Before building:"
echo "  1. cat user_nl_clm and confirm hillslope_file shows the actual path,"
echo "     not literal '\${...}' text."
echo "  2. ./preview_namelists && grep -E 'fsurdat|hillslope_file|use_hillslope' \\"
echo "     CaseDocs/lnd_in -- confirm hillslope_file resolves correctly and"
echo "     fsurdat matches control's (it's intentionally not set explicitly"
echo "     here -- control never set it either, and it still resolved right)."
echo "  3. ./xmlquery RUN_STARTDATE,REST_OPTION,REST_N,RESUBMIT,NTASKS_ROF"
echo "     -- confirm 1980-10-01 / nyears / 2 / 4 / -5."
echo "  4. ./case.build && ./case.submit"
echo "  5. Once running, verify QLATFLOWOUT actually appears in the lnd.log"
echo "     master field list (grep -A 2000 'MASTER FIELD' lnd.log.* | grep LATFLOW)."
echo ""
echo "IF a segment ever gets killed by walltime WITHOUT completing cleanly"
echo "(check the job's log for a normal stop vs. an abrupt kill), the next"
echo "resubmission may need DRV_RESTART_POINTER set explicitly:"
echo "  ./xmlquery DRV_RESTART_POINTER"
echo "  cat run/rpointer.lnd.<latest-date>  # confirm which restart actually exists"
echo "  ./xmlchange DRV_RESTART_POINTER='rpointer.cpl.<latest-date>-00000'"
echo "This is a CESM3-specific requirement -- CONTINUE_RUN=TRUE alone does not"
echo "guarantee it resumes from the right date if the last stop wasn't clean."
echo "=========================================================================="
