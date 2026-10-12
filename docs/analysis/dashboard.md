(dashboard)=
# Dashboard

The [dashboard](https://project.cgd.ucar.edu/projects/ctsm-conus/dashboard.html) compares all five configurations with observations at every gauge, in one self-contained page.

**Layout**

- **Left column:** controls, a gauge map coloured by skill, the monthly time series for the selected gauge, and a metrics table for all configurations.
- **Right column:** six water-year seasonal climatology panels. Streamflow is fixed; the defaults for the other five are precipitation, snow water (H2OSNO), ET, soil moisture and runoff, all averaged over the gauge's contributing area.
- **Colour** marks the configuration; observations are black. On the map, blue always means better skill.

**Tools**

- Search by gauge name or ID, with a HUC02 filter.
- Switch the map metric between NSE, KGE and PBIAS; short records are flagged.
- Load any other basin-averaged CTSM variable, including configuration-specific ones such as QIRRIG_\*, QLATFLOWOUT or GPP.
- Difference mode shows each configuration minus the baseline in every panel.
- The difference maps in Results are this view: map metric NSE, the test configuration, and difference mode against its baseline.
- Each gauge header lists the initialization date of every configuration.
- The first 3 water years are shaded; a log-scale toggle helps low-flow gauges.
- **Link** copies a permalink to the current view; **CSV** downloads the plotted data.

**How it is built**

- dashboard/build_streamflow_dashboard.py reads each configuration's archive, computes the metrics and basin means, and writes one self-contained HTML file. Basin averages come from analysis/lib/basins.py; its gauge-to-grid weights are cached under the output root.
- dashboard/dashboard_template.py holds the HTML, CSS and JavaScript; plots use Plotly.
- dashboard/run_dashboard.pbs builds all five configurations on Casper (10 CPUs, 100 GB, up to 6 h).

**Build.** Test on one gauge first, then submit the full build from dashboard/:

```
python build_streamflow_dashboard.py --configs control,irrigation_on --test-basins 09040000
```

Full build submission: see [Code and data](#code-and-data) (PBS submission).

The builder writes &lt;name&gt;_dashboard.html to the dashboard/ folder under the output root (see [Code and data](#code-and-data), Paths; paths.DASHBOARD_OUT; --outdir overrides it).

**Size:** the five-configuration page is about 70 MB, mostly the monthly series.
