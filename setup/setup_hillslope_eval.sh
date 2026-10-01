#!/bin/bash
# setup_hillslope_eval.sh -- create and configure the hillslope eval case (hillslope_eval).
#
# Inputs : setup/ctsm.env (compset, resolution, project, $SEAN_FILES_COPY), the
#          restart date of the hillslope_on spinup. Run from the CIME scripts
#          folder ($CIME_SCRIPTS in ctsm.env), where create_newcase is.
# Outputs: the case folder ./hillslope_eval (hybrid run from hillslope_on),
#          configured but not built; prints the commands that stage the restart.
#
# Usage:
#   bash <repo>/setup/setup_hillslope_eval.sh 2004-10-01    # <RUN_REFDATE>
#   bash <repo>/setup/setup_hillslope_eval.sh --dry-run   # only write user_nl_clm to a temp folder

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

# -h / --help prints the header block above
[[ "${1:-}" =~ ^(-h|--help)$ ]] && { sed -n '2,/^$/s/^# \{0,1\}//p' "$0"; exit 0; }

set -e
source "$(dirname "$0")/ctsm.env"   # settings and paths
dry_run=false; [[ "${1:-}" == "--dry-run" ]] && { dry_run=true; shift; }

SEAN_FILES="$SEAN_FILES_COPY"
hillslope_file="${SEAN_FILES}/hillslope_geo_params_trapezoid_0.125nldas2_FAB.nc"

spinup_case="hillslope_on"
refdate=$1
if ! $dry_run && [ -z "$refdate" ]; then
    echo "USAGE: bash setup_hillslope_eval.sh <RUN_REFDATE, e.g. 2004-10-01>"
    exit 1
fi
casename="hillslope_eval"

# user_nl_clm: control's 44 fields plus QLATFLOWOUT (right after QOUT,QIN) and
# H2OSOI, and the hillslope switches.
write_user_nl() {
    write_hist_nl "$HIST_FIELDS_1
              'QOUT','QIN','QLATFLOWOUT',$HIST_FIELDS_2,'H2OSOI'"
    cat >> user_nl_clm << EOF

hillslope_file = '${hillslope_file}'
use_hillslope = .true.
use_hillslope_routing = .true.
EOF
}

if $dry_run; then
    cd "$(dry_run_dir "$casename")"
    write_user_nl
    echo "dry run: wrote $PWD/user_nl_clm"
    exit 0
fi

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

write_user_nl

echo ""
echo "=========================================================================="
echo "Case created. Since GET_REFCASE=FALSE, you must manually stage the"
echo "reference restart files BEFORE building. Preferred source is the"
echo "archived restart (st_archive should have moved it there already):"
echo ""
echo "  SPINUP_RESTDIR=${ARCHIVE}/${spinup_case}/rest/${refdate}-00000"
echo "  ls \$SPINUP_RESTDIR   # confirm it's not empty before copying"
echo "  cp \$SPINUP_RESTDIR/* ${SCRATCH}/${casename}/run/"
echo ""
echo "If that archive directory is empty (st_archive hasn't run for that"
echo "segment yet), use the live run directory instead:"
echo "  cp ${SCRATCH}/${spinup_case}/run/*${refdate}* \\"
echo "     ${SCRATCH}/${casename}/run/"
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