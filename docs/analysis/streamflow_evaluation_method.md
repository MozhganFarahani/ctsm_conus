(streamflow-evaluation-method)=
# Streamflow evaluation method

Monthly routed streamflow at each gauge's MERIT reach is compared with observed flow over water years 1981-2018, using NSE, KGE and percent bias.

**Observations**

- Daily multi-agency streamflow, 2,282 sites (flow_multi_agency_1965-10-01_2024-09-30.nc, m³/s), resampled to monthly means.
- Monthly naturalized streamflow for the 29 USBR Colorado River Basin gauges that are not in the daily file (flow_multi_agency_1965-10_2024-09_month.nc, m³/s, one value per month). If a gauge were in both files, the daily record would be used.
- 1,314 USGS, 945 USACE and 52 USBR sites; 742 naturalized and 1,569 observed flows. 
- A crosswalk (flow_multi_agency_all_meta.csv) links each of the 2,311 gauges to its MERIT reach (merit_reach_id) and labels it naturalized or observed.
- 2,286 of the 2,311 gauges have at least 12 months of overlapping record and are evaluated.
- Note: This dataset and the routing model network were assembled in NCAR water-security projects with USACE and USBR.

**Matching model and observations**

- Model: mizuRoute RoutedRunoff at the gauge's reach, monthly.
- Time: mizuRoute stamps each month on day 16 and observations on day 1, so both are placed on a monthly period index before comparison.
- Metrics use only the months common to the observations and every configuration being compared.

**Metrics**

- **NSE** (Nash-Sutcliffe efficiency): 1 is perfect; below 0 is worse than the observed mean.
- **KGE** (Kling-Gupta efficiency): combines correlation, variability ratio and bias.
- **PBIAS:** percent bias in mean flow.
- **NSE_stable:** NSE reported only for records of 60 months or more. Short, low-variance records can give extreme values (one 24-month record scores NSE = −452,139).

**How gauges are counted.** Metrics come from each configuration's &lt;config&gt;_streamflow_eval.csv (analysis/streamflow/ctsm_streamflow_eval.py). All five configurations are scored on the same gauges and the same months per gauge. At each gauge a configuration is better than its baseline when NSE or KGE is higher, or abs(PBIAS) is smaller. Two counts are reported:

- **Strict:** any change in that direction.
- **Material:** a change larger than 0.01 in NSE or KGE, or 1 percentage point in abs(PBIAS); smaller changes count as neither.

**Basin-averaged CTSM fields.** To explain streamflow errors, CTSM variables (precipitation, ET, snow, soil moisture, runoff and others) are averaged over each gauge's full contributing area.

- Grid-to-catchment weights:  spatialweights_nldas0.125_to_merit_nldas.nc.
- Upstream catchments: the augmented MERIT topology (ntopo_MERIT_Hydro_v1_aug.nc, allUpSegIndices).
- Contributing areas span 26 to 1,339,481 km²; the median basin covers 11 grid cells.
- Derived fields: PRECIP = RAIN + SNOW, SOILMOIST = TOTSOILLIQ + TOTSOILICE, and WBAL = PRECIP − ET − QRUNOFF.
