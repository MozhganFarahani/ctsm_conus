#!/bin/bash

set -e

# Created 2026-08-12 15:33:34

CASEDIR="/glade/work/mozhgana/ctsm_conus/cime/scripts/irrigation_on"

/glade/work/mozhgana/ctsm_conus/cime/scripts/create_newcase --case irrigation_on --compset I2000Clm60SpMizGsNldas --driver nuopc --compiler intel --res nldas2_nldas2_rMERIT_mnldas2 --machine derecho --project P93300041 --run-unsupported

cd "${CASEDIR}"

./xmlchange DATM_YR_START=1980

./xmlchange DATM_YR_END=2018

./xmlchange DATM_YR_ALIGN=1980

./xmlchange RUN_TYPE=startup

./xmlchange RUN_STARTDATE=1980-01-01

./xmlchange CONTINUE_RUN=FALSE

./xmlchange STOP_OPTION=nyears

./xmlchange STOP_N=22

./xmlchange RESUBMIT=0

./xmlchange JOB_QUEUE=main --subgroup case.run

./xmlchange JOB_WALLCLOCK_TIME=05:00:00 --subgroup case.run

./xmlchange NTASKS_ROF=-5

./case.setup

./preview_namelists

./case.build

./case.submit

./xmlchange RUN_TYPE=hybrid

./xmlchange RUN_REFCASE=irrigation_on

./xmlchange RUN_REFDATE=2002-01-01

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

