#!/bin/bash
# setup_irrigation.sh
#
# Run this from: /glade/work/mozhgana/ctsm_conus/cime/scripts
#
# Usage:
#   bash /glade/u/home/mozhgana/mywork/ctsm_conus_setup/setup_irrigation.sh spinup                       # create + configure the spinup run
#   bash /glade/u/home/mozhgana/mywork/ctsm_conus_setup/setup_irrigation.sh eval 2002-10-01              # create + configure the real simulation run,
#                                                                                                        using the spinup's final restart date

set -e
source /glade/u/home/mozhgana/mywork/ctsm_conus_setup/ctsm.env

mode=$1
casename="irrigation_on"

if [ "$mode" == "spinup" ]; then

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
    ./xmlchange RUN_STARTDATE=1980-10-01
    ./xmlchange CONTINUE_RUN=FALSE
    ./xmlchange STOP_OPTION=nyears
    ./xmlchange STOP_N=22          # matches control's validated spinup length -- verify with site-level check
    ./xmlchange RESUBMIT=0
    ./xmlchange JOB_QUEUE=main --subgroup case.run
    ./xmlchange JOB_WALLCLOCK_TIME=05:00:00 --subgroup case.run
    ./xmlchange NTASKS_ROF=-5

    ./case.setup

    # user_nl_clm: base fields + irrigate=.true. + QIRRIG_* fields
    cat >> user_nl_clm << 'EOF'
hist_empty_htapes = .true.
hist_mfilt = 1,365
hist_nhtfrq = 0,-24
irrigate = .true.
hist_fincl1 = 'BTRANMN','H2OSFC','H2OSNO','SNOWDP','ZWT','ZWT_PERCH','FROST_TABLE',
              'TWS','QDRAI','QOVER','QH2OSFC','QDRAI_PERCH','QVEGT','QVEGE','QSOIL',
              'QOUT','QIN','QFLX_SNOW_DRAIN','SOILLIQ','SOILICE','TLAI','TBOT','TSA',
              'TG','TV','TSKIN','FPSN','FSH','EFLX_LH_TOT','EFLX_SOIL_GRND','FGR12',
              'FIRA','FIRE','FSNO','FH2OSFC','FSDS','RAIN','SNOW','TSOI','ALT',
              'QRUNOFF','TOTSOILLIQ','TOTSOILICE','QFLX_EVAP_TOT',
              'QIRRIG_FROM_SURFACE','QIRRIG_FROM_GW_UNCONFINED','QIRRIG_FROM_GW_CONFINED',
              'QIRRIG_DRIP','QIRRIG_SPRINKLER','QIRRIG_DEMAND'
hist_fincl2 = 'BTRANMN','H2OSFC','H2OSNO','SNOWDP','ZWT','ZWT_PERCH','FROST_TABLE',
              'TWS','QDRAI','QOVER','QH2OSFC','QDRAI_PERCH','QVEGT','QVEGE','QSOIL',
              'QOUT','QIN','QFLX_SNOW_DRAIN','SOILLIQ','SOILICE','TLAI','TBOT','TSA',
              'TG','TV','TSKIN','FPSN','FSH','EFLX_LH_TOT','EFLX_SOIL_GRND','FGR12',
              'FIRA','FIRE','FSNO','FH2OSFC','FSDS','RAIN','SNOW','TSOI','ALT',
              'QRUNOFF','TOTSOILLIQ','TOTSOILICE','QFLX_EVAP_TOT',
              'QIRRIG_FROM_SURFACE','QIRRIG_FROM_GW_UNCONFINED','QIRRIG_FROM_GW_CONFINED',
              'QIRRIG_DRIP','QIRRIG_SPRINKLER','QIRRIG_DEMAND'
EOF

    echo "Spinup case created and configured. Next: ./case.build && ./case.submit"

elif [ "$mode" == "eval" ]; then

    refdate=$2
    if [ -z "$refdate" ]; then
        echo "USAGE: ./setup_irrigation.sh eval <RUN_REFDATE, e.g. 2002-01-01>"
        exit 1
    fi

    cd "$casename"

    ./xmlchange RUN_TYPE=hybrid
    ./xmlchange RUN_REFCASE="$casename"
    ./xmlchange RUN_REFDATE="$refdate"
    ./xmlchange GET_REFCASE=FALSE
    ./xmlchange RUN_STARTDATE=1980-10-01
    ./xmlchange CONTINUE_RUN=FALSE
    ./xmlchange STOP_OPTION=nyears
    ./xmlchange STOP_N=38
    ./xmlchange RESUBMIT=0
    ./xmlchange JOB_WALLCLOCK_TIME=12:00:00 --subgroup case.run

    echo "Eval run configured from spinup restart $refdate."
    echo "Add H2OSOI or other new fields to user_nl_clm now if desired (hybrid allows this)."
    echo "Then: ./case.setup --reset && ./case.build && ./case.submit"

else
    echo "USAGE: ./setup_irrigation.sh [spinup|eval <RUN_REFDATE>]"
    exit 1
fi
