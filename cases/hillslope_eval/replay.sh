#!/bin/bash

set -e

# Created 2026-09-15 16:44:09

CASEDIR="/glade/work/mozhgana/ctsm_conus/cime/scripts/hillslope_eval"

/glade/work/mozhgana/ctsm_conus/cime/scripts/create_newcase --case hillslope_eval --compset I2000Clm60SpMizGsNldas --driver nuopc --compiler intel --res nldas2_nldas2_rMERIT_mnldas2 --machine derecho --project P93300041 --run-unsupported

cd "${CASEDIR}"

./xmlchange DATM_YR_START=1980

./xmlchange DATM_YR_END=2018

./xmlchange DATM_YR_ALIGN=1980

./xmlchange RUN_TYPE=hybrid

./xmlchange RUN_REFCASE=hillslope_on

./xmlchange RUN_REFDATE=2004-10-01

./xmlchange DRV_RESTART_POINTER=rpointer.cpl.2004-10-01-00000

./xmlchange GET_REFCASE=FALSE

./xmlchange RUN_STARTDATE=1980-10-01

./xmlchange CONTINUE_RUN=FALSE

./xmlchange STOP_OPTION=nyears

./xmlchange STOP_N=6

./xmlchange REST_OPTION=nyears

./xmlchange REST_N=6

./xmlchange RESUBMIT=6

./xmlchange JOB_QUEUE=main --subgroup case.run

./xmlchange JOB_WALLCLOCK_TIME=08:00:00 --subgroup case.run

./xmlchange NTASKS_ROF=-5

./xmlchange --append CLM_BLDNML_OPTS=-ignore_warnings

./case.setup

./case.build

./case.submit

./xmlchange NTASKS_ROF=-14

./case.setup --reset

./case.build

./case.submit

