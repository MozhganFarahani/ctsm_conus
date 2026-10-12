(overview)=
# High-resolution (1/8th degree) CTSM CONUS-wide hydrology evaluation and community baseline simulation datasets

This project runs CTSM coupled to the mizuRoute river routing model at ~12 km (0.125°) resolution over CONUS. Starting from a control configuration, each experiment changes one process option against its baseline: irrigation, evolving land cover, hillslope hydrology, or prognostic phenology (spinup history also differs by configuration; see [Lessons, caveats and future work](#lessons)). Simulated streamflow is evaluated against approximately 2,300 stream gauges over water years 1981-2018. This note documents the setup, spinup, quality control and evaluation.

## Motivation and science question

The Community Terrestrial Systems Model (CTSM) now offers multiple process configuration options, including satellite vs. prognostic phenology, static vs. evolving land cover, irrigation, and hillslope hydrology. How these choices affect simulated snow, soil moisture, runoff, evapotranspiration and streamflow over the contiguous United States (CONUS) at spatial scales relevant to hydrology and water resources has not been systematically evaluated, which is the primary motivation for this study. The core science questions we address are the following:

*Which CTSM configuration choices most influence fine-scale CONUS land and hydrology simulation performance, and how do the resulting simulations compare with observations?*

The simulations are intended as a reusable baseline for the CTSM community, for choosing configurations in hydrologic applications, and as a foundation for follow-on work, including model calibration efforts.

## What was produced

- Five CTSM simulations on the NLDAS2 0.125° grid with mizuRoute on the MERIT network, each with its own spinup and a 38-year evaluation run (water years 1981-2018).
- An evaluation of routed streamflow against ~2,300 multi-agency gauges, with CTSM fields averaged over each gauge's contributing area.
- An interactive dashboard comparing all five configurations with observations.
- An archive of the setup scripts and case directories.

## Links

- Project page: [project.cgd.ucar.edu/projects/ctsm-conus](https://project.cgd.ucar.edu/projects/ctsm-conus/)
- Dashboard: [project.cgd.ucar.edu/projects/ctsm-conus/dashboard.html](https://project.cgd.ucar.edu/projects/ctsm-conus/dashboard.html)
- Code and case archive: [github.com/MozhganFarahani/ctsm_conus](https://github.com/MozhganFarahani/ctsm_conus)

## Team

Mozhgan Farahani, Andy Wood, Sean Swenson, Naoki Mizukami from the Terrestrial Sciences Section, CGD Laboratory, NSF NCAR. Dr. Farahani conducted all CTSM modeling and analysis efforts, with input from team members. Funded by CGD SIF-T FY26, August-September 2026.

## Acknowledgments

This work was created with support from the CGD Science Innovation Fund (SIF-T) during August–September of FY26, and with minor support from the NCAR Water Systems Program. Computing was provided on NCAR's Derecho and Casper HPC systems. We also acknowledge the contribution of CONUS streamflow modeling datasets developed in water security projects supported by the U.S. Army Corps of Engineers and the US Bureau of Reclamation.

## Map of the tabs

- [Common setup](#common-setup)
- [Cases](#cases)
  - [control](#case-control)
  - [irrigation_on](#case-irrigation-on)
  - [evolving_landcover](#case-evolving-landcover)
  - [hillslope](#case-hillslope)
  - [prog_phenology](#case-prog-phenology)
- [Analysis](#analysis)
  - [Checks](#checks)
  - [Streamflow evaluation method](#streamflow-evaluation-method)
  - [Results](#results)
  - [Dashboard](#dashboard)
- [Code and data](#code-and-data)
- [Lessons, caveats and future work](#lessons)
