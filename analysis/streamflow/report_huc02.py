"""HUC02 aggregate figures for the technical note (Results / Regional detail).

Inputs : the five <config>_streamflow_eval.csv from ctsm_streamflow_eval.py (one row per
         gauge; columns Station ID, HUC02, NSE, KGE, PBIAS), default <output root>/streamflow
Outputs: in --outdir (default <output root>/report):
  huc02_summary.csv              medians + strict/material counts (same layout as s82_huc02.csv)
  huc02_medians.png              heatmaps: median NSE, KGE, PBIAS by region x configuration
  huc02_counts_<metric>_<rule>.png  better/worse share of gauges per region, one panel per contrast

Usage:
  module load conda && conda activate npl-2026a
  python report_huc02.py --huc 10 --outdir <test dir>   # quick test on one region
  python report_huc02.py                                # all regions, default folders
"""
import argparse
import os
import sys
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "config"))
import paths  # analysis/config/paths.py

CFGS = ["control", "irrigation_on", "evolving_landcover", "hillslope_eval", "prog_phenology"]
LABEL = {"control": "Control", "irrigation_on": "Irrigation", "evolving_landcover": "Land cover",
         "hillslope_eval": "Hillslope", "prog_phenology": "Prog. phenology"}
# (test, baseline, panel title) -- baselines as in the note's contrast table
CONTRASTS = [("irrigation_on", "control", "Irrigation vs control"),
             ("evolving_landcover", "irrigation_on", "Land cover vs irrigation_on"),
             ("hillslope_eval", "control", "Hillslope vs control"),
             ("prog_phenology", "control", "Prog. phenology vs control")]
TH = {"NSE": 0.01, "KGE": 0.01, "PBIAS": 1.0}  # material thresholds (NSE/KGE units, PBIAS pp)
REGION = {1: "New England", 2: "Mid-Atlantic", 3: "South Atlantic-Gulf", 4: "Great Lakes", 5: "Ohio",
          6: "Tennessee", 7: "Upper Mississippi", 8: "Lower Mississippi", 9: "Souris-Red-Rainy",
          10: "Missouri", 11: "Arkansas-White-Red", 12: "Texas-Gulf", 13: "Rio Grande",
          14: "Upper Colorado", 15: "Lower Colorado", 16: "Great Basin", 17: "Pacific Northwest",
          18: "California"}


def load(indir):
    d = {c: pd.read_csv(Path(indir) / f"{c}_streamflow_eval.csv", dtype={"Station ID": str})
              .set_index("Station ID") for c in CFGS}
    return d


def gain(d, t, b, m):
    """Positive = test better than baseline (higher NSE/KGE, smaller abs(PBIAS))."""
    x, y = d[t][m], d[b][m]
    return (x - y) if m != "PBIAS" else (y.abs() - x.abs())


def summarize_huc02(d, hucs):
    huc = d["control"]["HUC02"].astype(int)
    rows = []
    for h in hucs:
        s = huc == h
        r = {"HUC02": h, "Region": REGION[h], "n": int((s & d["control"]["NSE"].notna()).sum())}
        for m in ["NSE", "KGE", "PBIAS"]:
            for c in CFGS:
                r[f"{m}_{c}"] = d[c].loc[s, m].median()
            for t, b, _ in CONTRASTS:
                g = gain(d, t, b, m)[s].dropna()
                r[f"{m}_{t}_strict_better"], r[f"{m}_{t}_strict_worse"] = int((g > 0).sum()), int((g < 0).sum())
                r[f"{m}_{t}_material_better"] = int((g > TH[m]).sum())
                r[f"{m}_{t}_material_worse"] = int((g < -TH[m]).sum())
        rows.append(r)
    return pd.DataFrame(rows)


def plot_medians(T, out):
    """Three heatmaps; cell text = the median, colour clipped so outliers don't wash out the rest."""
    ylab = [f"{h:02d} {n}" for h, n in zip(T.HUC02, T.Region)]
    xlab = [LABEL[c] for c in CFGS]
    specs = [("NSE", "Median monthly NSE", "RdBu", TwoSlopeNorm(0, -1, 1), "{:.2f}"),
             ("KGE", "Median monthly KGE", "RdBu", TwoSlopeNorm(0, -1, 1), "{:.2f}"),
             ("PBIAS", "Median PBIAS (%)", "PuOr_r", TwoSlopeNorm(0, -100, 100), "{:+.0f}")]
    fig, axs = plt.subplots(1, 3, figsize=(15, 0.36 * len(T) + 2.2), sharey=True)
    for ax, (m, title, cmap, norm, fmt) in zip(np.atleast_1d(axs), specs):
        v = T[[f"{m}_{c}" for c in CFGS]].to_numpy(float)
        im = ax.imshow(v, cmap=cmap, norm=norm, aspect="auto")
        for i in range(v.shape[0]):
            for j in range(v.shape[1]):
                ax.text(j, i, fmt.format(v[i, j]).replace("-", "\u2212"), ha="center", va="center",
                        fontsize=8, color="white" if abs(norm(v[i, j]) - 0.5) > 0.35 else "black")
        ax.set_xticks(range(len(xlab)), xlab, rotation=30, ha="right")
        ax.set_title(title)
        cb = fig.colorbar(im, ax=ax, extend="both", fraction=0.05, pad=0.02)
        if m == "PBIAS":
            cb.set_label("over-prediction (+) / under-prediction (\u2212)")
    axs[0].set_yticks(range(len(ylab)), ylab)
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


def plot_counts(T, metric, rule, out):
    """Share of each region's gauges better (right, blue) / worse (left, red) vs the baseline."""
    lab = "abs(PBIAS)" if metric == "PBIAS" else metric
    ylab = [f"{h:02d} {n}" for h, n in zip(T.HUC02, T.Region)]
    y = np.arange(len(T))
    fig, axs = plt.subplots(1, 4, figsize=(16, 0.36 * len(T) + 2), sharey=True, sharex=True)
    for ax, (t, _, title) in zip(axs, CONTRASTS):
        bt, wo = T[f"{metric}_{t}_{rule}_better"], T[f"{metric}_{t}_{rule}_worse"]
        ax.barh(y, 100 * bt / T.n, color="#2166ac")
        ax.barh(y, -100 * wo / T.n, color="#b2182b")
        for i in range(len(T)):  # raw counts at bar ends, as in the tables
            ax.text(100 * bt.iloc[i] / T.n.iloc[i] + 2, i, str(bt.iloc[i]), va="center", fontsize=7)
            ax.text(-100 * wo.iloc[i] / T.n.iloc[i] - 2, i, str(wo.iloc[i]), va="center", ha="right", fontsize=7)
        ax.axvline(0, color="k", lw=0.8)
        ax.set_title(title, fontsize=10)
        ax.set_xlim(-115, 115)
        ax.set_xticks([-100, -50, 0, 50, 100], ["100", "50", "0", "50", "100"])
        ax.set_xlabel("% of gauges: worse | better")
    axs[0].set_yticks(y, ylab)
    axs[0].invert_yaxis()
    th = {"NSE": "\u00b10.01", "KGE": "\u00b10.01", "PBIAS": "\u00b11 pp"}[metric]
    fig.suptitle(f"Gauges better / worse in {lab}, {rule}" + (f" ({th})" if rule == "material" else ""))
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--indir", default=f"{paths.OUTPUT_ROOT}/streamflow",
                   help="folder with the five <config>_streamflow_eval.csv")
    p.add_argument("--outdir", default=f"{paths.OUTPUT_ROOT}/report",
                   help="where figures and huc02_summary.csv go")
    p.add_argument("--huc", type=int, nargs="*", help="limit to these HUC02 regions (test)")
    a = p.parse_args()
    out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
    d = load(a.indir)
    hucs = a.huc or sorted(d["control"]["HUC02"].dropna().astype(int).unique())
    T = summarize_huc02(d, hucs)
    T.to_csv(out / "huc02_summary.csv", index=False)
    plot_medians(T, out / "huc02_medians.png")
    for m in ["NSE", "KGE", "PBIAS"]:
        for r in ["strict", "material"]:
            plot_counts(T, m, r, out / f"huc02_counts_{m}_{r}.png")
    print(f"{len(T)} regions -> {out}")
