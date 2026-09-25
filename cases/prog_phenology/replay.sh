#!/bin/bash

set -e

# Created 2026-09-18 09:53:40

CASEDIR="/glade/work/mozhgana/ctsm_conus/cime/scripts/prog_phenology"

/glade/work/mozhgana/ctsm_conus/cime/scripts/create_newcase --case prog_phenology --compset 2000_DATM%NLDAS2_CLM60%BGC_SICE_SOCN_MIZUROUTE_SGLC_SWAV --driver nuopc --compiler intel --res nldas2_nldas2_rMERIT_mnldas2 --machine derecho --project P93300041 --run-unsupported

cd "${CASEDIR}"

./xmlchange DATM_YR_START=1980

./xmlchange DATM_YR_END=2018

./xmlchange DATM_YR_ALIGN=1980

./xmlchange RUN_TYPE=startup

./xmlchange RUN_STARTDATE=1980-10-01

./xmlchange CONTINUE_RUN=FALSE

./xmlchange STOP_OPTION=nyears

./xmlchange STOP_N=22

./xmlchange REST_OPTION=nyears

./xmlchange REST_N=6

./xmlchange RESUBMIT=0

./xmlchange JOB_QUEUE=main --subgroup case.run

./xmlchange JOB_PRIORITY=premium

./xmlchange JOB_WALLCLOCK_TIME=12:00:00 --subgroup case.run

./xmlchange NTASKS_ROF=-5

./case.setup

./case.build

./case.submit

./xmlchange RUN_TYPE=hybrid

./xmlchange RUN_REFCASE=prog_phenology

./xmlchange RUN_REFDATE=2002-10-01

./xmlchange GET_REFCASE=FALSE

./xmlchange RUN_STARTDATE=1980-10-01

./xmlchange CONTINUE_RUN=FALSE

./xmlchange STOP_OPTION=nyears

./xmlchange STOP_N=38

./xmlchange RESUBMIT=0

./xmlchange JOB_WALLCLOCK_TIME=12:00:00 --subgroup case.run

./case.setup --reset

./case.build

./case.submit

