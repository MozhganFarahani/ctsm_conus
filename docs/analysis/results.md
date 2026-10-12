(results)=
# Results

The control reaches a median monthly NSE of 0.098 across 2,286 gauges. Hillslope hydrology raises it to 0.215 and prognostic phenology lowers it to 0.060; irrigation and evolving land cover each change it by less than 0.01 against their baselines.

## Control baseline

- **Best and worst regions** (HUC02): best in 06 (Tennessee), 11 (Arkansas-White-Red), 05 (Ohio) and 03 (South Atlantic-Gulf); worst in 15 (Lower Colorado), 13 (Rio Grande) and 16 (Great Basin), with the Missouri (10) also poor.
- **Best gauge:** North Fork Alsea River at Alsea, OR (NSE 0.941).
- **Missouri over-prediction:** at the 22 naturalized mainstem gauges, bias grows upstream from +63% at Hermann, near the mouth, to about +130% at the Dakota mainstem reservoirs, Fort Randall, Big Bend and Oahe, and then falls back to roughly +60 to +110% further upstream. NSE keeps getting worse going upstream: −0.39 at Hermann, −8.4 at Fort Benton, and −13.9 at Canyon Ferry in Montana. For comparison, the Ohio and Mississippi test gauges are at 0.3 to 0.5

```{figure} ../figures/control_nse_map.png
:alt: Monthly NSE at each gauge, control

Monthly NSE at each gauge, control.
```

```{figure} ../figures/control_kge_map.png
:alt: Monthly KGE at each gauge, control

Monthly KGE at each gauge, control.
```

```{figure} ../figures/control_abs_pbias_map.png
:alt: abs(PBIAS) at each gauge, control

abs(PBIAS) at each gauge, control (dashboard; scale 0 to 100%). The map shows the size of the bias, not its sign.
```

## Configuration sensitivities

Hillslope hydrology is the only option that improves streamflow skill substantially: median monthly NSE rises from 0.098 to 0.215 and KGE from 0.246 to 0.349. Prognostic phenology lowers skill on all three metrics, and irrigation and evolving land cover change it by amounts mostly within the materiality threshold.

Each contrast changes one option against the right baseline (spinup history also differs by configuration; see [Lessons, caveats and future work](#lessons)):

| Contrast | Compared runs | Option tested |
|---|---|---|
| Irrigation | irrigation_on − control | irrigation on |
| Land cover | evolving_landcover − irrigation_on | evolving land cover, irrigation held on |
| Hillslope | hillslope_eval − control | hillslope hydrology |
| Phenology | prog_phenology − control | prognostic (BGC) vs satellite phenology |

Medians use 2,286 gauges (2,285 for KGE and correlation: the Swan River at East Patchogue, NY has zero simulated flow, so KGE is undefined there).

**Summary across gauges**

| Configuration | Median NSE | Median NSE, ≥ 60 months (n = 2,157) | Median KGE | Median PBIAS | Median abs(PBIAS) | Median correlation |
|---|---|---|---|---|---|---|
| control | 0.098 | 0.101 | 0.246 | +13.9% | 28.5% | 0.638 |
| irrigation_on | 0.095 | 0.099 | 0.245 | +15.2% | 28.5% | 0.639 |
| evolving_landcover | 0.086 | 0.088 | 0.251 | +14.7% | 28.6% | 0.636 |
| hillslope_eval | 0.215 | 0.221 | 0.349 | −17.4% | 32.1% | 0.711 |
| prog_phenology | 0.060 | 0.063 | 0.210 | +31.3% | 41.0% | 0.677 |

**Gauges improved vs baseline** (better / worse; the rest unchanged)

| Contrast | NSE, strict | NSE, material | KGE, strict | KGE, material | abs(PBIAS), strict | abs(PBIAS), material |
|---|---|---|---|---|---|---|
| Irrigation vs control | 943 / 1,340 | 222 / 599 | 1,057 / 1,228 | 188 / 464 | 1,027 / 1,256 | 274 / 552 |
| Land cover vs irrigation_on | 1,262 / 1,021 | 569 / 419 | 1,282 / 1,003 | 383 / 302 | 1,131 / 1,152 | 448 / 397 |
| Hillslope vs control | 1,380 / 903 | 1,337 / 860 | 1,438 / 847 | 1,391 / 779 | 1,092 / 1,191 | 1,072 / 1,161 |
| Prog. phenology vs control | 934 / 1,349 | 845 / 1,254 | 867 / 1,418 | 765 / 1,329 | 671 / 1,612 | 607 / 1,536 |

**Irrigation.** Irrigation lowers the median NSE slightly (0.098 to 0.095) and raises the median PBIAS from +13.9% to +15.2%. 821 of 2,286 gauges change materially, and losses outnumber gains (222 better, 599 worse in NSE). The losses concentrate in the Missouri (28 / 135), the Pacific Northwest (27 / 147), Texas-Gulf (6 / 55) and California (10 / 49); the Missouri median PBIAS rises from +86% to +96%.

```{figure} ../figures/dnse_irrigation_on_minus_control.png
:alt: Change in monthly NSE, irrigation_on − control

Change in monthly NSE at each gauge, irrigation_on − control. Blue is better; colours are clipped at ±0.3.
```

**Land cover.** Against irrigation_on, evolving land cover lowers the median NSE from 0.095 to 0.086 even though more gauges improve than degrade (569 better, 419 worse in NSE). Gains are in the Pacific Northwest (169 / 19), California (50 / 15) and the Great Basin (26 / 9). Losses are in the Missouri (80 / 93), the Mid-Atlantic (33 / 54), South Atlantic-Gulf (25 / 38) and Souris-Red-Rainy, where the median NSE falls from 0.208 to −0.041.

```{figure} ../figures/dnse_evolving_landcover_minus_irrigation_on.png
:alt: Change in monthly NSE, evolving_landcover − irrigation_on

Change in monthly NSE at each gauge, evolving_landcover − irrigation_on. Blue is better; colours are clipped at ±0.3.
```

**Hillslope hydrology.** Hillslope roughly doubles the median NSE (0.098 to 0.215) and raises median KGE from 0.246 to 0.349 and median correlation from 0.638 to 0.711. NSE is materially better at 1,337 gauges and worse at 860.

```{figure} ../figures/dnse_hillslope_eval_minus_control.png
:alt: Change in monthly NSE, hillslope_eval − control

Change in monthly NSE at each gauge, hillslope_eval − control. Blue is better; colours are clipped at ±0.3.
```

- **Median PBIAS is lower in every HUC02 region.** The median PBIAS flips from +13.9% to −17.4%. The median abs(PBIAS) rises from 28.5% to 32.1%, and the abs(PBIAS) count leans worse (1,072 / 1,161).
- **Gains are largest where control over-predicts.** Missouri NSE goes from −0.94 to −0.03 (PBIAS +86% to +12%), Lower Colorado from −2.83 to 0.09, Rio Grande from −1.97 to −0.38, and Lower Mississippi from 0.21 to 0.56.
- **On the Missouri mainstem**, Hermann improves from NSE −0.39 to 0.59 and PBIAS +63.4% to +1.5%. Fort Benton, MT stays poor (NSE −8.40 to −8.01) although its PBIAS falls from +97.8% to +25.0%.
- **Losses are where control already has small bias**, mostly along the Appalachians in the map: Ohio NSE falls from 0.44 to 0.29 (PBIAS −6.8% to −32.5%), Tennessee from 0.68 to 0.52, Mid-Atlantic from 0.33 to 0.19 and Great Lakes from 0.22 to 0.08.

**Prognostic phenology.** prog_phenology lowers skill on all three metrics: median NSE falls to 0.060, KGE to 0.210, and median PBIAS rises to +31.3%. NSE is materially worse at 1,254 gauges and better at 845; abs(PBIAS) is worse at 1,536. Median correlation rises from 0.638 to 0.677.

```{figure} ../figures/dnse_prog_phenology_minus_control.png
:alt: Change in monthly NSE, prog_phenology − control

Change in monthly NSE at each gauge, prog_phenology − control. Blue is better; colours are clipped at ±0.3.
```

- **Largest losses by median NSE change:** the Missouri (median NSE −0.94 to −3.43, PBIAS +86% to +164%; Hermann NSE −3.33, PBIAS +134%), Souris-Red-Rainy (0.21 to −1.84, PBIAS +230%), the Great Basin (−1.88 to −2.36), the Lower Colorado (−2.83 to −3.17) and the Upper Mississippi (0.14 to −0.11).
- **Gains by median NSE change:** the Rio Grande (−1.97 to −1.51) and the Pacific Northwest (NSE −0.22 to 0.21, KGE 0.30 to 0.48).

**By region (HUC02).** Median monthly NSE, KGE and PBIAS per configuration, and gauges materially better / worse in NSE per contrast.

```{figure} ../figures/huc02_median_heatmap.png
:alt: Median monthly NSE, KGE and PBIAS by HUC02 region and configuration

Median monthly NSE, KGE and PBIAS by HUC02 region and configuration. Cell text is the median; colours are clipped at ±1 (NSE, KGE) and ±100% (PBIAS). For PBIAS the colour shows over- (+) or under-prediction (−), not skill.
```

The six bar charts below show the share of each region's gauges better (blue, right) or worse (red, left) than the contrast's baseline; for abs(PBIAS), smaller counts as better. Material counts a change larger than 0.01 in NSE or KGE, or 1 pp in abs(PBIAS); strict counts any change. Numbers at the bar ends are gauge counts.

```{figure} ../figures/huc02_counts_nse_material.png
:alt: Gauges materially better / worse in NSE by HUC02 region

NSE, material.
```

```{figure} ../figures/huc02_counts_kge_material.png
:alt: Gauges better / worse in KGE, material, by HUC02 region

KGE, material.
```

```{figure} ../figures/huc02_counts_abs_pbias_material.png
:alt: Gauges better / worse in abs(PBIAS), material, by HUC02 region

abs(PBIAS), material.
```

```{figure} ../figures/huc02_counts_nse_strict.png
:alt: Gauges better / worse in NSE, strict, by HUC02 region

NSE, strict.
```

```{figure} ../figures/huc02_counts_kge_strict.png
:alt: Gauges better / worse in KGE, strict, by HUC02 region

KGE, strict.
```

```{figure} ../figures/huc02_counts_abs_pbias_strict.png
:alt: Gauges better / worse in abs(PBIAS), strict, by HUC02 region

abs(PBIAS), strict.
```

Every regional median and count (NSE, KGE and PBIAS; strict and material) is in huc02_summary.csv, attached here ([huc02_summary.csv](../data/huc02_summary.csv)) and on GLADE at `/glade/work/mozhgana/ctsm_conus_output/report/huc02_summary.csv`.
