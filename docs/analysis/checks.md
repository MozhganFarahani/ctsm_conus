(checks)=
# Checks

The control's mizuRoute output has no NaN or negative flows.

**mizuRoute screen** (control, 227,247 reaches)

- 0 reaches with NaN or negative flow; 294 reaches are zero throughout.
- The largest reach (reach 74072586) averages 23,301 m³/s.

**Upstream mapping check.** CTSM fields are averaged over each gauge's contributing area ([Streamflow evaluation method](#streamflow-evaluation-method)). Three independent methods give the same basin mean at the test gauge (0.7719 mm/day): direct aggregation, Naoki Mizukami's remap(), and the coupler's own lnd2rof ESMF weights. Across all 2,311 gauges the mapped area matches the network's totalArea to within 0.000%.
