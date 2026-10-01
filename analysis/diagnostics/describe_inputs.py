#!/usr/bin/env python
"""Print the dimensions, variables and attributes of representative CTSM input files.

From the notebook input_data_reference.ipynb. Covers the control case
(compset I2000Clm60SpMizGsNldas); one example file per role:
  NLDAS2 raw LDASIN       original NLDAS2 file the DATM streams were built from
  DATM Precip/Solar/TPQWL forcing streams, 0.125 deg CONUS grid (224 lat x 464 lon,
                          25-53N / 235-293E), monthly files 1980-2018
  land/atm mesh           model_meshfile = mesh_atm = mesh_lnd = mesh_mask (geometry only)
  mizuRoute mesh          mesh_rof: river-segment centroids (centerCoords, nodeCoords)
  lnd2rof / rof2lnd maps  area-weighted regridding between the CLM grid and MERIT segments
  ntopo                   river network topology (connectivity, length, slope)
  fsurdat                 static surface data (PFTs, soils, irrigated CFTs, lake/wetland/urban)
  finidat                 initial condition (restart of the previous eval run; check
                          ctsm.input_data_list of the case for the one in use)

How they connect:
  DATM forcing (0.125 deg) -> CLM (fsurdat, paramfile, finidat) -> QRUNOFF on the land grid
  -> lnd2rof_map (mesh_lnd + mesh_rof) -> mizuRoute (ntopo) -> RoutedRunoff per reachID
  -> gauges via merit_reach_id (flow_multi_agency_all_meta.csv) -> streamflow evaluation

Inputs : the files above (paths from analysis/config/paths.py); only metadata is read.
Outputs: text on stdout.

Usage
-----
    module load conda && conda activate npl-2026a
    python describe_inputs.py
For the list of every input file a case uses and whether it exists, see
tools/list_case_inputs.py.
"""

import argparse
import os
import sys

import xarray as xr

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config"))
import paths  # analysis/config/paths.py

FORCING_ROOT = paths.NLDAS2_DATM
ROF_ROOT = paths.MIZUROUTE_INPUT

# (label, path), in the order of the notebook
FILES = [
    ("nldas", f"{paths.NLDAS2_RAW}/1999/1999010100.LDASIN_DOMAIN1"),
    ("DATM Precip stream (example month)",
     f"{FORCING_ROOT}/Precip/ctsmforc.NLDAS2.0.125d.v1.Prec.1985-06.nc"),
    ("DATM Solar stream (example month)",
     f"{FORCING_ROOT}/Solar/ctsmforc.NLDAS2.0.125d.v1.Solr.1985-06.nc"),
    ("DATM TPQWL stream (example month)",
     f"{FORCING_ROOT}/TPQWL/ctsmforc.NLDAS2.0.125d.v1.TPQWL.1985-06.nc"),
    ("Shared land/atm mesh (model_meshfile / mesh_atm / mesh_lnd / mesh_mask)",
     f"{paths.MESH_ROOT}/0.125nldas2_ESMFmesh_cd5_241220.nc"),
    ("mizuRoute river-segment mesh (mesh_rof)", paths.ROF_MESH),
    ("lnd2rof_map (CLM grid -> mizuRoute segments)",
     f"{ROF_ROOT}/gridmaps/map_0.125nldas2_TO_MERITmz_CONUS_aave.210609.nc"),
    ("rof2lnd_map (mizuRoute segments -> CLM grid)",
     f"{ROF_ROOT}/gridmaps/map_MERITmz_CONUS_TO_0.125nldas2_aave.210609.nc"),
    ("River network topology (fname_ntopold)",
     f"{ROF_ROOT}/ancillary_data/ntopo_MERITmz_0.125nldas2_cdf5_fill_reorder_c20210625.nc"),
    ("Static surface dataset (fsurdat)",
     f"{paths.CLM_INPUT}/surfdata_esmf/ctsm5.4.0/surfdata_0.125nldas2_hist_2000_78pfts_c251022.nc"),
    # Path depends on which case's run directory you're checking -- update as needed
    ("Initial condition / restart (finidat)",
     f"{paths.RUN_ROOT}/control/run/control.clm2.r.2018-10-01-00000.nc"),
]


def describe(path, label):
    print(f"\n{'='*90}\n{label}\n{path}\n{'='*90}")
    try:
        ds = xr.open_dataset(path)
    except Exception as e:
        print(f"  Could not open: {e}")
        return None
    print(f"Dimensions: {dict(ds.sizes)}")
    print(f"Data variables ({len(ds.data_vars)}):")
    for v in ds.data_vars:
        print(f"  {v:25s} {str(ds[v].dims):30s} {ds[v].dtype}")
    print(f"Coordinates: {list(ds.coords)}")
    if ds.attrs:
        print(f"Global attrs: {dict(ds.attrs)}")
    return ds


def main():
    argparse.ArgumentParser(description=__doc__,
                            formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    for label, path in FILES:
        describe(path, label)


if __name__ == "__main__":
    main()
