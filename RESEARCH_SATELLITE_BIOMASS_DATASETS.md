# Satellite Missions & Datasets for Forest Biomass Measurement
## External to Google Earth Engine -- Integration Candidates for SINR v3 Training Pipeline

**Research Date:** 2026-02-25
**Context:** Multi-task deep learning model (SINR v3) predicting 43,500 tree species + carbon/biomass globally from 23.6M GBIF occurrence points. Currently sampling features from GEE (AlphaEarth, WorldClim, soil, Hansen, MODIS NPP). This document identifies the best external biomass/carbon datasets for download and integration.

---

## Table of Contents

1. [ESA BIOMASS Mission (P-band SAR)](#1-esa-biomass-mission)
2. [NISAR (NASA-ISRO SAR)](#2-nisar)
3. [ESA CCI Biomass](#3-esa-cci-biomass)
4. [ALOS PALSAR / PALSAR-2 (L-band SAR)](#4-alos-palsar--palsar-2)
5. [GEDI L4B Gridded Biomass](#5-gedi-l4b-gridded-biomass)
6. [Copernicus Global Land Service](#6-copernicus-global-land-service)
7. [GlobBiomass](#7-globbiomass)
8. [JPL/NASA Carbon Monitoring System (CMS)](#8-jplnasa-carbon-monitoring-system)
9. [WRI/Global Forest Watch Biomass Density](#9-wriglobal-forest-watch-biomass-density)
10. [Other Cutting-Edge Datasets (2024-2026)](#10-other-cutting-edge-datasets-2024-2026)
11. [Comparative Analysis & Recommendations](#11-comparative-analysis--recommendations)
12. [Priority Integration Roadmap](#12-priority-integration-roadmap)

---

## 1. ESA BIOMASS Mission

### Mission Overview

| Field | Value |
|-------|-------|
| **Full Name** | ESA Earth Explorer 7 -- Biomass |
| **Provider** | European Space Agency (ESA) |
| **Launch Date** | **29 April 2025** (confirmed -- launched on Vega-C from Kourou, French Guiana) |
| **Current Status** | **Fully commissioned as of January 2026.** L1 data open to all since 26 January 2026. Tomographic global coverage phase underway (~18 months). Interferometric phase to follow. |
| **Mission Duration** | Minimum 5.5 years (consumables for longer) |
| **Orbit** | Polar, dawn-dusk, Sun-synchronous, 666 km altitude, 98-degree inclination |
| **Repeat Cycle** | 3-day repeat cycle for interferometric acquisitions |
| **Prime Contractor** | Airbus (UK) |

### P-band SAR: The Physics

**What is P-band?**
P-band is the lowest frequency band used in synthetic aperture radar (SAR), operating at approximately **435 MHz** (center frequency) with a **wavelength of ~69 cm** (~70 cm). ESA's Biomass is the **first satellite ever to carry a P-band SAR** in space.

**Why P-band is uniquely suited for biomass estimation:**

1. **Deep canopy penetration:** The ~70 cm wavelength penetrates through leaves, small branches, and even the upper canopy structure to interact directly with **large woody components** -- trunks, major branches, and the ground beneath. This is where the majority of forest carbon is physically stored.

2. **Sensitivity to woody volume:** P-band backscatter is strongly correlated with stem volume and above-ground biomass density (AGBD). The long wavelength means the radar signal scatters primarily off objects comparable in size to the wavelength -- i.e., tree trunks and large branches (diameter >10 cm).

3. **Reduced saturation compared to shorter wavelengths:** The signal does not saturate until much higher biomass levels than C-band or L-band SAR.

4. **Tomographic capability:** P-band polarimetric interferometric SAR (PolInSAR) enables 3D tomographic imaging of forest vertical structure, separating ground and canopy contributions.

### SAR Band Comparison for Biomass

| Parameter | C-band (Sentinel-1) | L-band (ALOS PALSAR) | P-band (Biomass) |
|-----------|---------------------|----------------------|-------------------|
| **Frequency** | ~5.4 GHz | ~1.27 GHz | ~435 MHz |
| **Wavelength** | ~5.6 cm | ~23.5 cm | ~69 cm |
| **Penetration Depth** | Surface/upper canopy only | Mid-canopy, some trunk interaction | **Full canopy to ground** |
| **Biomass Saturation** | ~50 Mg/ha | ~100-150 Mg/ha | **>300 Mg/ha (potentially >500 Mg/ha)** |
| **Primary Scatterers** | Leaves, small twigs | Branches, smaller trunks | **Large trunks, major branches, ground** |
| **Biomass Sensitivity** | Low | Moderate | **High** |
| **Tropical Forest Utility** | Very limited (saturates quickly) | Limited in high-biomass tropics | **Excellent -- designed for this** |

### Biomass Mission Instrument Specifications

- **Instrument:** Fully polarimetric P-band SAR (quad-pol: HH, HV, VH, VV)
- **Antenna:** 12-meter diameter passive deployable reflector (largest SAR antenna ever launched)
- **Peak Transmit Power:** +49.5 dBm
- **Feed Array:** 4 patches in 2 doublets
- **Spatial Resolution (L1 SLC):** ~60 m (azimuth) x ~50 m (range) -- mode dependent
- **Expected L2 AGB Product Resolution:** 200 m (target), potentially aggregated to 4 ha (200x200m)

### Data Products & Availability

**L1 Data (NOW AVAILABLE as of Jan 2026):**
- L1a: Raw data
- L1b: Single Look Complex (SLC) focused SAR data
- Available via ESA Earth Online: https://earth.esa.int/eogateway/missions/biomass/biomass-data

**L2 Products (Expected):**
- **L2 AGB (Above-Ground Biomass):** Not yet available. Expected after tomographic phase completion (~mid-2027 at earliest for first global coverage). The tomographic phase takes ~18 months from commissioning end (Jan 2026), so first tomographic global coverage expected ~mid-2027.
- **Forest Height:** From PolInSAR/tomographic processing
- **Forest structure:** 3D canopy profiles from tomography

**Data Access:**
- **Download URL:** https://earth.esa.int/eogateway/missions/biomass/biomass-data
- **Also via:** ESA's Copernicus Data Space Ecosystem (future)
- **Format:** SAFE format (standard ESA EO format)
- **License:** Free and open access (ESA open data policy)

### Expected AGB Accuracy

- **Target accuracy:** 20% relative error or 20 Mg/ha (whichever is larger) for above-ground biomass
- **Saturation point:** P-band SAR is expected to maintain sensitivity up to **>300 Mg/ha**, potentially up to **500 Mg/ha** in some forest types. This is a transformative improvement over L-band (~100-150 Mg/ha saturation) and C-band (~50 Mg/ha saturation).
- **Tropical forests:** This is the primary target. Dense tropical forests in the Congo Basin, Amazon, and Southeast Asia often have AGB >300 Mg/ha, precisely where L-band and C-band fail.

### Early Results & Validation

- **First images released:** June 2025 -- striking images of Bolivian forests showing forest/non-forest boundaries, deforestation fronts, and forest structure
- **Carbon transect published:** January 2026 -- a transect across Gabon, Republic of the Congo, Cameroon, and Central African Republic showing estimated forest carbon content (tonnes/hectare)
- **Airborne validation campaign:** Conducted over Gabon in coordination with DLR, AGEOS, and Gabonese Air Force using airborne P-band SAR systems timed to coincide with satellite overpasses
- **Key reference:** Quegan, S., Le Toan, T., Chave, J. et al. (2019). "The European Space Agency BIOMASS mission: Measuring forest above-ground biomass from space." *Remote Sensing of Environment*. https://doi.org/10.1016/j.rse.2019.03.032

### Integration Priority for SINR v3

| Attribute | Assessment |
|-----------|------------|
| **Priority** | **2 (Should Have) -- rising to 1 when L2 AGB products are released** |
| **Rationale** | L1 SAR data available now but requires significant processing to derive biomass. L2 AGB products (the ready-to-use maps) are expected ~2027. When available, these will be the single best satellite-derived biomass product for tropical forests. |
| **Temporal Match** | Single epoch (2025-2026 onward) -- no historical match to older GBIF observations |
| **Action Items** | (1) Monitor L2 product release schedule. (2) Plan GEE asset upload when L2 AGB products become available. (3) Consider downloading L1 SLC data for key tropical regions and processing with open-source tools for early integration. |

---

## 2. NISAR (NASA-ISRO Synthetic Aperture Radar)

### Mission Overview

| Field | Value |
|-------|-------|
| **Full Name** | NASA-ISRO Synthetic Aperture Radar (NISAR) |
| **Provider** | NASA (Jet Propulsion Laboratory) + Indian Space Research Organisation (ISRO) |
| **Launch Date** | **30 July 2025** (confirmed) |
| **Current Status** | **Commissioning phase** (as of Feb 2026). Sample L-band data products available. |
| **Orbit Altitude** | 747 km |
| **Orbit Inclination** | 98.4 degrees (polar, Sun-synchronous) |
| **Repeat Cycle** | **12 days** (ascending + descending = ~6-day average revisit) |
| **Baseline Mission Duration** | 3 years (consumables for 5 years) |
| **Time of Nodal Crossing** | 6 AM / 6 PM (dawn-dusk) |
| **Data Policy** | **Free and open** |

### Dual-Band SAR: L-band + S-band

**L-band SAR (NASA-provided):**
- **Wavelength:** 24 cm (~1.26 GHz)
- **Penetration:** Mid-canopy, interacts with branches and smaller trunks
- **Biomass Sensitivity:** Moderate -- sensitive to woody biomass up to ~100-150 Mg/ha saturation
- **Duty Cycle:** >50% of orbit
- **Polarization:** Quad-pol capability
- **Resolution:** **3-10 m** (mode-dependent) -- this is extremely high resolution for a SAR biomass mission

**S-band SAR (ISRO-provided):**
- **Wavelength:** ~10 cm (9.4 cm, ~3.2 GHz)
- **Penetration:** Upper canopy / surface
- **Biomass Sensitivity:** Lower than L-band for biomass, but useful for crop monitoring, soil moisture
- **Duty Cycle:** ~10% of orbit
- **Resolution:** 3-10 m (mode-dependent)

### Biomass Estimation Capability

NISAR does **not have a dedicated Level 2 biomass product** in its standard product suite. However:

1. **L-band SAR backscatter** is a well-established predictor of forest biomass (same wavelength as ALOS PALSAR-2)
2. **12-day repeat cycle** enables time-series analysis and change detection at unprecedented temporal resolution
3. **3-10 m resolution** is far finer than any previous global SAR mission for biomass
4. The science team explicitly lists **ecosystems and biomass** as a key science area
5. The **combination of L-band + S-band** allows differential analysis of canopy layers

**Comparison to ALOS PALSAR-2:**
- NISAR L-band operates at the same frequency as ALOS PALSAR-2
- NISAR offers **much higher temporal resolution** (12 days vs. 14 days, but with ascending+descending = ~6 days vs. 14)
- NISAR offers **finer spatial resolution** (3-10 m vs. 25 m for PALSAR-2 ScanSAR)
- NISAR is **free and open**, whereas some PALSAR-2 data requires JAXA agreements
- NISAR provides **dual-frequency** (L+S) whereas PALSAR-2 is L-band only

### Expected AGB Accuracy from L-band

- **Saturation point:** ~100-150 Mg/ha (same physics as ALOS PALSAR)
- **RMSE:** Typically 30-50 Mg/ha for L-band SAR-derived biomass estimates in published literature
- **Limitation in tropics:** High-biomass tropical forests (>150 Mg/ha) will show saturation, limiting utility for dense tropical forests. However, NISAR's high resolution and repeat cycle make it excellent for **detecting biomass change** (deforestation, degradation, regrowth) even if absolute AGB estimation saturates.

### Data Access

| Attribute | Value |
|-----------|-------|
| **Archive/Distribution** | Alaska Satellite Facility (ASF) DAAC |
| **Download URL** | https://www.earthdata.nasa.gov/centers/asf-daac |
| **Sample Data** | Available now at https://www.earthdata.nasa.gov/news/nisar-sample-data-products-available |
| **Format** | Standard SAR product formats (GeoTIFF, HDF5) |
| **License** | Free and open access |
| **GEE Availability** | **Not yet** -- too new. Future ingestion likely. |

### Integration Priority for SINR v3

| Attribute | Assessment |
|-----------|------------|
| **Priority** | **2 (Should Have)** |
| **Rationale** | L-band SAR backscatter is a strong biomass predictor. The 3-10 m resolution is exceptional. However: (1) still in commissioning, (2) no standard biomass product -- would need custom processing, (3) SAR data is complex to work with, (4) L-band saturates in dense tropics. Best use case: pair with optical data for change detection features. |
| **Temporal Match** | 2025 onward only -- no match to historical GBIF observations |
| **Action Items** | (1) Download sample data and evaluate. (2) When operational data flows begin, consider extracting HH/HV backscatter values at training points. (3) Could be used as a feature (SAR backscatter) rather than a label (biomass). |

---

## 3. ESA CCI Biomass

### Dataset Overview

| Field | Value |
|-------|-------|
| **Full Name** | ESA Climate Change Initiative (CCI) Biomass -- Global datasets of forest above-ground biomass |
| **Current Version** | **v6.0** (released 17 April 2025) |
| **Provider** | ESA Climate Change Initiative (CCI) |
| **Project Lead** | Professor Richard Lucas (Aberystwyth University) |
| **Science Lead** | Professor Shaun Quegan (University of Sheffield) |
| **Algorithm Lead** | Maurizio Santoro, Oliver Cartus (Gamma Remote Sensing, Switzerland) |

### Spatial & Temporal Coverage

| Parameter | Value |
|-----------|-------|
| **Spatial Resolution** | **100 m** (grid spacing) |
| **Spatial Coverage** | Global |
| **Temporal Coverage** | **2007, 2010, and annually 2015-2022** (10 epochs total in v6.0) |
| **Temporal Resolution** | Annual maps (individual years) |
| **Coordinate Reference** | WGS84 geographic (lat/lon) |

### Methodology

The ESA CCI Biomass maps are created from a fusion of multiple satellite data sources:

1. **Sentinel-1 C-band SAR** (ESA) -- backscatter data
2. **ALOS PALSAR / PALSAR-2 L-band SAR** (JAXA) -- backscatter mosaics
3. **Spaceborne LiDAR** -- forest height and canopy density information, including NASA's **GEDI** (Global Ecosystem Dynamics Investigation)
4. **ASCAT C-band scatterometer** -- for additional backscatter information

The retrieval algorithm:
- Uses the Water Cloud Model and empirical relationships between SAR backscatter and biomass
- Incorporates LiDAR-derived canopy height/density as constraints
- Builds on the GlobBiomass project algorithms, advanced through CCI Biomass
- Applies a cost function to ensure temporal consistency between the 2007-2010 maps and 2015+ maps

### Products Available

**AGB Maps:**
- Per-pixel above-ground biomass density (Mg/ha) at 100 m resolution
- Per-pixel uncertainty (standard deviation, Mg/ha)
- For each epoch: 2007, 2010, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022

**AGB Change Maps:**
- Standard deviation of AGB change between consecutive years
- Quality flags for AGB change
- Change maps for: 2016-2015, 2017-2016, 2018-2017, 2019-2018, 2020-2019, 2021-2020, 2022-2021
- Decadal change: 2020-2010
- Period change: 2010-2007
- NOTE: The change itself is computed as the difference between two AGB maps (not provided as a separate layer)

**Aggregated Products:**
- Available at coarser resolutions: 1 km, 10 km, 25 km, 50 km
- Both NetCDF and GeoTIFF formats

### Accuracy & Uncertainty

- **Target relative error:** <20% where AGB exceeds 50 Mg/ha
- **Per-pixel uncertainty:** Provided as standard deviation maps
- **Validation:** Extensive validation against ground plots globally (see PVIR document v6.0)
- **Known limitations:**
  - SAR saturation in high-biomass tropical forests
  - Temporal gaps (no annual data between 2010-2015)
  - Potential biases in areas with limited calibration data

### Data Access

| Attribute | Value |
|-----------|-------|
| **Download URL** | https://catalogue.ceda.ac.uk/uuid/95913ffb6467447ca72c4e9d8cf30501/ |
| **Alternative** | ESA CCI Open Data Portal: https://climate.esa.int/en/data/ |
| **Format** | **GeoTIFF and NetCDF** |
| **License** | Free and open (ESA CCI open data policy) |
| **GEE Availability** | **No** -- not natively in GEE catalog |

### Key Citation

Santoro, M.; Cartus, O. (2025): ESA Biomass Climate Change Initiative (Biomass_cci): Global datasets of forest above-ground biomass for the years 2007, 2010, 2015, 2016, 2017, 2018, 2019, 2020, 2021 and 2022, v6.0. NERC EDS Centre for Environmental Data Analysis, 17 April 2025. doi:10.5285/95913ffb6467447ca72c4e9d8cf30501

**Algorithm paper:**
Santoro M., Cartus, O., Quegan, S., Kay H., Lucas, R. M., et al. (2024). "Design and performance of the Climate Change Initiative Biomass global retrieval algorithm." *Science of Remote Sensing*. https://doi.org/10.1016/j.srs.2024.100169

### Integration Priority for SINR v3

| Attribute | Assessment |
|-----------|------------|
| **Priority** | **1 (MUST HAVE)** |
| **Rationale** | This is the single most important dataset for our use case. It provides: (1) global coverage at 100 m, (2) annual temporal resolution matching GBIF observation years (2015-2022), (3) AGB change detection, (4) well-validated, (5) free, (6) ready-to-use GeoTIFF format, (7) already at an appropriate resolution for point sampling. |
| **Temporal Match** | **Excellent.** Annual maps 2015-2022 can be matched to GBIF observation years. The 2010 and 2007 maps cover earlier observations. |
| **Action Items** | **(1) IMMEDIATE: Download v6.0 GeoTIFF data for all years. (2) Upload to GEE as an ImageCollection asset OR extract values at all 23.6M GBIF points using BigQuery/Python. (3) For each GBIF point, sample the AGB value from the year-matched CCI Biomass map. (4) Also sample the uncertainty layer. (5) Consider sampling AGB change as an additional feature.** |
| **Estimated Storage** | ~100-200 GB for all years at 100 m global (GeoTIFF) |

---

## 4. ALOS PALSAR / PALSAR-2

### Dataset Overview

| Field | Value |
|-------|-------|
| **Full Name** | Advanced Land Observing Satellite -- PALSAR/PALSAR-2 Yearly Mosaic |
| **Provider** | JAXA (Japan Aerospace Exploration Agency) Earth Observation Research Center (EORC) |
| **Instruments** | PALSAR (ALOS, 2006-2011) and PALSAR-2 (ALOS-2, 2014-present) |

### GEE Availability

**YES -- ALOS PALSAR yearly mosaics ARE in GEE:**

| Asset | GEE Asset ID | Years |
|-------|-------------|-------|
| **PALSAR/PALSAR-2 Yearly Mosaic v1** | `JAXA/ALOS/PALSAR/YEARLY/SAR` | 2007-2010, 2015-2019 |
| **PALSAR/PALSAR-2 Yearly Mosaic (Epoch)** | `JAXA/ALOS/PALSAR/YEARLY/SAR_EPOCH` | 2015-2021 |
| **JAXA Forest/Non-Forest Map** | `JAXA/ALOS/PALSAR/YEARLY/FNF` | 2007-2010, 2015-2020 |
| **JAXA Forest/Non-Forest (Epoch)** | `JAXA/ALOS/PALSAR/YEARLY/FNF4` | 2015-2021 |

### Technical Specifications

| Parameter | Value |
|-----------|-------|
| **Wavelength** | 23.5 cm (L-band, ~1.27 GHz) |
| **Resolution** | **25 m** (yearly mosaics) |
| **Polarization** | HH and HV (dual-pol) |
| **Data Format** | 16-bit digital number (DN) |
| **DN to dB conversion** | gamma-naught (dB) = 10*log10(DN^2) - 83.0 |
| **Temporal Coverage** | ALOS: 2007-2010 (gap 2011-2014); ALOS-2: 2015-present |
| **DEM correction** | Ortho-rectified using 90 m SRTM DEM |

### L-band SAR Sensitivity to Biomass

**Strengths:**
- HV polarization backscatter has a strong, well-documented relationship with forest above-ground biomass
- L-band penetrates through leaves to interact with branches and trunks
- 25 m resolution provides fine spatial detail

**Saturation Limitation:**
- **L-band SAR saturates at approximately 100-150 Mg/ha** (varies by forest type)
- In tropical forests with AGB >150 Mg/ha, the HV backscatter signal plateaus and cannot distinguish between, say, 200 and 400 Mg/ha
- This is the fundamental limitation addressed by P-band (ESA Biomass mission)
- Saturation is lower in some studies: reported at ~100 Mg/ha for HV, ~80 Mg/ha for HH

**Use in CCI Biomass:**
- ALOS PALSAR/PALSAR-2 L-band data is one of the primary inputs to the ESA CCI Biomass product
- Combined with C-band and LiDAR to extend sensitivity beyond L-band saturation

### Integration Priority for SINR v3

| Attribute | Assessment |
|-----------|------------|
| **Priority** | **1 (MUST HAVE) -- already in GEE** |
| **Rationale** | Already available in GEE, already at 25 m resolution. The HV backscatter channel is a direct, physics-based proxy for woody biomass. Should be sampled as a **feature** (input) for the model, not used as a biomass label. |
| **Action Items** | **(1) Add `JAXA/ALOS/PALSAR/YEARLY/SAR` and `JAXA/ALOS/PALSAR/YEARLY/SAR_EPOCH` to GEE sampling pipeline. (2) Extract HH and HV bands, year-matched to GBIF observations. (3) Convert DN to gamma-naught (dB) in the extraction pipeline.** |

---

## 5. GEDI L4B Gridded Biomass

### Dataset Overview

| Field | Value |
|-------|-------|
| **Full Name** | GEDI L4B Gridded Aboveground Biomass Density, Version 2 |
| **Provider** | NASA / University of Maryland |
| **Instrument** | GEDI (Global Ecosystem Dynamics Investigation) -- spaceborne LiDAR on ISS |
| **PI** | Ralph Dubayah (University of Maryland) |

### Technical Specifications

| Parameter | Value |
|-----------|-------|
| **Spatial Resolution** | **1 km** (1 km x 1 km grid cells) |
| **Spatial Coverage** | Global, **51.6 N to 51.6 S latitude** (ISS orbit constraint) |
| **Temporal Coverage** | 2019-04-18 to 2021-08-04 (mission weeks 19-138) |
| **Temporal Resolution** | One-time estimate (integrated over ~2 years) |
| **Grid System** | EASE-Grid 2.0 (equal-area) |
| **Variables** | Mean AGBD, Standard Error, Variance Components, Quality Flag, Number of Samples |
| **Format** | Cloud-Optimized GeoTIFF (10 files) |
| **Units** | Mg/ha (megagrams per hectare) |

### Method

- GEDI fires laser pulses from ISS, measuring 3D canopy structure via waveform LiDAR
- L4A product: individual 25 m footprint biomass predictions from waveform-to-biomass models
- L4B product: statistical inference of mean AGBD within 1 km cells from L4A sample footprints
- Uses hybrid model-based inference (Patterson et al. 2019)
- Does NOT use a forest mask -- estimates cover entire 1 km cell (forest + non-forest)

### GEE Availability

**Partially.** GEDI L4B V2.1 was previously listed in GEE catalog but the specific asset ID `NASA/GEDI/L4B_Gridded_Biomass_V2_1` may require checking. The dataset is also available directly from ORNL DAAC.

| Attribute | Value |
|-----------|-------|
| **ORNL DAAC** | https://doi.org/10.3334/ORNLDAAC/2017 |
| **Earthdata** | https://daac.ornl.gov/cgi-bin/dsviewer.pl?ds_id=2017 |
| **GEE** | Check for `LARSE/GEDI/GEDI04_B_002` or similar |

### Quality & Limitations

- **L1 Science Requirement:** 80% of 1 km cells must have standard error <20 Mg/ha or <20% of estimate (whichever is greater)
- **Latitude limitation:** No coverage above 51.6 N or below 51.6 S -- **misses boreal forests** in Scandinavia, northern Russia, northern Canada, and Alaska
- **Coverage gaps:** Due to ISS orbit characteristics, some cells have insufficient observations for hybrid inference (show zero values)
- **Single epoch:** Not suitable for temporal change analysis
- **Coarse resolution:** 1 km is coarser than CCI Biomass (100 m) but GEDI provides independent LiDAR-based validation

### Key Citations

Dubayah, R.O., J. Armston, S.P. Healey, et al. (2022). GEDI L4B Gridded Aboveground Biomass Density, Version 2. ORNL DAAC. https://doi.org/10.3334/ORNLDAAC/2017

Duncanson, L., Kellner, J.R., Armston, J., et al. (2022). "Aboveground biomass density models for NASA's GEDI lidar mission." *Remote Sensing of Environment* 270:112845. https://doi.org/10.1016/j.rse.2021.112845

### Integration Priority for SINR v3

| Attribute | Assessment |
|-----------|------------|
| **Priority** | **2 (Should Have)** |
| **Rationale** | GEDI provides an independent LiDAR-based biomass estimate that can complement the SAR-based CCI Biomass product. The 1 km resolution is coarser than CCI Biomass (100 m) but the methodology is fundamentally different (LiDAR vs SAR). Using both provides model resilience. However: (1) no boreal coverage, (2) single epoch, (3) coarser resolution. |
| **Temporal Match** | Moderate -- represents 2019-2021 average |
| **Action Items** | (1) Download from ORNL DAAC or check GEE availability. (2) Sample AGBD and SE at all GBIF points within latitude range. (3) Use as complementary feature to CCI Biomass. |

---

## 6. Copernicus Global Land Service (CGLS)

### Overview

The Copernicus Land Monitoring Service (CLMS) provides a range of bio-geophysical variables at global and European scales. Relevant products for biomass/carbon:

### Relevant Products

**1. Global Dynamic Land Cover (CGLS-LC100)**
| Parameter | Value |
|-----------|-------|
| **Resolution** | 100 m |
| **Coverage** | Global |
| **Temporal** | Annual (2015-present) |
| **Content** | Discrete land cover classes + continuous fractional cover layers |
| **Relevant layers** | Tree cover fraction, forest type classification |
| **Download** | https://land.copernicus.eu/en/products/global-dynamic-land-cover |
| **GEE** | `COPERNICUS/Landcover/100m/Proba-V-C3/Global` |
| **Priority** | 2 -- useful for forest type context but no direct biomass |

**2. Leaf Area Index (LAI)**
| Parameter | Value |
|-----------|-------|
| **Resolution** | 300 m (from PROBA-V, Sentinel-3) |
| **Coverage** | Global |
| **Temporal** | 10-day composites |
| **Relevance** | LAI is correlated with canopy density and indirectly with productivity/biomass |
| **GEE** | Available via Copernicus collections |

**3. Fraction of Absorbed Photosynthetically Active Radiation (FAPAR)**
| Parameter | Value |
|-----------|-------|
| **Resolution** | 300 m |
| **Coverage** | Global |
| **Relevance** | Indicator of vegetation productivity; complementary to NPP |

**4. Dry Matter Productivity (DMP)**
| Parameter | Value |
|-----------|-------|
| **Resolution** | 300 m |
| **Content** | Estimated daily dry matter production |
| **Relevance** | Direct productivity metric |

**NOTE:** Copernicus Global Land Service does **NOT** provide a dedicated AGB/biomass density product. The relevant biomass datasets come from ESA CCI Biomass (see Section 3) and other projects.

### Integration Priority for SINR v3

| Attribute | Assessment |
|-----------|------------|
| **Priority** | **3 (Nice to Have) for LAI/FAPAR; 2 for Land Cover** |
| **Rationale** | No direct biomass product. Land cover (CGLS-LC100) is already likely partially captured by existing GEE features. LAI and FAPAR could add complementary information about canopy structure. |

---

## 7. GlobBiomass

### Dataset Overview

| Field | Value |
|-------|-------|
| **Full Name** | GlobBiomass -- Global Forest Above-Ground Biomass |
| **Provider** | ESA (Data User Element, predecessor to CCI Biomass) |
| **Algorithm Team** | Same team as CCI Biomass (Santoro, Cartus et al.) |
| **Epoch** | **2010 only** (single year) |
| **Resolution** | **100 m** |
| **Coverage** | Global |
| **Status** | **Superseded by ESA CCI Biomass v6.0** |

### Technical Details

- Uses ALOS PALSAR L-band + Envisat ASAR C-band + ICESat GLAS LiDAR
- Same fundamental algorithm later advanced in CCI Biomass
- Single-epoch: 2010

### Data Access

| Attribute | Value |
|-----------|-------|
| **Download** | https://globbiomass.org/products/global-mapping/ |
| **Also via** | PANGAEA: https://doi.org/10.1594/PANGAEA.894711 |
| **Format** | GeoTIFF |
| **License** | Free and open |
| **GEE** | **No** -- not in GEE catalog |

### Integration Priority for SINR v3

| Attribute | Assessment |
|-----------|------------|
| **Priority** | **3 (Nice to Have) -- superseded by CCI Biomass** |
| **Rationale** | CCI Biomass v6.0 includes a 2010 map that is an improved version of GlobBiomass. No reason to use GlobBiomass separately unless comparing historical products. |

---

## 8. JPL/NASA Carbon Monitoring System (CMS)

### Overview

The NASA Carbon Monitoring System (CMS) is a program that produces a variety of carbon flux and stock products. Several are relevant:

### Key Global/Regional Products

**1. CMS Global Forest AGB (Saatchi et al.)**
| Parameter | Value |
|-----------|-------|
| **Full Name** | A benchmark map of forest carbon stocks across the tropics |
| **Authors** | Saatchi, S.S., Harris, N.L., Brown, S., et al. |
| **Publication** | PNAS, 2011 |
| **Resolution** | 1 km |
| **Coverage** | Pantropical (tropics only) |
| **Epoch** | ~2007-2008 |
| **Download** | https://daac.ornl.gov/CMS/guides/CMS_Global_Forest_AGB.html (may redirect) |
| **GEE** | **No** |
| **Priority** | 3 -- superseded by newer products |

**2. CMS ABoVE Boreal Biomass**
| Parameter | Value |
|-----------|-------|
| **Coverage** | Alaska + northwestern Canada (Arctic-Boreal) |
| **Resolution** | 30 m |
| **Method** | Landsat + GLAS LiDAR |
| **Download** | ORNL DAAC |
| **Priority** | 3 -- regional only |

**3. NASA CMS Global Aboveground and Belowground Biomass Carbon Density Maps (Spawn et al. 2020)**
| Parameter | Value |
|-----------|-------|
| **Full Name** | Global Aboveground and Belowground Biomass Carbon Density Maps for the Year 2010 |
| **Authors** | Spawn, S.A., Sullivan, C.C., Lark, T.J., Gibbs, H.K. |
| **Publication** | Scientific Data (2020) |
| **Resolution** | ~300 m (10 arc-second) |
| **Coverage** | Global |
| **Epoch** | 2010 |
| **Variables** | Aboveground biomass carbon density + Belowground biomass carbon density |
| **Download** | ORNL DAAC: https://doi.org/10.3334/ORNLDAAC/1763 |
| **Format** | GeoTIFF |
| **GEE** | **Yes** -- `NASA/ORNL/biomass_carbon_density/v1` |
| **Priority** | **2 (Should Have)** |

### Integration Priority for SINR v3

| Attribute | Assessment |
|-----------|------------|
| **Priority** | **2 for Spawn et al. (2020) -- already in GEE as `NASA/ORNL/biomass_carbon_density/v1`** |
| **Rationale** | The Spawn et al. 2020 product is a harmonized global AGB + BGB carbon density map at ~300 m. It's already in GEE. Single epoch (2010) limits temporal matching. Useful as a complementary baseline. |
| **Action Items** | (1) Check if already being sampled in current GEE pipeline. (2) If not, add to sampling. |

---

## 9. WRI/Global Forest Watch Biomass Density

### Dataset Overview

| Field | Value |
|-------|-------|
| **Full Name** | Aboveground Live Woody Biomass Density (ALWBD) |
| **Provider** | Global Forest Watch / World Resources Institute (WRI) |
| **Source Data** | Originally from WHRC (Woods Hole Research Center) / Baccini et al. (2012) |
| **Updated by** | Harris, N.L. et al. (2021) -- Nature Climate Change |

### Technical Specifications

| Parameter | Value |
|-----------|-------|
| **Resolution** | 30 m |
| **Coverage** | Global (pan-tropical in original; extended globally in later versions) |
| **Epoch** | 2000 (original Baccini/WHRC); ~2000 baseline with loss/gain adjustments |
| **Method** | GLAS LiDAR + Landsat + ground plots |
| **Units** | Mg/ha (megagrams of dry aboveground live woody biomass per hectare) |

### GEE Availability

**Not directly as a standard GEE catalog entry.** However:
- Some versions are available as community uploads or via GFW data API
- The underlying WHRC/Baccini pantropical biomass map has been uploaded by various users
- Check: `projects/earthengine-legacy/assets/projects/glad/GLCLU/Biomass` or similar community assets

### Data Access

| Attribute | Value |
|-----------|-------|
| **Download** | https://data.globalforestwatch.org/ (search "aboveground biomass") |
| **Also** | https://glad.umd.edu/dataset/gfw-global-above-ground-biomass |
| **Format** | GeoTIFF tiles |
| **License** | CC BY 4.0 |
| **GEE** | **Not in official catalog** -- may be available as community asset |

### Key Citation

Harris, N.L., Gibbs, D.A., Baccini, A., et al. (2021). "Global maps of twenty-first century forest carbon fluxes." *Nature Climate Change* 11:234-240. https://doi.org/10.1038/s41558-020-00976-6

### Integration Priority for SINR v3

| Attribute | Assessment |
|-----------|------------|
| **Priority** | **2 (Should Have)** |
| **Rationale** | 30 m resolution is excellent. However, single baseline epoch (~2000) with modeled adjustments limits temporal matching. The Harris et al. (2021) product provides annual carbon flux estimates 2001-2020 at 30 m, which would be extremely valuable if accessible. |
| **Action Items** | (1) Investigate downloading the Harris et al. (2021) annual flux tiles. (2) Upload as GEE asset if not already available. (3) Sample at GBIF points. |

---

## 10. Other Cutting-Edge Datasets (2024-2026)

### 10.1 ICESat-2 Derived Products

**ICESat-2 (launched Sept 2018)** carries the ATLAS photon-counting LiDAR. While primarily designed for ice sheet altimetry, it also provides vegetation canopy height measurements.

**Key Product: Global Canopy Height from ICESat-2 + Sentinel-2 (Lang et al. 2023)**
| Parameter | Value |
|-----------|-------|
| **Full Name** | A high-resolution canopy height model of the Earth |
| **Authors** | Lang, N., Jetz, W., Schindler, K., Wegner, J.D. |
| **Publication** | *Nature Ecology & Evolution* (2023) |
| **Resolution** | **10 m** |
| **Coverage** | Global |
| **Epoch** | 2020 |
| **Method** | Deep learning model trained on GEDI + Sentinel-2 imagery |
| **Download** | https://langnico.github.io/globalcanopyheight/ |
| **GEE** | `users/nlang/ETH_GlobalCanopyHeight_2020_10m_v1` (community upload) |
| **Also** | Check for `ETH/CANOPY/HEIGHT_2020` or similar |
| **Priority** | **1 (MUST HAVE)** -- canopy height is a strong predictor of biomass |

**Meta/WRI Global Canopy Height (Tolan et al. 2024)**
| Parameter | Value |
|-----------|-------|
| **Full Name** | Very high resolution canopy height maps from Meta/WRI |
| **Authors** | Tolan, J. et al. (Meta AI) |
| **Resolution** | **1 m** |
| **Coverage** | Global |
| **Epoch** | 2024 |
| **Method** | DiNOv2 foundation model + Maxar satellite imagery + GEDI LiDAR |
| **GEE** | Check for availability (very new) |
| **Priority** | **2 (Should Have)** -- extraordinary resolution but very new and large |

### 10.2 GEDI-Derived Wall-to-Wall Products Beyond L4B

**GEDI + Machine Learning Wall-to-Wall AGB:**
Several research groups have published wall-to-wall AGB maps by training ML models on GEDI footprint-level biomass (L4A) with Sentinel-1/2, Landsat, and other wall-to-wall predictors:

- **Dubayah et al. (2022)** -- the official L4B product at 1 km
- **Healey et al. (2024-2025)** -- GEDI-informed AGB maps at finer resolution using GHMB inference (expected as GEDI mission matures)
- **Various community products** at ~100 m or finer resolution using GEDI + random forest / gradient boosting models

**Hunka et al. (2023)** -- "On the NASA GEDI and ESA CCI biomass maps: aligning for uptake in the UNFCCC global stocktake." *Environmental Research Letters*. https://doi.org/10.1088/1748-9326/ad0b60

This paper specifically compares and harmonizes GEDI L4B and CCI Biomass for policy use.

### 10.3 SMOS Vegetation Optical Depth (L-VOD)

| Parameter | Value |
|-----------|-------|
| **Full Name** | SMOS L-band Vegetation Optical Depth (L-VOD) |
| **Instrument** | SMOS (Soil Moisture and Ocean Salinity) satellite |
| **Wavelength** | L-band (~1.4 GHz, passive microwave) |
| **Resolution** | ~25-50 km (very coarse) |
| **Temporal** | 2010-present, multiple passes |
| **Relevance** | L-VOD has been shown to correlate strongly with AGB, even in high-biomass tropical forests where SAR saturates |
| **Key paper** | Fan, L., Wigneron, J.P., Ciais, P., et al. (2022). "Siberian carbon sink reduced by forest disturbances." *Nature Geoscience*. |
| **Priority** | 3 (Nice to Have) -- resolution too coarse for point-based model |

### 10.4 State-of-the-Art Papers (2024-2025)

1. **Santoro et al. (2024)** -- "Design and performance of the Climate Change Initiative Biomass global retrieval algorithm." *Science of Remote Sensing*. https://doi.org/10.1016/j.srs.2024.100169
   - Definitive paper on the CCI Biomass algorithm (v5/v6)

2. **Yang, H., Ciais, P., Frappart, F., et al. (2023)** -- "Global increase in biomass carbon stock dominated by growth of northern young forests over past decade." *Nature Geoscience*. https://doi.org/10.1038/s41561-023-01274-4
   - Uses CCI Biomass time series to show global AGB trends

3. **Araza, A., et al. (2023)** -- "Past decade above-ground biomass change comparisons from four multi-temporal global maps." *International Journal of Applied Earth Observation and Geoinformation*. https://doi.org/10.1016/j.jag.2023.103274
   - Critical comparison of multiple AGB map products

4. **Mo, L., Zohner, C.M., Reich, P.B., et al. (2023)** -- "Integrated global assessment of the natural forest carbon potential." *Nature*. https://doi.org/10.1038/s41586-023-06723-z
   - Uses CCI Biomass as a key input for estimating global forest carbon potential

5. **Lang, N. et al. (2023)** -- Global canopy height map at 10 m (see Section 10.1)

6. **ESA Biomass mission first results (2025-2026)** -- Papers expected from PolinSAR Biomass 2026 workshop (Jan 2026, Slovenia) and Living Planet Symposium 2025

---

## 11. Comparative Analysis & Recommendations

### Question 1: Which provide TEMPORAL biomass data (AGB change over time)?

| Dataset | Temporal Coverage | Annual Resolution? | Change Products? |
|---------|-------------------|--------------------|--------------------|
| **ESA CCI Biomass v6** | 2007, 2010, 2015-2022 | **Yes (2015-2022)** | **Yes -- explicit change maps** |
| **ESA Biomass Mission** | 2025 onward | Will have repeat coverage | Future (interferometric phase) |
| **NISAR** | 2025 onward | 12-day repeat | Future (backscatter change) |
| **GEDI L4B** | 2019-2021 (single epoch) | No | No |
| **ALOS PALSAR** | 2007-2010, 2015-present | Annual mosaics | Backscatter change possible |
| **GFW/Harris et al.** | 2001-2020 | **Annual flux estimates** | **Yes** |
| **Spawn/CMS** | 2010 only | No | No |

**Winner for temporal biomass: ESA CCI Biomass v6.0** (annual 2015-2022 at 100 m with change products)

### Question 2: Which have the highest spatial resolution?

| Dataset | Resolution |
|---------|-----------|
| **Meta/WRI Canopy Height** | 1 m |
| **GFW/Harris biomass** | 30 m |
| **ALOS PALSAR backscatter** | 25 m |
| **Lang et al. Canopy Height** | 10 m |
| **ESA CCI Biomass** | 100 m |
| **Spawn/CMS** | 300 m |
| **GEDI L4B** | 1 km |
| **NISAR** | 3-10 m (SAR backscatter, not biomass product) |

**Winner for resolution: NISAR SAR backscatter (3-10 m)** as a feature; **GFW/Harris (30 m)** as a biomass product; **Lang et al. (10 m)** for canopy height

### Question 3: Which have the best accuracy in tropical forests?

Tropical forests are where SAR saturation is the primary challenge (AGB often >200-400 Mg/ha).

| Dataset | Tropical Performance |
|---------|---------------------|
| **ESA Biomass (P-band)** | **Best -- designed for this. Saturates >300-500 Mg/ha** |
| **ESA CCI Biomass** | Good -- combines L+C band + LiDAR to mitigate saturation |
| **GEDI L4B** | Good -- LiDAR does not saturate, but 1 km resolution averages heterogeneity |
| **ALOS PALSAR (L-band)** | Poor in dense tropics -- saturates ~100-150 Mg/ha |
| **Sentinel-1 (C-band)** | Very poor -- saturates ~50 Mg/ha |

**Winner for tropical accuracy: ESA Biomass P-band (when L2 products arrive); currently: ESA CCI Biomass + GEDI**

### Question 4: Which are best for temperate/boreal forests?

| Dataset | Temperate/Boreal Performance |
|---------|-------------------------------|
| **ESA CCI Biomass** | Good -- L-band and C-band sufficient (AGB usually <200 Mg/ha) |
| **ALOS PALSAR** | Good -- L-band within non-saturation range for most temperate/boreal |
| **GEDI L4B** | **No coverage >51.6 N** -- misses much of boreal zone |
| **NISAR** | Excellent -- high resolution, L-band sufficient |
| **ESA Biomass** | Good, but primary design focus is tropics |

**Winner for temperate/boreal: ESA CCI Biomass + ALOS PALSAR** (GEDI misses high latitudes)

### Question 5: Current state-of-the-art for global AGB mapping?

The current state-of-the-art (as of Feb 2026) is characterized by:

1. **ESA CCI Biomass v6.0 (Santoro et al. 2025)** -- The most comprehensive multi-temporal global AGB product. 100 m, 10 epochs. Uses SAR + LiDAR fusion. The definitive reference dataset.

2. **GEDI L4B (Dubayah et al. 2022)** -- The only LiDAR-based global gridded biomass product. Independent methodology from SAR-based products. Limited by ISS orbit (latitude) and 1 km resolution.

3. **ESA Biomass mission (2025-2026)** -- Will become the gold standard when L2 products arrive (~2027). P-band SAR resolves the tropical saturation problem. First-ever spaceborne P-band.

4. **Emerging fusion approaches** -- Combining GEDI footprints + Sentinel-1/2 + ALOS PALSAR + Landsat using deep learning (transformers, foundation models) to produce wall-to-wall AGB at 10-30 m resolution. Papers expected 2026-2027.

5. **Global canopy height maps** -- Lang et al. (2023) at 10 m and Meta/WRI at 1 m provide structural proxies for biomass that can be combined with allometric relationships.

### Question 6: Accuracy comparison

| Dataset | Reported RMSE (Mg/ha) | Notes |
|---------|----------------------|-------|
| ESA CCI Biomass v6 | ~30-60 (varies by biome) | Target <20% where AGB>50 |
| GEDI L4B | Varies; SE provided per-pixel | Generally 20-40 in well-sampled cells |
| GFW/Harris | ~40-70 | Higher in tropics due to saturation |
| ALOS PALSAR (direct) | ~50-80 | Limited by L-band saturation |
| Spawn/CMS 2020 | Not well characterized | Harmonization product |
| ESA Biomass (expected) | ~20% or 20 Mg/ha target | Not yet validated |

### Question 7: Priority ranking for our model (23.6M point-based training)

**Tier 1 -- MUST HAVE (integrate immediately):**
1. **ESA CCI Biomass v6.0** -- The primary biomass label/feature. Annual 2015-2022, 100 m, global.
2. **ALOS PALSAR HH/HV** -- Already in GEE. Direct SAR feature input at 25 m.
3. **Global Canopy Height (Lang et al. 2023)** -- 10 m, strong biomass proxy, in GEE.

**Tier 2 -- SHOULD HAVE (integrate within 3 months):**
4. **GEDI L4B** -- Independent LiDAR-based AGB estimate at 1 km.
5. **Spawn/CMS AGB Carbon** -- Already in GEE (`NASA/ORNL/biomass_carbon_density/v1`). 300 m, epoch 2010.
6. **GFW/Harris Annual Carbon Flux** -- 30 m annual, if accessible.
7. **NISAR L-band backscatter** -- When operational data flows stabilize (2026).

**Tier 3 -- NICE TO HAVE (integrate opportunistically):**
8. **Meta/WRI 1m Canopy Height** -- Extraordinary resolution but massive data volume.
9. **ESA Biomass L2 AGB** -- When released (~2027).
10. **Copernicus LAI/FAPAR** -- Supplementary vegetation structure.
11. **SMOS L-VOD** -- Too coarse for point-based model.

---

## 12. Priority Integration Roadmap

### Phase 1: Immediate (This Sprint)

**Dataset: ESA CCI Biomass v6.0**
```
Download URL: https://catalogue.ceda.ac.uk/uuid/95913ffb6467447ca72c4e9d8cf30501/
Format: GeoTIFF (100 m global tiles per year)
Years: 2007, 2010, 2015-2022
Size: ~100-200 GB total
Integration method:
  Option A: Upload all years as GEE ImageCollection asset -> sample at GBIF points
  Option B: Download tiles -> extract values at GBIF coordinates using Python/rasterio
  Option C: Use BigQuery + geospatial functions if data is in cloud storage
For each GBIF point: sample AGB (Mg/ha) + uncertainty from year-matched map
```

**Dataset: ALOS PALSAR (already in GEE)**
```
GEE Asset: JAXA/ALOS/PALSAR/YEARLY/SAR_EPOCH (2015-2021)
            JAXA/ALOS/PALSAR/YEARLY/SAR (2007-2010, 2015-2019)
Bands: HH, HV (16-bit DN -> convert to gamma-naught dB)
Integration: Add to GEE sampling pipeline, year-matched
```

**Dataset: Global Canopy Height (Lang et al. 2023)**
```
GEE: Check for community asset or upload
Resolution: 10 m
Integration: Sample at GBIF points
```

### Phase 2: Next Quarter

**Dataset: GEDI L4B**
```
Download: https://doi.org/10.3334/ORNLDAAC/2017
Format: Cloud-Optimized GeoTIFF (1 km)
Integration: Upload to GEE or sample directly
Note: Only covers 51.6N-51.6S
```

**Dataset: NASA/ORNL Biomass Carbon Density (Spawn et al.)**
```
GEE: NASA/ORNL/biomass_carbon_density/v1
Already in GEE -- just add to sampling pipeline
```

**Dataset: NISAR sample data**
```
Download: https://www.earthdata.nasa.gov/centers/asf-daac
Evaluate sample products for feasibility
```

### Phase 3: Future (2026-2027)

- ESA Biomass L2 AGB products when released
- NISAR operational L-band mosaics
- Next-generation fusion products (GEDI + Sentinel + deep learning)

---

## Appendix A: GEE Asset Reference Table

| Dataset | In GEE? | Asset ID | Notes |
|---------|---------|----------|-------|
| ALOS PALSAR SAR | YES | `JAXA/ALOS/PALSAR/YEARLY/SAR` | 2007-2010, 2015-2019 |
| ALOS PALSAR SAR (Epoch) | YES | `JAXA/ALOS/PALSAR/YEARLY/SAR_EPOCH` | 2015-2021 |
| JAXA Forest/Non-Forest | YES | `JAXA/ALOS/PALSAR/YEARLY/FNF` | 2007-2010, 2015-2020 |
| GEDI L4B | PARTIAL | Check `LARSE/GEDI/GEDI04_B_002` | May need manual upload |
| Spawn/CMS AGB Carbon | YES | `NASA/ORNL/biomass_carbon_density/v1` | 2010 only |
| Hansen Global Forest | YES | `UMD/hansen/global_forest_change_2023_v1_11` | Already in pipeline |
| MODIS NPP | YES | `MODIS/061/MOD17A3HGF` | Already in pipeline |
| Copernicus Land Cover | YES | `COPERNICUS/Landcover/100m/Proba-V-C3/Global` | 2015-2019 |
| Lang Canopy Height | PARTIAL | Community asset | Check for availability |
| ESA CCI Biomass | **NO** | -- | **Must upload or extract offline** |
| ESA Biomass L1/L2 | NO | -- | Future |
| NISAR | NO | -- | Too new |
| GFW Biomass | NO | -- | Must upload or use GFW API |
| GlobBiomass | NO | -- | Superseded by CCI Biomass |

---

## Appendix B: SAR Frequency Band Reference

| Band | Frequency Range | Wavelength | Example Missions | Biomass Saturation |
|------|----------------|------------|------------------|-------------------|
| X-band | 8-12 GHz | 2.5-3.8 cm | TerraSAR-X, COSMO-SkyMed | ~20-30 Mg/ha |
| C-band | 4-8 GHz | 3.8-7.5 cm | Sentinel-1, Radarsat-2 | ~50 Mg/ha |
| S-band | 2-4 GHz | 7.5-15 cm | NISAR (ISRO) | ~70-100 Mg/ha |
| L-band | 1-2 GHz | 15-30 cm | ALOS PALSAR-2, NISAR (NASA) | ~100-150 Mg/ha |
| P-band | 0.3-1 GHz | 30-100 cm | ESA Biomass | ~300-500+ Mg/ha |

---

## Appendix C: Key References

1. Santoro, M. & Cartus, O. (2025). ESA CCI Biomass v6.0 dataset. doi:10.5285/95913ffb6467447ca72c4e9d8cf30501
2. Santoro, M. et al. (2024). "Design and performance of the CCI Biomass retrieval algorithm." *Science of Remote Sensing*. doi:10.1016/j.srs.2024.100169
3. Quegan, S. et al. (2019). "The ESA BIOMASS mission." *Remote Sensing of Environment*. doi:10.1016/j.rse.2019.03.032
4. Dubayah, R.O. et al. (2022). GEDI L4B Gridded AGB Density, V2. ORNL DAAC. doi:10.3334/ORNLDAAC/2017
5. Duncanson, L. et al. (2022). "AGB density models for GEDI." *Remote Sensing of Environment* 270:112845
6. Lang, N. et al. (2023). "A high-resolution canopy height model of the Earth." *Nature Ecology & Evolution*
7. Harris, N.L. et al. (2021). "Global maps of 21st century forest carbon fluxes." *Nature Climate Change* 11:234-240
8. Spawn, S.A. et al. (2020). "Global AGB and BGB biomass carbon density maps." *Scientific Data*
9. Shimada, M. et al. (2014). "New global forest/non-forest maps from ALOS PALSAR." *Remote Sensing of Environment* 155:13-31
10. Patterson, P.L. et al. (2019). "Statistical properties of hybrid estimators for GEDI." *Environmental Research Letters* 14:065007
11. Araza, A. et al. (2023). "Past decade AGB change comparisons from four multi-temporal global maps." *IJAEOG*
12. Yang, H. et al. (2023). "Global increase in biomass carbon stock." *Nature Geoscience*
13. Mo, L. et al. (2023). "Integrated global assessment of natural forest carbon potential." *Nature*
14. Hunka, N. et al. (2023). "On the GEDI and CCI biomass maps: aligning for UNFCCC." *ERL*

---

*Document prepared for the Silvi/Treekipedia SINR v3 development team.*
*Last updated: 2026-02-25*
