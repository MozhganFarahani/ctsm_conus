#!/bin/bash
#
# Run this from: /glade/work/mozhgana/ctsm_conus/cime/scripts
# (shared worktree with evolving_landcover -- this config needs a custom
#  compset added to config_compsets.xml, which is why it's NOT built
#  directly in ctsm_conus like irrigation/hillslope)
#
# ============================================================================
# No existing compset combines BGC (prognostic phenology) with our
# NLDAS2/mizuRoute setup -- this uses a custom compset longname directly:
#   2000_DATM%NLDAS2_CLM60%BGC_SICE_SOCN_MIZUROUTE_SGLC_SWAV
#
# Per Sean (Slack + email, Sep 2026):
#   - The NLDAS domain isn't commonly used for carbon-cycle work, so there's
#     no existing spun-up BGC initial condition file for it. The DEFAULT
#     finidat (an interpolated global f09 CMIP7 restart) is fine to use as-is
#     -- soil carbon won't be in equilibrium, but that's expected and OK
#     since carbon dynamics aren't what this config is evaluating.
#   - No separate carbon-specific spin-up procedure needed -- just the same
#     hydrology-focused spinup as the other configs. "As long as the fluxes
#     and hydrology look ok, you should be fine."
#   --> finidat is intentionally NOT set below -- letting it resolve to the
#       default is the correct, confirmed choice, not an oversight.
#
# Throughput measured via a 1-year test (Sep 2026): 00:17:53 wall for 1 year,
# ~80 sim-years/day -- slower than control's ~140-165/day (BGC's carbon-
# nitrogen cycling adds real per-timestep cost) but nowhere near hillslope's
# ~7-8x slowdown. Real measured 22yr spinup: 5.55hr, ~95 sim-years/day --
# 22 years fits comfortably in one submission at this rate.
#
# Usage:
#bash /glade/u/home/mozhgana/mywork/ctsm_conus_setup/setup_proghenol.sh spinup  # step 1: create + configure spinup    
#bash /glade/u/home/mozhgana/mywork/ctsm_conus_setup/setup_proghenol.sh eval <RUN_REFDATE>      # step 2: real eval run

# bash /glade/u/home/mozhgana/mywork/ctsm_conus_setup/setup_proghenol.sh eval 2002-10-01
set -e
source /glade/u/home/mozhgana/mywork/ctsm_conus_setup/ctsm.env

mode=$1
casename="prog_phenology"
compset_longname="2000_DATM%NLDAS2_CLM60%BGC_SICE_SOCN_MIZUROUTE_SGLC_SWAV"

if [ "$mode" == "spinup" ]; then

    ./create_newcase \
        --case "$casename" \
        --compset "$compset_longname" \
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
    ./xmlchange STOP_N=22            # full spinup length, matches control/irrigation/
                                     # landcover -- confirmed fits in one submission at
                                     # this config's measured throughput.
    ./xmlchange REST_OPTION=nyears
    ./xmlchange REST_N=6              # matches what was actually run (see timing log) --
                                     # periodic checkpoints, cheap insurance against a
                                     # crash/system issue unrelated to walltime sizing.
    ./xmlchange RESUBMIT=0            # STOP_N=22 IS the full spinup target, not a per-segment
                                     # chunk -- RESUBMIT fires unconditionally after a
                                     # successful completion, so RESUBMIT=1 here would trigger
                                     # an UNWANTED extra 22-year continuation (years 22-44)
                                     # once this run finishes, wasting significant compute.
                                     # (This was wrong in an earlier version of this script --
                                     # caught by questioning the walltime sizing before
                                     # submitting.) 12hr walltime gives ~5.4hr margin over the
                                     # ~6.6hr estimate from the 1yr timing test -- comfortable
                                     # for a single submission.
    ./xmlchange JOB_QUEUE=main --subgroup case.run
    ./xmlchange JOB_PRIORITY=premium

    ./xmlchange JOB_WALLCLOCK_TIME=12:00:00 --subgroup case.run   # ~6.6hr needed + margin
    ./xmlchange NTASKS_ROF=-5

    ./case.setup

    # finidat intentionally NOT set here -- see header notes. This is the
    # confirmed-correct choice per Sean, not a missing setting.
    cat >> user_nl_clm << 'EOF'
hist_empty_htapes = .true.
hist_mfilt = 1,365
hist_nhtfrq = 0,-24
hist_fincl1 = 'BTRANMN','H2OSFC','H2OSNO','SNOWDP','ZWT','ZWT_PERCH','FROST_TABLE',
              'TWS','QDRAI','QOVER','QH2OSFC','QDRAI_PERCH','QVEGT','QVEGE','QSOIL',
              'QOUT','QIN','QFLX_SNOW_DRAIN','SOILLIQ','SOILICE','TLAI','TBOT','TSA',
              'TG','TV','TSKIN','FPSN','FSH','EFLX_LH_TOT','EFLX_SOIL_GRND','FGR12',
              'FIRA','FIRE','FSNO','FH2OSFC','FSDS','RAIN','SNOW','TSOI','ALT',
              'QRUNOFF','TOTSOILLIQ','TOTSOILICE','QFLX_EVAP_TOT','H2OSOI',
              'GPP','NPP','NEE','TOTECOSYSC','TOTVEGC','TOTSOMC','AR','HR'
hist_fincl2 = 'BTRANMN','H2OSFC','H2OSNO','SNOWDP','ZWT','ZWT_PERCH','FROST_TABLE',
              'TWS','QDRAI','QOVER','QH2OSFC','QDRAI_PERCH','QVEGT','QVEGE','QSOIL',
              'QOUT','QIN','QFLX_SNOW_DRAIN','SOILLIQ','SOILICE','TLAI','TBOT','TSA',
              'TG','TV','TSKIN','FPSN','FSH','EFLX_LH_TOT','EFLX_SOIL_GRND','FGR12',
              'FIRA','FIRE','FSNO','FH2OSFC','FSDS','RAIN','SNOW','TSOI','ALT',
              'QRUNOFF','TOTSOILLIQ','TOTSOILICE','QFLX_EVAP_TOT','H2OSOI',
              'GPP','NPP','NEE','TOTECOSYSC','TOTVEGC','TOTSOMC','AR','HR'
EOF

    echo ""
    echo "=========================================================================="
    echo "Case created and configured. Before building:"
    echo "  1. ./xmlquery STOP_N,REST_OPTION,REST_N,RESUBMIT,JOB_PRIORITY"
    echo "     -- confirm 22 / nyears / 6 / 0 / premium."
    echo "  2. ./preview_namelists && grep finidat CaseDocs/lnd_in"
    echo "     -- confirm it's the SAME f09 CMIP7 default as before (expected,"
    echo "        confirmed correct by Sean), not blank/broken."
    echo "  3. ./case.build && ./case.submit"
    echo "  4. Track actual wall-clock vs. the ~6.6hr estimate once it's running --"
    echo "     if soil carbon spin-up cost grows over the run (untested), this"
    echo "     could take longer than the 1yr test suggested."
    echo "=========================================================================="

elif [ "$mode" == "eval" ]; then

    refdate=$2
    if [ -z "$refdate" ]; then
        echo "USAGE: ./setup_proghenol.sh eval <RUN_REFDATE, e.g. 2002-10-01>"
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
    ./xmlchange STOP_N=38             # full eval length, NOT a per-segment chunk --
                                      # RESUBMIT stays 0 for the same reason it does in
                                      # spinup (see below).
    ./xmlchange RESUBMIT=0             # STOP_N=38 IS the full eval target. RESUBMIT fires
                                      # unconditionally on a SUCCESSFUL completion (it does
                                      # NOT fire on a walltime kill), so RESUBMIT=1 here would
                                      # risk an unwanted extra 38-year continuation if this
                                      # run finishes cleanly -- same lesson as the spinup.
                                      # If walltime IS exceeded, there's no automatic
                                      # resubmit either way -- you'd notice via qstat/log and
                                      # manually switch to CONTINUE_RUN=TRUE.
    ./xmlchange JOB_WALLCLOCK_TIME=12:00:00 --subgroup case.run
    # TIMING: prog_phenology's actual measured spinup rate (22yr in 5.546hr, the real
    # full-run number, not the shorter 1yr test) projects to ~9.6hr needed for 38 years --
    # only ~25% margin at 12hr walltime. This is noticeably tighter than the spinup's own
    # buffer. If a longer walltime queue/allocation is available, consider bumping this up;
    # otherwise, keep an eye on it via qstat once submitted rather than assuming it's fine.

    ./case.setup --reset

    echo ""
    echo "Eval run configured from spinup restart $refdate."
    echo "hist_fincl1/2 (including H2OSOI and the carbon variables) carry over"
    echo "from the case's existing user_nl_clm -- add more fields now if desired"
    echo "(hybrid allows this) before building."
    echo ""
    echo "Before building:"
    echo "  1. ./xmlquery RUN_REFCASE,RUN_REFDATE,STOP_N,RESUBMIT,JOB_WALLCLOCK_TIME"
    echo "     -- confirm prog_phenology / $refdate / 38 / 0 / 12:00:00."
    echo "  2. ./case.build && ./case.submit"
    echo "  3. Given the tighter margin noted above, check qstat partway through"
    echo "     rather than assuming it'll finish cleanly."

else
    echo "USAGE: bash setup_proghenol.sh [spinup|eval <RUN_REFDATE>]"
    exit 1
fi