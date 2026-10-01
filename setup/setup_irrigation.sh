#!/bin/bash
# setup_irrigation.sh -- create and configure the irrigation_on case: spinup, then eval.
#
# Inputs : setup/ctsm.env (compset, resolution, project). Run from the CIME
#          scripts folder ($CIME_SCRIPTS in ctsm.env), where create_newcase is.
# Outputs: the case folder ./irrigation_on, configured but not built. spinup mode
#          runs create_newcase, xmlchange, case.setup and writes user_nl_clm
#          (irrigate = .true.); eval mode switches it to a hybrid run.
#
# Usage:
#   bash <repo>/setup/setup_irrigation.sh spinup             # create + configure the spinup run
#   bash <repo>/setup/setup_irrigation.sh eval 2002-10-01    # eval run from the spinup's final restart date
#   bash <repo>/setup/setup_irrigation.sh --dry-run          # only write user_nl_clm to a temp folder

# -h / --help prints the header block above
[[ "${1:-}" =~ ^(-h|--help)$ ]] && { sed -n '2,/^$/s/^# \{0,1\}//p' "$0"; exit 0; }

set -e
source "$(dirname "$0")/ctsm.env"   # settings and paths

dry_run=false; [[ "${1:-}" == "--dry-run" ]] && { dry_run=true; shift; }
mode=$1
casename="irrigation_on"

# user_nl_clm: base fields + irrigate=.true. + QIRRIG_* fields
write_user_nl() {
    write_hist_nl "$HIST_FIELDS_1
              'QOUT','QIN',$HIST_FIELDS_2,
              'QIRRIG_FROM_SURFACE','QIRRIG_FROM_GW_UNCONFINED','QIRRIG_FROM_GW_CONFINED',
              'QIRRIG_DRIP','QIRRIG_SPRINKLER','QIRRIG_DEMAND'" \
        "irrigate = .true."
}

if $dry_run; then
    cd "$(dry_run_dir "$casename")"
    write_user_nl
    echo "dry run: wrote $PWD/user_nl_clm"
    exit 0
fi

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

    write_user_nl

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
