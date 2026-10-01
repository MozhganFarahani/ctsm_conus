"""Streamflow skill metrics: NSE, KGE, PBIAS, for many gauges at once.

Extracted from the vectorized version in ctsm_streamflow_eval.py, with the
degenerate-record guards of the dashboard builder. Callers align the series,
apply MIN_MONTHS, and (dashboard only) clamp for display.
"""

import numpy as np

MIN_MONTHS = 12          # fewer months in common -> no metrics for the gauge
# NSE_stable: the dashboard reports NSE only for gauges with 60+ months
# (the filter itself runs in the dashboard's JavaScript).
STABLE_MIN_MONTHS = 60


def nse_kge_pbias(O, M):
    """O, M: observed and simulated arrays (time x gauge). Months where either is
    NaN are dropped per gauge. Returns dict of 1-D arrays nse, kge, pbias, corr, n.

    NaN (not +-inf) where the observed record cannot support a metric:
    NSE when obs has no variance; KGE when obs is constant or has zero mean;
    PBIAS when obs mean is zero.
    """
    O = np.asarray(O, dtype=float)
    M = np.asarray(M, dtype=float)
    mask = ~np.isnan(M) & ~np.isnan(O)
    n_valid = mask.sum(axis=0)
    Mm, Om = np.where(mask, M, np.nan), np.where(mask, O, np.nan)

    with np.errstate(invalid="ignore", divide="ignore"):
        obs_mean, sim_mean = np.nanmean(Om, axis=0), np.nanmean(Mm, axis=0)
        sse = np.nansum((Om - Mm) ** 2, axis=0)
        sst = np.nansum((Om - obs_mean) ** 2, axis=0)
        nse = 1 - sse / sst
        obs_std = np.nanstd(Om, axis=0, ddof=1)
        sim_std = np.nanstd(Mm, axis=0, ddof=1)
        # covariance with the same ddof=1 as the stds; dividing by n instead
        # biased corr by up to 7e-3 (checked against pandas .corr()).
        cov = np.nansum((Om - obs_mean) * (Mm - sim_mean), axis=0) / (n_valid - 1)
        corr = cov / (obs_std * sim_std)
        alpha, beta = sim_std / obs_std, sim_mean / obs_mean
        kge = 1 - np.sqrt((corr - 1) ** 2 + (alpha - 1) ** 2 + (beta - 1) ** 2)
        pbias = 100 * (sim_mean - obs_mean) / obs_mean

    nse = np.where(sst > 0, nse, np.nan)
    ok_obs = (obs_std > 0) & (obs_mean != 0)
    kge = np.where(ok_obs & np.isfinite(corr), kge, np.nan)
    pbias = np.where(obs_mean != 0, pbias, np.nan)
    return {"nse": nse, "kge": kge, "pbias": pbias, "corr": corr, "n": n_valid}
