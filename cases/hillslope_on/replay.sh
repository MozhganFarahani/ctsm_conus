#!/bin/bash

set -e

# Created 2026-09-10 11:19:38

CASEDIR="/glade/work/mozhgana/ctsm_conus/cime/scripts/hillslope_on"

/glade/work/mozhgana/ctsm_conus/cime/scripts/create_newcase --case hillslope_on --compset I2000Clm60SpMizGsNldas --driver nuopc --compiler intel --res nldas2_nldas2_rMERIT_mnldas2 --machine derecho --project P93300041 --run-unsupported

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

./xmlchange REST_N=2

./xmlchange RESUBMIT=5

./xmlchange JOB_QUEUE=main --subgroup case.run

./xmlchange JOB_WALLCLOCK_TIME=08:00:00 --subgroup case.run

./case.setup

./case.build

./xmlchange --append CLM_BLDNML_OPTS=-ignore_warnings

./case.build

./case.submit

./xmlchange CONTINUE_RUN=TRUE

./xmlchange STOP_N=6

./xmlchange RESUBMIT=2

./xmlchange DRV_RESTART_POINTER=rpointer.cpl.1986-10-01-00000

./case.submit

