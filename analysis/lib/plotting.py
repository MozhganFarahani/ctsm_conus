"""Shared map style: CONUS extent, projection and basemap.

basemap() is taken from climatology/ctsm_climatology_maps.py.
"""

import cartopy.crs as ccrs
import cartopy.feature as cfeature

CONUS_EXTENT = [235, 293, 25, 53]    # lon 0-360, lat
PROJ = ccrs.PlateCarree()


def basemap(ax):
    """Grey land, white ocean, states, coastlines and borders, CONUS extent."""
    ax.add_feature(cfeature.LAND, facecolor="0.9", zorder=0)
    ax.add_feature(cfeature.OCEAN, facecolor="white", zorder=2)
    ax.add_feature(cfeature.STATES, lw=0.25, ec="0.5", zorder=3)
    ax.coastlines(lw=0.4, color="0.3", zorder=3)
    ax.add_feature(cfeature.BORDERS, lw=0.4, ec="0.3", zorder=3)
    ax.set_extent(CONUS_EXTENT, crs=PROJ)
