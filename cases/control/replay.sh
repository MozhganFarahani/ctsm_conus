#!/bin/bash

set -e

# Created 2026-08-05 12:14:02

CASEDIR="/glade/work/mozhgana/ctsm_conus/cime/scripts/control"

/glade/work/mozhgana/ctsm_conus/cime/scripts/create_newcase --case control --compset I2000Clm60SpMizGsNldas --driver nuopc --compiler intel --res nldas2_nldas2_rMERIT_mnldas2 --run-unsupported --project P08010000

cd "${CASEDIR}"

./case.setup

./case.build

./xmlchange RUN_TYPE

./xmlchange RUN_STARTDATE=1980-01-01

./case.submit

./xmlchange PROJECT=NRAL0044

./case.submit

./pelayout

./pelayout

./xmlchange NTASKS_ROF=-5

./pelayout

./xmlchange JOB_WALLCLOCK_TIME=00:30:00 --subgroup case.run

./case.setup --reset

./xmlchange PROJECT=P93300041

./xmlchange CHARGE_ACCOUNT=P93300041

./case.setup --reset

./case.build --clean

./case.submit

./case.build

./case.submit

./case.submit

./case.submit

./case.build --clean

./case.build

./case.submit

./xmlchange STOP_OPTION=nyears

./xmlchange STOP_N=10

./xmlchange STOP_N=4

./xmlchange RESUBMIT=2

./xmlchange JOB_WALLCLOCK_TIME=08:00:00 --subgroup case.run

./case.submit

./xmlchange STOP_N=10

./case.submit

./case.submit

./xmlchange RUN_TYPE=hybrid

./xmlchange RUN_REFCASE=control

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

./xmlchange RUN_TYPE=hybrid

./xmlchange RUN_REFCASE=control

./xmlchange RUN_REFDATE=2018-10-01

./xmlchange GET_REFCASE=FALSE

./xmlchange RUN_STARTDATE=1980-10-01

./xmlchange CONTINUE_RUN=FALSE

./xmlchange STOP_OPTION=nyears

./xmlchange STOP_N=38

./xmlchange RESUBMIT=0

./case.setup --reset

./case.build

./case.submit

