#!/bin/bash
# setup_control.sh
#
# Run this from: /glade/work/mozhgana/ctsm_conus/cime/scripts
#
#
# Usage:
#   ./setup_control.sh spinup      # create + configure the spinup run
#   bash /glade/u/home/mozhgana/mywork/ctsm_conus_setup/setup_control.sh spinup 
#   ./setup_control.sh eval <RUN_REFDATE>   # create + configure the real eval run,
#                                              using the spinup's final restart date

set -e
source /glade/u/home/mozhgana/mywork/ctsm_conus_setup/ctsm.env

mode=$1
casename="control"

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

    # -- all xmlchanges before case.setup, per documented CTSM workflow --
    ./xmlchange DATM_YR_START=1980
    ./xmlchange DATM_YR_END=2018
    ./xmlchange DATM_YR_ALIGN=1980
    ./xmlchange RUN_TYPE=startup
    ./xmlchange RUN_STARTDATE=1980-01-01
    ./xmlchange CONTINUE_RUN=FALSE
    ./xmlchange STOP_OPTION=nyears
    ./xmlchange STOP_N=22          # validated via site-level drift check (Florida wetland site) --
                                    # see Spinup_Process_Report.docx. 12yrs was NOT enough; 22 was.
    ./xmlchange RESUBMIT=0
    ./xmlchange JOB_QUEUE=main --subgroup case.run
    ./xmlchange JOB_WALLCLOCK_TIME=08:00:00 --subgroup case.run  # 10 years took 90 minutes
    ./xmlchange NTASKS_ROF=-5

    ./case.setup

    # user_nl_clm: base 38-field diagnostic set used throughout the project.
    # NOTE: does NOT include H2OSOI here -- that field can only be added on a
    # fresh startup/hybrid run, not a CONTINUE_RUN continuation. It was added
    # later, on the eval (hybrid) run below, not on this spinup namelist.
    cat >> user_nl_clm << 'EOF'
hist_empty_htapes = .true.
hist_mfilt = 1,365
hist_nhtfrq = 0,-24
hist_fincl1 = 'BTRANMN','H2OSFC','H2OSNO','SNOWDP','ZWT','ZWT_PERCH','FROST_TABLE',
              'TWS','QDRAI','QOVER','QH2OSFC','QDRAI_PERCH','QVEGT','QVEGE','QSOIL',
              'QOUT','QIN','QFLX_SNOW_DRAIN','SOILLIQ','SOILICE','TLAI','TBOT','TSA',
              'TG','TV','TSKIN','FPSN','FSH','EFLX_LH_TOT','EFLX_SOIL_GRND','FGR12',
              'FIRA','FIRE','FSNO','FH2OSFC','FSDS','RAIN','SNOW','TSOI','ALT',
              'QRUNOFF','TOTSOILLIQ','TOTSOILICE','QFLX_EVAP_TOT'
hist_fincl2 = 'BTRANMN','H2OSFC','H2OSNO','SNOWDP','ZWT','ZWT_PERCH','FROST_TABLE',
              'TWS','QDRAI','QOVER','QH2OSFC','QDRAI_PERCH','QVEGT','QVEGE','QSOIL',
              'QOUT','QIN','QFLX_SNOW_DRAIN','SOILLIQ','SOILICE','TLAI','TBOT','TSA',
              'TG','TV','TSKIN','FPSN','FSH','EFLX_LH_TOT','EFLX_SOIL_GRND','FGR12',
              'FIRA','FIRE','FSNO','FH2OSFC','FSDS','RAIN','SNOW','TSOI','ALT',
              'QRUNOFF','TOTSOILLIQ','TOTSOILICE','QFLX_EVAP_TOT'
EOF

    echo "Spinup case created and configured. Next: ./case.build && ./case.submit"
    echo "NOTE: if extending spinup later (CONTINUE_RUN=TRUE), do NOT add new"
    echo "hist_fincl fields -- field count must match the existing restart file."

elif [ "$mode" == "eval" ]; then

    refdate=$2
    if [ -z "$refdate" ]; then
        echo "USAGE: ./setup_control.sh eval <RUN_REFDATE, e.g. 2002-01-01>"
        exit 1
    fi

    cd "$casename"

    # -- all xmlchanges before case.setup --reset --
    ./xmlchange RUN_TYPE=hybrid
    ./xmlchange RUN_REFCASE="$casename"
    ./xmlchange RUN_REFDATE="$refdate"
    ./xmlchange GET_REFCASE=FALSE
    ./xmlchange RUN_STARTDATE=1980-10-01     # water-year aligned, per Andy's question
    ./xmlchange CONTINUE_RUN=FALSE
    ./xmlchange STOP_OPTION=nyears
    ./xmlchange STOP_N=38                    # full NLDAS2 record, 1980-2018
    ./xmlchange RESUBMIT=0
    ./xmlchange JOB_QUEUE=main --subgroup case.run
    ./xmlchange JOB_WALLCLOCK_TIME=12:00:00 --subgroup case.run

    # hybrid start allows changing hist_fincl -- add H2OSOI here (blocked on spinup continuation)
    if ! grep -q "H2OSOI" user_nl_clm; then
        sed -i "s/'QFLX_EVAP_TOT'/'QFLX_EVAP_TOT','H2OSOI'/g" user_nl_clm
        echo "Added H2OSOI to hist_fincl1/hist_fincl2 (only possible on hybrid/startup, not continuation)."
    fi

    ./case.setup --reset

    echo "Eval run configured from spinup restart $refdate."
    echo "Then: ./case.build && ./case.submit"

else
    echo "USAGE: ./setup_control.sh [spinup|eval <RUN_REFDATE>]"
    exit 1
fi
