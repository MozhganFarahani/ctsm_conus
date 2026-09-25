#!/bin/bash
# setup_hillslope_eval.sh
#
# Sets up the hillslope EVAL run (38 years, 1980-2018) in a SEPARATE case
# folder (hillslope_eval), referencing the spinup (hillslope_on) restart
# via a hybrid run -- deliberately NOT reusing hillslope_on's own directory,
# so the original spinup stays untouched if you need to revisit it or run
# a different spinup configuration later.
#
# GET_REFCASE=FALSE (matches your irrigation/landcover eval scripts): the
# reference restart files must be manually copied into this new case's run
# directory before building. Exact commands are printed at the end -- use
# 'cp', never 'mv' or a symlink, so hillslope_on's own files are never at risk.
#
# Run this from: /glade/work/mozhgana/ctsm_conus/cime/scripts
#
# Usage:
#   bash /glade/u/home/mozhgana/mywork/ctsm_conus_setup/setup_hillslope_eval.sh <RUN_REFDATE>
#   e.g.:
#   bash /glade/u/home/mozhgana/mywork/ctsm_conus_setup/setup_hillslope_eval.sh 2004-10-01

set -e
source /glade/u/home/mozhgana/mywork/ctsm_conus_setup/ctsm.env

SEAN_FILES="/glade/u/home/mozhgana/mywork/ctsm_conus_setup/for_mozhgan"
hillslope_file="${SEAN_FILES}/hillslope_geo_params_trapezoid_0.125nldas2_FAB.nc"

spinup_case="hillslope_on"
refdate=$1
if [ -z "$refdate" ]; then
    echo "USAGE: bash setup_hillslope_eval.sh <RUN_REFDATE, e.g. 2004-10-01>"
    exit 1
fi
casename="hillslope_eval"

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
./xmlchange RUN_TYPE=hybrid
./xmlchange RUN_REFCASE="$spinup_case"
./xmlchange RUN_REFDATE="$refdate"
./xmlchange DRV_RESTART_POINTER="rpointer.cpl.${refdate}-00000"  # explicit, per CESM
                                  # tutorial: hybrid runs need this set too, not just plain
                                  # CONTINUE_RUN=TRUE restarts -- easy to miss since
                                  # RUN_REFCASE/RUN_REFDATE alone don't guarantee it.
./xmlchange GET_REFCASE=FALSE
./xmlchange RUN_STARTDATE=1980-10-01
./xmlchange CONTINUE_RUN=FALSE
./xmlchange STOP_OPTION=nyears
./xmlchange STOP_N=6             # same segmenting logic as spinup -- hillslope's throughput
                                  # doesn't change just because it's the eval run now.
./xmlchange REST_OPTION=nyears
./xmlchange REST_N=6
./xmlchange RESUBMIT=6            # 7 total submissions x 6yr = 42yr capacity, covers the
                                  # 38yr eval target with margin.
./xmlchange JOB_QUEUE=main --subgroup case.run
./xmlchange JOB_WALLCLOCK_TIME=08:00:00 --subgroup case.run
# ./xmlchange NTASKS_ROF=-5

./xmlchange --append CLM_BLDNML_OPTS="-ignore_warnings"

./case.setup

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
echo "Case created. Since GET_REFCASE=FALSE, you must manually stage the"
echo "reference restart files BEFORE building. Preferred source is the"
echo "archived restart (st_archive should have moved it there already):"
echo ""
echo "  SPINUP_RESTDIR=/glade/derecho/scratch/mozhgana/archive/${spinup_case}/rest/${refdate}-00000"
echo "  ls \$SPINUP_RESTDIR   # confirm it's not empty before copying"
echo "  cp \$SPINUP_RESTDIR/* /glade/derecho/scratch/mozhgana/${casename}/run/"
echo ""
echo "If that archive directory is empty (st_archive hasn't run for that"
echo "segment yet), use the live run directory instead:"
echo "  cp /glade/derecho/scratch/mozhgana/${spinup_case}/run/*${refdate}* \\"
echo "     /glade/derecho/scratch/mozhgana/${casename}/run/"
echo ""
echo "IMPORTANT: use 'cp', never 'mv' or a symlink -- this guarantees"
echo "hillslope_on's own spinup files are never modified or moved."
echo ""
echo "After copying:"
echo "  1. cat user_nl_clm and confirm hillslope_file shows the actual path."
echo "  2. ./xmlquery RUN_REFCASE,RUN_REFDATE,DRV_RESTART_POINTER -- confirm"
echo "     DRV_RESTART_POINTER='rpointer.cpl.${refdate}-00000' (not blank/wrong)."
echo "  3. ./case.build && ./case.submit"
echo "  4. After the first segment, verify it actually picked up the"
echo "     ${refdate} spinup state (not a cold start) -- e.g. compare an"
echo "     early state variable against hillslope_on's own value at that date."
echo "=========================================================================="