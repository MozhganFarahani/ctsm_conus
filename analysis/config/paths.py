"""Every GLADE path used by the analysis code. Edit paths here, nowhere else.

Scripts import this module with
    sys.path.insert(0, <path to analysis/config>)
    import paths

Strings are kept exactly as the original scripts had them: upstream_basin.py
hashes NTOPO and WEIGHTS into its cache file names.
"""

# --- model output ------------------------------------------------------------
SCRATCH = "/glade/derecho/scratch/mozhgana"
RUN_ROOT = SCRATCH                    # <case>/run/ (lnd_in, restarts)
ARCHIVE = f"{SCRATCH}/archive"        # <case>/{lnd/hist,rof/hist,rest}/
CASES_ROOT = "/glade/work/mozhgana/ctsm_conus/cime/scripts"   # <case>/CaseDocs/


def lnd_hist(case):
    """CTSM history folder (h0a monthly, h1a daily) for a case."""
    return f"{ARCHIVE}/{case}/lnd/hist"


def rof_hist(case):
    """mizuRoute history folder (monthly <case>.mizuroute.h.YYYY-MM.nc)."""
    return f"{ARCHIVE}/{case}/rof/hist"


# --- observed streamflow (Naoki Mizukami) and gauge metadata -----------------
OBS_DIR = "<path_to_streamflow_tseries>"
OBS_DAILY = f"{OBS_DIR}/flow_multi_agency_1965-10-01_2024-09-30.nc"
OBS_MONTHLY = f"{OBS_DIR}/flow_multi_agency_1965-10_2024-09_month.nc"   # 29 sites only

CALIB_CONUS = "<path_to_gauge_metadata>"
CROSSWALK = f"{CALIB_CONUS}/route/extract_seg/ancillary_data/flow_multi_agency_all_meta.csv"
HUC2_SITES = CALIB_CONUS + "/huc2/multi_agency_{region}_site.gpkg"    # .format(region="18")

# --- MERIT routing network and NLDAS-to-MERIT mapping (Naoki Mizukami) -------
NTOPO = ("/glade/work/mizukami/test_mizuRoute/MERIT_basin_nldas/ancillary_data/"
         "ntopo_MERIT_Hydro_v1_aug.nc")
WEIGHTS = ("/glade/work/mizukami/py_mapping/MERIT_Hydro/mapping_v1/"
           "spatialweights_nldas0.125_to_merit_nldas.nc")
MERIT_CATCH_GPKG = "/glade/campaign/ral/hap/mizukami/work/data/MERIT_hydro/v1/nldas/nldas_MERIT_v1_catch.gpkg"

# --- CESM input data ---------------------------------------------------------
INPUTDATA = "/glade/campaign/cesm/cesmdata/inputdata"
NLDAS2_DATM = f"{INPUTDATA}/atm/datm7/atm_forcing.datm7.NLDAS2.0.125d.v1"
NLDAS2_RAW = "/glade/campaign/ral/hap/common/NLDAS2"      # original LDASIN files
MESH_ROOT = f"{INPUTDATA}/share/meshes"
MIZUROUTE_INPUT = f"{INPUTDATA}/rof/mizuRoute"
ROF_MESH = f"{MIZUROUTE_INPUT}/meshes/polygon_centroid/MERITmz_0.125nldas2_ctrcrd_sqr_cdf5_ESMFmesh_c20210113.nc"
CLM_INPUT = f"{INPUTDATA}/lnd/clm2"

# --- outputs (outside the repo, so nothing is committed by accident) ---------
OUTPUT_ROOT = "/glade/work/mozhgana/ctsm_conus_output"
CLIM_OUT = f"{OUTPUT_ROOT}/climatology/maps"
CLIM_CACHE = f"{OUTPUT_ROOT}/climatology/ctsm_monthly_climatology.nc"
DASHBOARD_OUT = f"{OUTPUT_ROOT}/dashboard"
UPSTREAM_CACHE = f"{OUTPUT_ROOT}/dashboard/cache"    # upstream_basin.py weight matrices
