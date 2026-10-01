#!/bin/bash
# check_landcover_irrigate.sh -- which irrigate value does build-namelist pick for
# the evolving_landcover setup? (diagnostic; no build, no submit)
#
# Inputs : setup/ctsm.env, $SEAN_FILES_COPY (the land-cover files), the control,
#          irrigation_on and evolving_landcover cases (read only).
# Outputs: throwaway cases ./lcchk_asis and ./lcchk_off and a report on stdout.
#
# Usage (from $CIME_SCRIPTS):
#   bash <repo>/setup/check_landcover_irrigate.sh            # create both test cases + report
#   bash <repo>/setup/check_landcover_irrigate.sh report     # just re-print the report
#   bash <repo>/setup/check_landcover_irrigate.sh clean      # delete the test cases

# Why does evolving_landcover have irrigate = .true. when setup_landcover.sh
# never sets it?
#
# Creates throwaway cases IDENTICAL to setup_landcover.sh (spinup path only),
# runs ./preview_namelists, and reports what CTSM's build-namelist decided.
# No ./case.build, no ./case.submit -- this takes minutes and burns no core
# hours. Run on Derecho.
#
# Three cases are compared:
#   lcchk_asis     exactly your setup_landcover.sh  -> what IS the default?
#   lcchk_off      same + explicit irrigate=.false. -> can it be overridden?
#   (plus your existing control/irrigation_on lnd_in, read-only)
#
# Interpretation:
#   asis = .true.   -> the default comes from the 1850 fsurdat /
#                      flanduse_timeseries, not from anything you wrote.
#                      Nothing to fix in your script; it is a CTSM default,
#                      and the question becomes whether to keep it.
#   asis = .false.  -> the default is OFF, so the .true. in your production
#                      run came from somewhere else in that case directory,
#                      and that case needs investigating.

# -h / --help prints the header block above
[[ "${1:-}" =~ ^(-h|--help)$ ]] && { sed -n '2,/^$/s/^# \{0,1\}//p' "$0"; exit 0; }

set -e
source "$(dirname "$0")/ctsm.env"   # settings and paths
SETUP_DIR="$(cd "$(dirname "$0")" && pwd)"   # setup_*.sh live next to this script

compset_longname="HIST_DATM%NLDAS2_CLM60%SP_SICE_SOCN_MIZUROUTE_SGLC_SWAV"
SEAN_FILES="$SEAN_FILES_COPY"
FLANDUSE="${SEAN_FILES}/landuse.timeseries_0.125nldas2_hist_1850-2023_78pfts_c260813.nc"
FSURDAT="${SEAN_FILES}/surfdata_0.125nldas2_hist_1850_78pfts_c260813.nc"

SCRATCH_ROOT="$SCRATCH"
CASES="lcchk_asis lcchk_off"

# --------------------------------------------------------------- helpers
find_lnd_in() {   # $1 = case name; CaseDocs first, then the run directory
    local c=$1
    for p in "./$c/CaseDocs/lnd_in" "${SCRATCH_ROOT}/$c/run/lnd_in"; do
        [[ -f "$p" ]] && { echo "$p"; return; }
    done
}

show() {          # $1 = label, $2 = path to an lnd_in
    local label=$1 f=$2
    if [[ -z "$f" || ! -f "$f" ]]; then
        printf "  %-16s  (lnd_in not found)\n" "$label"
        return
    fi
    local irr fs fl
    irr=$(grep -iE "^ *irrigate" "$f" | head -1 | sed 's/.*= *//;s/ *$//')
    fs=$(grep -iE "^ *fsurdat" "$f" | head -1 | sed "s|.*/||;s/'//g")
    fl=$(grep -iE "^ *flanduse_timeseries" "$f" | head -1 | sed "s|.*/||;s/'//g")
    printf "  %-16s  irrigate = %-10s\n" "$label" "${irr:-<absent>}"
    printf "  %-16s  fsurdat  = %s\n" "" "${fs:-<none>}"
    [[ -n "$fl" ]] && printf "  %-16s  flanduse = %s\n" "" "$fl"
}

report() {
    echo ""
    echo "============================================================"
    echo " What build-namelist decided"
    echo "============================================================"
    echo ""
    echo "-- your production cases (read-only) --"
    for c in control irrigation_on evolving_landcover; do
        show "$c" "$(find_lnd_in "$c")"
    done
    echo ""
    echo "-- test cases --"
    show "lcchk_asis" "$(find_lnd_in lcchk_asis)"
    show "lcchk_off"  "$(find_lnd_in lcchk_off)"
    echo ""
    echo "-- did you ever set irrigate yourself? --"
    grep -n -i "irrigate" "$SETUP_DIR"/setup_*.sh \
        2>/dev/null || echo "  (not mentioned in any setup_*.sh)"
    echo ""
    echo "-- is it in the production case's user_nl_clm? --"
    for c in control irrigation_on evolving_landcover; do
        if [[ -f "./$c/user_nl_clm" ]]; then
            printf "  %-20s %s\n" "$c:" \
                "$(grep -i irrigate "./$c/user_nl_clm" || echo '<not set by you>')"
        fi
    done
    echo ""
    echo "READ IT THIS WAY"
    echo "  lcchk_asis irrigate = .true.   -> CTSM default from the 1850"
    echo "     fsurdat / flanduse_timeseries. Your script is fine; decide"
    echo "     whether to keep irrigation on for physical consistency."
    echo "  lcchk_asis irrigate = .false.  -> the default is OFF, so the"
    echo "     .true. in evolving_landcover came from that case directory."
    echo "  lcchk_off  irrigate = .false.  -> the override works, so a"
    echo "     clean land-cover-only run is one line away."
    echo ""
}

# --------------------------------------------------------------- modes
if [[ "$1" == "report" ]]; then report; exit 0; fi

if [[ "$1" == "clean" ]]; then
    for c in $CASES; do
        rm -rf "./$c" "${SCRATCH_ROOT}/$c"
        echo "removed $c"
    done
    exit 0
fi

for c in $CASES; do
    [[ -d "./$c" ]] && { echo "ERROR: ./$c exists. Run '$0 clean' first."; exit 1; }
done

for c in $CASES; do
    echo ""
    echo "### creating $c ###"

    # identical to setup_landcover.sh spinup
    ./create_newcase \
        --case "$c" \
        --compset "$compset_longname" \
        --driver "$DRIVER" \
        --compiler "$COMPILER" \
        --res "$RES" \
        --machine "$MACHINE" \
        --project "$PROJECT" \
        --run-unsupported

    pushd "$c" > /dev/null

    ./xmlchange DATM_YR_START=1980
    ./xmlchange DATM_YR_END=2018
    ./xmlchange DATM_YR_ALIGN=1980
    ./xmlchange RUN_TYPE=startup
    ./xmlchange RUN_STARTDATE=1980-10-01
    ./xmlchange CONTINUE_RUN=FALSE
    ./xmlchange STOP_OPTION=nyears
    ./xmlchange STOP_N=22
    ./xmlchange RESUBMIT=0

    ./case.setup

    cat >> user_nl_clm << EOF
hist_empty_htapes = .true.
hist_mfilt = 1,365
hist_nhtfrq = 0,-24
hist_fincl1 = 'QRUNOFF','QFLX_EVAP_TOT','RAIN','SNOW','H2OSNO'
flanduse_timeseries = '${FLANDUSE}'
fsurdat = '${FSURDAT}'
EOF

    # the only difference between the two test cases
    if [[ "$c" == "lcchk_off" ]]; then
        echo "irrigate = .false." >> user_nl_clm
    fi

    # generates CaseDocs/lnd_in without building
    ./preview_namelists

    popd > /dev/null
done

report
echo "Delete the test cases when done:  $0 clean"
