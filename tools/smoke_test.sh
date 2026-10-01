#!/bin/bash
#PBS -N smoke_test
#PBS -q casper
#PBS -l select=1:ncpus=2:mem=40GB
#PBS -l walltime=01:00:00
#PBS -j oe
#
# smoke_test.sh -- run every script in the repo on its smallest input and report pass/fail.
#
# Inputs : model output in $ARCHIVE (setup/ctsm.env): control and hillslope_on, one
#          year (1990, water year 1990 for the daily files); gauge 09040000; the
#          archived cases/<case>/user_nl_clm for the setup dry runs.
# Outputs: $OUTPUT_ROOT/smoke_test/ (emptied at the start): one log per test in
#          logs/, every script's output, and summary.txt. Nothing is written into
#          the repo or into the real output folders.
# A test passes when the command exits 0 and its log has no Traceback or ERROR line.
# The setup dry runs must also match cases/<case>/user_nl_clm (comments and
# whitespace ignored). Exit status: the number of failed tests.
#
# Usage (from the repo root, npl-2026a is activated if needed):
#   bash tools/smoke_test.sh                # on a login node (light reads only)
#   source setup/ctsm.env && qsub -A "$PROJECT" -o "$OUTPUT_ROOT/" tools/smoke_test.sh

[[ "${1:-}" =~ ^(-h|--help)$ ]] && { sed -n '8,/^$/s/^# \{0,1\}//p' "$0"; exit 0; }

set -uo pipefail          # no -e: a failing test is reported, not fatal
cd "${PBS_O_WORKDIR:-$(dirname "$0")/..}"      # repo root
REPO=$PWD
source setup/ctsm.env > /dev/null              # ARCHIVE, OUTPUT_ROOT
if [[ "${CONDA_DEFAULT_ENV:-}" != npl-2026a ]]; then
    module load conda && conda activate npl-2026a
fi
export OMP_NUM_THREADS=1

SMOKE="${OUTPUT_ROOT:?}/smoke_test"
rm -rf "$SMOKE" && mkdir -p "$SMOKE/logs"

# smallest inputs
GAUGE=09040000                         # East Fork Troublesome Creek, CO
YEAR=1990
H0=$ARCHIVE/control/lnd/hist           # control history folders
ROF=$ARCHIVE/control/rof/hist
H1_WY=$H0/control.clm2.h1a.$((YEAR-1))-10-02-00000.nc   # daily file of water year $YEAR

# one-year folders of symlinks, for the scripts that read a whole h0a folder
link_year() {   # $1 = case; prints the folder
    local d=$SMOKE/inputs/$1_h0a_$YEAR
    mkdir -p "$d" && ln -s "$ARCHIVE/$1/lnd/hist/$1.clm2.h0a.$YEAR-"??.nc "$d/" && echo "$d"
}
CTRL_YEAR=$(link_year control)
HILL_YEAR=$(link_year hillslope_on)

: > "$SMOKE/summary.txt"
NFAIL=0
run() {         # $1 = test name, rest = command, run from the repo root
    local name=$1; shift
    local log=$SMOKE/logs/$name.log t0=$SECONDS status=PASS
    (cd "$REPO" && "$@") > "$log" 2>&1 || status=FAIL
    grep -qE "Traceback|ERROR" "$log" && status=FAIL
    [[ $status == FAIL ]] && NFAIL=$((NFAIL+1))
    printf "%-4s %5ds  %s\n" "$status" $((SECONDS-t0)) "$name" | tee -a "$SMOKE/summary.txt"
}

# --- every script prints its usage ---
help_all() {
    local f
    for f in analysis/*/*.py dashboard/build_streamflow_dashboard.py tools/list_case_inputs.py; do
        case $f in analysis/lib/*|analysis/config/*) continue ;; esac
        python "$f" --help > /dev/null || { echo "ERROR: $f --help"; return 1; }
    done
    for f in setup/setup_*.sh tools/capture_cases.sh tools/smoke_test.sh; do
        bash "$f" --help > /dev/null || { echo "ERROR: $f --help"; return 1; }
    done
}
run help help_all

# --- analysis/ ---
run qc_explore python analysis/qc/ctsm_control_explore.py --config control \
    --h0 "$H0/control.clm2.h0a.$YEAR-*.nc" --h1 "$H1_WY" \
    --mizuroute "$ROF/control.mizuroute.h.$YEAR-*.nc" \
    --lnd-in cases/control/CaseDocs/lnd_in --outdir "$SMOKE/qc"
run qc_water_balance python analysis/qc/ctsm_spatial_water_balance.py --config control \
    --h0 "$H0/control.clm2.h0a.$YEAR-*.nc" --outdir "$SMOKE/qc_spatial"
run spinup_hillslope python analysis/spinup/check_hillslope_spinup.py --case hillslope_on \
    --run-dir "$HILL_YEAR" --outdir "$SMOKE/spinup"
run spinup_restart python analysis/spinup/check_restart_discontinuity.py --case hillslope_on \
    --restart-date 1998-10-01 --window-months 2 --outdir "$SMOKE/spinup"
run spinup_drift python analysis/spinup/check_spinup_drift.py --case hillslope_on \
    --years $YEAR $YEAR --outdir "$SMOKE/spinup"
run streamflow_eval python analysis/streamflow/ctsm_streamflow_eval.py --config control \
    --limit 1 --outdir "$SMOKE/streamflow"
run climatology python analysis/climatology/ctsm_climatology_maps.py --rebuild --vars QRUNOFF \
    --hist-dir "$CTRL_YEAR" --outdir "$SMOKE/climatology" --cache "$SMOKE/climatology/clim.nc"
run time_align python analysis/diagnostics/check_time_align.py $GAUGE --config control
run describe_inputs python analysis/diagnostics/describe_inputs.py
# the notebook runs from its own folder (nbconvert's default); OUT_DIR keeps its figures here
run animation_nb env OUT_DIR="$SMOKE/animation" jupyter nbconvert --to notebook --execute \
    --output-dir "$SMOKE/animation" analysis/animation/discharge_map_animation_conus.ipynb

# --- dashboard/ (--no-cache: no test weights in the shared cache) ---
run dashboard python dashboard/build_streamflow_dashboard.py --configs control \
    --test-basins $GAUGE --vars QRUNOFF --no-cache --outdir "$SMOKE/dashboard"

# --- tools/ ---
run list_case_inputs python tools/list_case_inputs.py control --csv "$SMOKE/case_inputs.csv"
run capture_cases bash tools/capture_cases.sh "$SMOKE/capture" control

# --- setup/: dry run of each script, compared with the archived user_nl_clm ---
strip_nl() { grep -v '^[[:space:]]*!' "$1" | tr -d '[:space:]'; }   # no comments, no whitespace
dry_run() {     # $1 = setup script, $2 = case
    DRY_RUN_DIR="$SMOKE/dry_run" bash "setup/$1" --dry-run || return 1
    local new=$SMOKE/dry_run/$2/user_nl_clm
    [[ "$(strip_nl "$new")" == "$(strip_nl "cases/$2/user_nl_clm")" ]] \
        || { echo "ERROR: $new differs from cases/$2/user_nl_clm"; return 1; }
}
run dry_control        dry_run setup_control.sh          control
run dry_irrigation     dry_run setup_irrigation.sh       irrigation_on
run dry_landcover      dry_run setup_landcover.sh        evolving_landcover
run dry_hillslope_on   dry_run setup_hillslope_spinup.sh hillslope_on
run dry_hillslope_eval dry_run setup_hillslope_eval.sh   hillslope_eval
run dry_prog_phenology dry_run setup_proghenol.sh        prog_phenology

# --- PBS scripts: syntax only (they are submitted by hand) ---
pbs_syntax() { local f; for f in analysis/*/*.pbs dashboard/*.pbs; do bash -n "$f" || return 1; done; }
run pbs_syntax pbs_syntax

echo "$NFAIL failed; logs in $SMOKE/logs" | tee -a "$SMOKE/summary.txt"
exit $NFAIL
