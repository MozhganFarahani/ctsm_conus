#!/bin/bash
# setup_control.sh -- create and configure the control case: spinup, then eval.
#
# Inputs : setup/ctsm.env (compset, resolution, project). Run from the CIME
#          scripts folder ($CIME_SCRIPTS in ctsm.env), where create_newcase is.
# Outputs: the case folder ./control, configured but not built. spinup mode runs
#          create_newcase, xmlchange, case.setup and writes user_nl_clm; eval mode
#          switches the same case to a hybrid run from the spinup restart.
#
# Usage:
#   bash <repo>/setup/setup_control.sh spinup             # create + configure the spinup run
#   bash <repo>/setup/setup_control.sh eval 2002-01-01    # eval run from the spinup's final restart date
#   bash <repo>/setup/setup_control.sh --dry-run          # only write the final user_nl_clm to a temp folder

# -h / --help prints the header block above
[[ "${1:-}" =~ ^(-h|--help)$ ]] && { sed -n '2,/^$/s/^# \{0,1\}//p' "$0"; exit 0; }

set -e
source "$(dirname "$0")/ctsm.env"   # settings and paths

dry_run=false; [[ "${1:-}" == "--dry-run" ]] && { dry_run=true; shift; }
mode=$1
casename="control"

# user_nl_clm: base 44-field diagnostic set used throughout the project.
# NOTE: does NOT include H2OSOI here -- that field can only be added on a
# fresh startup/hybrid run, not a CONTINUE_RUN continuation. It was added
# later, on the eval (hybrid) run (add_h2osoi), not on the spinup namelist.
write_user_nl() {
    write_hist_nl "$HIST_FIELDS_1
              'QOUT','QIN',$HIST_FIELDS_2"
}
add_h2osoi() {
    sed -i "s/'QFLX_EVAP_TOT'/'QFLX_EVAP_TOT','H2OSOI'/g" user_nl_clm
}

if $dry_run; then   # spinup namelist + the eval change = what the case ends with
    cd "$(dry_run_dir "$casename")"
    write_user_nl
    add_h2osoi
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

    write_user_nl

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
        add_h2osoi
        echo "Added H2OSOI to hist_fincl1/hist_fincl2 (only possible on hybrid/startup, not continuation)."
    fi

    ./case.setup --reset

    echo "Eval run configured from spinup restart $refdate."
    echo "Then: ./case.build && ./case.submit"

else
    echo "USAGE: ./setup_control.sh [spinup|eval <RUN_REFDATE>]"
    exit 1
fi
