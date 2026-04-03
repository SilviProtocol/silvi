# Strategic Research Report: Pre-Hansen Plantation Detection & Foundation Models for Treekipedia

**Date:** February 18, 2026  
**Context:** Treekipedia species prediction system — distinguishing plantations from natural forests, detecting pre-2000 land use change, and identifying cutting-edge tools for forest intelligence  
**Test Case:** Pinus radiata plantation at (-41.15, 175.10) in New Zealand, planted ~1997, showing treecover2000=90% with no Hansen loss/gain  

---

## Table of Contents

1. [The Core Problem: Hansen's Blind Spot](#1-the-core-problem-hansens-blind-spot)
2. [Clay Foundation Model](#2-clay-foundation-model)
3. [Prithvi (NASA/IBM) Foundation Model](#3-prithvi-nasaibm-foundation-model)
4. [DINOv2 for Remote Sensing](#4-dinov2-for-remote-sensing)
5. [Carbon Accumulation / Growth Rate as a Signal](#5-carbon-accumulation--growth-rate-as-a-signal)
6. [Landsat Time Series Analysis (1984-Present)](#6-landsat-time-series-analysis-1984-present)
7. [Historical Land Use from Pre-Satellite Era](#7-historical-land-use-from-pre-satellite-era)
8. [TorchGeo Framework](#8-torchgeo-framework)
9. [Land Carbon Lab / WRI Tree Mapping](#9-land-carbon-lab--wri-tree-mapping)
10. [The Canopy Height Paper (Tolan et al. 2024)](#10-the-canopy-height-paper-tolan-et-al-2024)
11. [Foundation Model Comparison Matrix](#11-foundation-model-comparison-matrix)
12. [Dual/Multi-Embedding Strategy for Treekipedia](#12-dualmulti-embedding-strategy-for-treekipedia)
13. [What Could Be Built on Treekipedia's Data](#13-what-could-be-built-on-treekipedias-data)
14. [WRI Comparison & Going Beyond](#14-wri-comparison--going-beyond)
15. [Novel Applications](#15-novel-applications)
16. [Additional Foundation Models & Papers (2023-2025)](#16-additional-foundation-models--papers-2023-2025)
17. [Implementation Roadmap](#17-implementation-roadmap)
18. [Conclusions & Recommendations](#18-conclusions--recommendations)

---

## 1. The Core Problem: Hansen's Blind Spot

### The Scenario
Our NZ test location (-41.15, 175.10) is a 28-year-old Pinus radiata plantation planted circa 1997. Hansen Global Forest Change (GFC) reports:
- **treecover2000** = 90% (plantation was already 3+ years old, had established canopy)
- **loss** = 0 (no detected deforestation)
- **gain** = 0 (no detected reforestation — because it was already "forest")

Hansen GFC treats this location identically to an old-growth native podocarp-broadleaf forest. This is a fundamental limitation because:

1. **No pre-2000 baseline**: Hansen's year-2000 snapshot cannot distinguish "forest that has always been there" from "forest planted on cleared land in the 1990s"
2. **No forest type classification**: Hansen measures canopy cover percentage, not forest composition, structure, or origin
3. **No growth rate signal**: A fast-growing 3-year-old Pinus radiata plantation and a centuries-old Dacrydium cupressinum forest both register as "high canopy cover"
4. **No rotation cycle detection**: Plantation forests are harvested and replanted on 25-30 year cycles, but if this happens between Hansen snapshots, it might be missed entirely

### What We Need to Detect
For Treekipedia's species prediction to be accurate, we need signals that can determine:
- **Is this a plantation or natural forest?** (forest type classification)
- **How old is this forest stand?** (forest age/growth stage)
- **Was this previously cleared land?** (land use history)
- **What is the growth trajectory?** (carbon accumulation rate)
- **What species are likely present?** (spectral/structural signatures of monoculture vs mixed)

---

## 2. Clay Foundation Model

### What It Is
Clay is an open-source AI foundation model for Earth observation data, developed by the Clay Foundation (a fiscally sponsored project of Radiant Earth, a 501c3 non-profit). Current version is **v1.5**, released November 2024, with code on GitHub under Apache-2.0 license.

### Architecture
- **Base**: Vision Transformer (ViT) with Masked Autoencoder (MAE) pre-training
- **Model size**: 632M total parameters (311M encoder, 15M decoder, 304M DINOv2 teacher)
- **Key innovation — Dynamic Embedding Block**: Generates patches from any number of bands using their wavelengths, making it sensor-agnostic
- **Position Encoding**: Encodes spatial (lat/lon) and temporal (week/hour) information, scaled by Ground Sampling Distance (GSD)
- **DINOv2 teacher**: Uses DINOv2 for representation loss (5% of total loss), with reconstruction loss being 95%
- **Training**: 70M globally distributed chips of 256x256, trained on 20 AWS g6.48xlarge instances (160 L4 GPUs) for ~100 epochs

### Satellite Inputs
Clay v1.5 supports multi-sensor inputs:
- **Sentinel-2**: 10 bands (10m-60m resolution)
- **Sentinel-1 SAR**: 2 bands (VV, VH)
- **Landsat 8/9**: 6 bands (30m resolution)
- **NAIP**: 4 bands (RGB + NIR, sub-meter)
- **LINZ**: 3 bands (RGB, NZ-specific aerial imagery)
- **MODIS**: 7 bands (250m-500m resolution)

**Critical NZ Detail**: LINZ (Land Information New Zealand) aerial imagery is explicitly included as a training data source. This means Clay has been specifically trained on NZ imagery, which is extremely relevant for our test case.

### Fine-tuning Capabilities
Clay provides documented fine-tuning examples for:
- **Segmentation** (Chesapeake Bay land cover)
- **Classification** (EuroSAT — 10 land use classes)
- **Regression** (BioMassters — above-ground biomass estimation)
- **Embeddings-based fine-tuning** (train downstream models on pre-computed embeddings)

### Could It Help Detect 25+ Year Old Plantations?
**YES, with fine-tuning.** Here's why:

1. **Spectral signatures**: Pinus radiata monocultures have distinct spectral signatures compared to native NZ broadleaf-podocarp forests. The near-infrared reflectance patterns differ significantly between conifer plantations and broadleaf forests. Clay's multi-band input can capture these differences.

2. **Structural signatures via SAR**: Sentinel-1 SAR data (included in Clay's inputs) is sensitive to forest structure. Plantation monocultures have uniform canopy texture (same-age, same-species), while natural forests have heterogeneous texture. This structural difference is detectable in SAR backscatter patterns.

3. **Temporal embedding**: Clay encodes time information. By feeding multi-temporal inputs, we could capture phenological differences. Pinus radiata is evergreen but has distinct seasonal growth patterns different from native species.

4. **NZ-trained**: Clay was trained on LINZ data, meaning it already has representations of NZ landscapes including plantation forests.

### Implementation Complexity
- **Medium**. Clay is pip-installable, has documented fine-tuning pipelines, and outputs 1024-D embeddings.
- Fine-tuning requires labeled training data for "plantation" vs "natural forest" — we would need to create or source this for NZ.
- NZ LCDB (Land Cover Database) could serve as training labels for plantation vs native forest classification.

### GEE Availability
- Clay embeddings are **not** directly available in GEE.
- Clay is a PyTorch model that runs locally or on cloud compute.
- Clay embeddings have been published on Source Cooperative.
- Integration would require computing embeddings externally and joining them to our GEE pipeline.

### Key Limitations
- Training data covers land only, not open ocean or poles
- Only trained on 6 different time points per location maximum
- No explicit change detection objective in pre-training (pure MAE reconstruction)
- No GEE native integration — must run inference externally

### Comparison to AlphaEarth
| Feature | Clay v1.5 | AlphaEarth |
|---------|-----------|------------|
| Embedding dim | 1024-D | 64-D |
| Sensors | S1, S2, L8/9, NAIP, LINZ, MODIS | S2 + environmental layers |
| Temporal | Multi-temporal with time encoding | Single-snapshot |
| Architecture | ViT-MAE + DINOv2 teacher | Proprietary (Google) |
| Open source | Yes (Apache-2.0) | No (API access) |
| GEE native | No | Yes |
| Global coverage | Yes | Yes |
| Forest-specific | No (general EO) | No (general EO) |
| NZ training | Yes (LINZ data) | Unknown |

### Dual Embedding Strategy: Clay + AlphaEarth
A dual-embedding approach would combine:
- **AlphaEarth 64-D**: Environmental/spectral context already integrated into Treekipedia (GEE-native, fast, global)
- **Clay 1024-D**: Richer multi-sensor, multi-temporal representation with structural information from SAR

This could be implemented as:
```
combined_embedding = concat(alpha_earth_64d, clay_1024d)  # 1088-D
# Or via learned fusion:
fused = MLP(concat(alpha_earth_64d, clay_1024d))  # → 128-D
```

Benefits: AlphaEarth captures environmental niche, Clay captures structural/spectral forest characteristics. Together they would be far more powerful at distinguishing plantation from natural forest.

---

## 3. Prithvi (NASA/IBM) Foundation Model

### What It Is
Prithvi is a family of AI foundation models for Earth developed jointly by IBM, NASA, and Jülich Supercomputing Centre. There are two branches:

1. **Prithvi-EO (Earth Observation)**: For land surface applications — the relevant one for us
2. **Prithvi-WxC (Weather & Climate)**: 2.3B parameter model for weather forecasting — not relevant for plantation detection

### Prithvi-EO-2.0 (Current Generation)
- **Architecture**: ViT with MAE pre-training, 3D patch embeddings for spatiotemporal inputs
- **Model sizes**: tiny (5M), 100M, 300M, 600M parameter variants
- **TL variants**: Include temporal and location embeddings (latitude/longitude + date of acquisition)
- **Training data**: NASA's Harmonized Landsat and Sentinel-2 (HLS) V2 product at 30m granularity
- **Training scale**: 4.2M samples with six bands (Blue, Green, Red, Narrow NIR, SWIR, SWIR 2)
- **Trained at**: Jülich Supercomputing Centre

### Key Features for Plantation Detection
1. **Temporal location awareness (TL models)**: The `-TL` variants encode both geolocation (lat/lon) and temporal information (year, day-of-year). This is critical because the model can learn location-dependent seasonal patterns.

2. **Multi-temporal 3D architecture**: Uses 3D convolutional patch embeddings that process sequences of T images at (H,W) spatial dimensions. This is explicitly designed for change detection and temporal analysis.

3. **HLS data source**: Harmonized Landsat-Sentinel-2 provides consistent, analysis-ready surface reflectance data from both Landsat and Sentinel-2, extending back to the 1980s through Landsat.

4. **Demonstrated fine-tuning tasks**:
   - Multi-temporal crop classification
   - Burn scar detection (Sen1Floods11)
   - Landslide segmentation
   - Carbon flux prediction (regression)

### Can It Detect Pre-2000 Plantations from Landsat Time Series?
**YES, this is potentially the most powerful tool for this task.** Here's why:

1. **Landsat temporal depth**: HLS integrates Landsat data going back to 1984 (Landsat 5 TM). This means Prithvi could potentially be fine-tuned on Landsat time series spanning 1984-2000, which would cover the period when our NZ plantation was established.

2. **Multi-temporal architecture**: The 3D ViT architecture processes image sequences natively. You could feed it a time series of Landsat images from 1990-2000 and it would learn the spectral trajectory of "grassland → young plantation → established plantation."

3. **Change detection capability**: The MAE pre-training on multi-temporal data means the model has learned representations of temporal change. Fine-tuning for "plantation establishment detection" is conceptually similar to their existing burn scar and crop classification tasks.

4. **Carbon flux regression**: The model has already been fine-tuned for carbon flux prediction, which is closely related to biomass accumulation rate estimation.

### Implementation Complexity
- **Medium-High**. Available on HuggingFace, fine-tuned via IBM TerraTorch framework.
- Would require creating training labels for "plantation establishment" events in NZ (or globally).
- The temporal dimension requires assembling Landsat time series for training locations.
- The TL variants need geolocation and date metadata, which we have.

### GEE Availability
- Prithvi is **not** directly available in GEE.
- However, the input data (HLS) is available in GEE as `NASA/HLS/HLSS30/v002` and `NASA/HLS/HLSL30/v002`.
- Running Prithvi would require external compute (e.g., Google Cloud, AWS, or local GPU).
- Results could be ingested back into GEE as Earth Engine assets.

### Key Limitations
- Training data is HLS-specific (6 bands), so adding SAR would require retraining
- No SAR integration (unlike Clay)
- 30m resolution — cannot detect individual trees
- HLS temporal coverage varies by location (some areas have sparse Landsat records in the 1980s-1990s)
- Pre-2000 Landsat data (Landsat 5 TM) has different band configurations than HLS

### Fine-Tuning for Forest Type Classification
The approach would be:
1. Assemble multi-temporal HLS (or Landsat) stacks for known plantation and natural forest locations
2. Use NZ LCDB or LUCAS data as training labels
3. Fine-tune Prithvi-EO-2.0-300M-TL on the classification task
4. The TL variant would learn NZ-specific seasonal patterns automatically

TerraTorch makes this relatively straightforward:
```python
from terratorch.registry import BACKBONE_REGISTRY
model = BACKBONE_REGISTRY.build("prithvi_eo_v2_300m_tl", pretrained=True)
```

---

## 4. DINOv2 for Remote Sensing

### What It Is
DINOv2 is Meta AI's self-supervised vision foundation model, trained on 142M images from the internet (LVD-142M dataset). It produces high-quality visual features that work across domains without fine-tuning. Available in sizes from ViT-S/14 (21M params) to ViT-g/14 (1.1B params).

### Key Architecture Details
- **Self-supervised learning**: Uses a combination of image-level and patch-level objectives (DINO loss + iBOT loss + SwAV loss)
- **ViT backbone**: Standard Vision Transformer with 14x14 patch size
- **Registers** (newer version): Added register tokens to improve attention maps
- **DINOv3**: A newer version was released in August 2025, continuing this line of work
- **dino.txt**: Vision-language alignment added December 2024

### Application to Satellite Imagery
DINOv2 has been **directly used** for satellite/remote sensing tasks:

1. **WRI/Meta Canopy Height Maps**: The landmark 1-meter global canopy height dataset was built using DINOv2 as the backbone. Meta trained DINOv2 on 18M satellite images, then fine-tuned a depth estimation head for canopy height prediction. This is the most significant RS application of DINOv2 to date.

2. **Channel-Adaptive DINO** (December 2025): Meta released a channel-adaptive extension of DINOv2 that can handle inputs with arbitrary numbers of channels. This is directly relevant because satellite imagery has more than 3 channels. Paper: "Scaling Channel-Adaptive Self-Supervised Learning" (NeurIPS 2025 area).

3. **Cell-DINO**: Demonstrates that DINOv2 can be adapted to domain-specific microscopy images, proving the architecture generalizes beyond natural images.

### Has Anyone Fine-Tuned DINOv2 for Remote Sensing?
**Yes, extensively:**

1. **Canopy height mapping** (Tolan et al., 2024) — Meta/WRI: Used DINOv2 ViT-Huge backbone pretrained on satellite imagery with NEON LIDAR as ground truth. Achieved global 1m canopy height maps.

2. **Land cover classification**: Multiple papers have shown DINOv2 features outperform ImageNet-pretrained models on EuroSAT, UC Merced, and other RS benchmarks, even with a simple linear probe.

3. **Forest type classification**: DINOv2 features have been used for forest/non-forest classification and forest type discrimination in European forests.

4. **Change detection**: DINOv2 patch features have been used for bi-temporal change detection by computing feature similarity between two time points.

### Comparison: DINOv2 vs AlphaEarth vs Clay vs Prithvi

| Feature | DINOv2 | AlphaEarth | Clay v1.5 | Prithvi-EO-2.0 |
|---------|--------|------------|-----------|----------------|
| **Type** | General vision FM | EO embedding service | EO FM | EO FM |
| **Architecture** | ViT (DINO+iBOT) | Proprietary | ViT-MAE | ViT-MAE |
| **Pre-training data** | 142M natural images | Sentinel-2 + env layers | Multi-sensor EO | HLS (L+S2) |
| **Input channels** | 3 (RGB) standard | Multi-band | Any # bands | 6 bands |
| **Temporal** | Single image | Single snapshot | Multi-temporal | Multi-temporal 3D |
| **SAR support** | No | No | Yes (S1) | No |
| **Spatial awareness** | No geolocation | Unknown | Yes (lat/lon + time) | Yes (TL variants) |
| **Embedding dim** | 384-1536 | 64 | 1024 | Varies by model |
| **Open source** | Yes (Apache-2.0) | No | Yes (Apache-2.0) | Yes (Apache-2.0) |
| **GEE native** | No | Yes | No | No |
| **Parameters** | 21M-1.1B | Unknown | 632M | 5M-600M |
| **RS fine-tuning** | Proven (canopy height) | N/A | Proven | Proven |
| **Forest tasks** | Canopy height, LULC | General embedding | Biomass regression | Crop/burn/carbon |
| **Global scale** | Yes | Yes | Yes | Yes |
| **Best for** | High-res RGB analysis | Quick embedding lookup | Multi-sensor fusion | Temporal analysis |

### For Plantation Detection Specifically
DINOv2 alone is **less suitable** than Clay or Prithvi because:
- It only handles 3-channel (RGB) input natively (though Channel-Adaptive DINO changes this)
- No temporal modeling
- No geospatial awareness
- However, when adapted for satellite imagery (as in the canopy height work), it's extremely powerful
- The Channel-Adaptive DINO variant (December 2025) could be fine-tuned on multi-spectral satellite data

### Implementation Complexity
- **Low** for using pre-trained features on RGB satellite imagery
- **Medium** for fine-tuning on multi-spectral data (requires Channel-Adaptive DINO)
- Available via PyTorch Hub: `torch.hub.load('facebookresearch/dinov2', 'dinov2_vitl14')`

---

## 5. Carbon Accumulation / Growth Rate as a Signal

### The Key Insight
Plantations and natural forests have fundamentally different carbon accumulation trajectories:

- **Young plantations (0-15 years)**: Extremely rapid growth. Pinus radiata in NZ can accumulate 15-25 tonnes CO2/ha/year.
- **Mature plantations (15-30 years)**: Growth slows but remains high. Pinus radiata accumulates 10-15 t CO2/ha/yr before harvest.
- **Old-growth natural forest**: Near carbon equilibrium. Growth ≈ decomposition. Net accumulation near 0 or slightly positive (1-3 t CO2/ha/yr).
- **Mature natural forest (secondary)**: 5-10 t CO2/ha/yr, but with heterogeneous structure.

This means: **If we can estimate carbon accumulation rate from remote sensing, we can distinguish plantation age classes from natural forest.**

### Available Biomass/Carbon Datasets

#### 1. GEDI (Global Ecosystem Dynamics Investigation)
- **What**: Spaceborne LIDAR on ISS, measuring forest canopy height and vertical structure
- **Resolution**: 25m footprints along orbital tracks (not wall-to-wall)
- **Temporal**: 2019-present (ongoing)
- **Key products**: L4A (Aboveground Biomass Density), L4B (gridded AGB at 1km)
- **GEE**: `LARSE/GEDI/GEDI02_A_002_MONTHLY`, `LARSE/GEDI/GEDI04_A_002`
- **Limitation for our case**: Only covers 2019-present, so cannot capture pre-2000 plantation establishment. But current biomass density IS useful as a snapshot.
- **Coverage**: Between 51.6°N and 51.6°S latitude (ISS orbital inclination) — our NZ test site at -41.15° IS within range.

#### 2. ICESat-2 (ATLAS)
- **What**: Spaceborne photon-counting LIDAR
- **Resolution**: Individual photon returns along orbital tracks
- **Temporal**: 2018-present
- **Products**: ATL08 (Land and Vegetation Height)
- **Key advantage**: Can measure canopy height at fine resolution
- **Temporal analysis**: If we compare ICESat-2 measurements from 2018-2026, we can estimate canopy height growth rate for individual forest stands

#### 3. ESA CCI Biomass
- **What**: Global above-ground biomass maps at 100m resolution
- **Temporal**: 2010, 2017, 2018, 2019, 2020 (five epochs)
- **GEE**: Not natively available but can be ingested
- **Plantation detection value**: Comparing 2010 vs 2020 biomass could show plantation growth patterns. A Pinus radiata stand planted in 1997 would have been ~13 years old in 2010 (~100 t/ha AGB) and ~23 years old in 2020 (~180 t/ha AGB), showing rapid increase. An old-growth forest would show minimal change.

#### 4. GLAD Global Forest Height (Potapov et al.)
- **What**: Forest canopy height at 30m resolution for years 2000 and 2020, calibrated with GEDI
- **GEE**: `projects/glad/GLCLU2020/Forest_height_2000` and `projects/glad/GLCLU2020/Forest_height_2020`
- **Plantation detection value**: **EXTREMELY HIGH.** By comparing forest height 2000 vs 2020:
  - Our Pinus radiata plantation at (-41.15, 175.10) would show: Height_2000 ≈ 3-5m (3-year-old trees), Height_2020 ≈ 25-35m (23-year-old trees). That's ~20-30m of height gain in 20 years.
  - An old-growth native forest would show: Height_2000 ≈ 25-35m, Height_2020 ≈ 25-35m. Minimal change.
  - **The height gain signal is a direct discriminator between young plantations and old-growth forests.**
- This is available in GEE right now and should be immediately integrated.

#### 5. NASA CMS (Carbon Monitoring System) Biomass
- **What**: Various AGB products at 30m-1km resolution for different regions/years
- **Limitation**: Regional products, not always global
- **Some products available in GEE**

#### 6. Meta/WRI 1m Canopy Height
- **What**: Global 1m resolution canopy height from DINOv2 + satellite imagery
- **Temporal**: Mosaic from 2009-2020 (mostly 2018-2020)
- **GEE**: Available via Earth Engine Community Catalog and official app
- **Plantation detection value**: Single-epoch but at 1m resolution could show plantation row structure vs natural forest heterogeneity

### Carbon Accumulation Rate as a Discriminator

The approach would be:

1. **Compute height change**: `delta_h = GLAD_Height_2020 - GLAD_Height_2000`
2. **Convert to AGB change**: Using allometric equations (species-dependent, but generalizable)
3. **Convert to carbon accumulation rate**: `C_rate = delta_AGB * 0.47 / 20_years`
4. **Classify**:
   - `C_rate > 10 t CO2/ha/yr` → likely young/active plantation
   - `C_rate 3-10 t CO2/ha/yr` → secondary/regenerating forest or mature plantation
   - `C_rate < 3 t CO2/ha/yr` → mature/old-growth natural forest
   - `C_rate < 0` → disturbed/degrading forest

For our NZ test case:
- Pinus radiata at 28 years: Height ~30m, AGB ~200 t/ha, C_rate ≈ 12-15 t CO2/ha/yr → **clearly plantation**
- Native podocarp forest: Height ~25-35m, AGB ~250 t/ha, C_rate ≈ 0-2 t CO2/ha/yr → **clearly natural**

### Implementation Complexity
- **LOW for GLAD height change** — data is already in GEE, just need to compute the difference
- **MEDIUM for GEDI/ICESat-2 temporal** — requires assembling multi-year datasets along sparse orbital tracks
- **HIGH for wall-to-wall carbon accumulation** — requires integrating multiple data sources and allometric models

### Recommendation
**GLAD Forest Height Change (2000-2020) should be the FIRST new signal added to Treekipedia's GEE pipeline.** It is:
- Already in GEE
- 30m resolution (matches our current pipeline)
- Directly discriminates plantation from natural forest
- Global coverage
- No ML needed — simple arithmetic

---

## 6. Landsat Time Series Analysis (1984-Present)

### Why This Matters
Landsat provides the only satellite record that extends before Hansen's 2000 baseline. The Landsat archive begins with Landsat 1 (1972) and achieves consistent multi-spectral coverage from Landsat 5 TM (1984). This 40+ year record can directly reveal:
- When a forest was established
- Whether land was previously cleared
- Plantation rotation cycles (clear-cut → replant → grow → harvest → replant)
- Gradual vs sudden forest change

### Key Algorithms

#### 1. LandTrendr (Landsat-based Detection of Trends in Disturbance and Recovery)
- **What**: Algorithm that fits temporal segments to pixel-level time series of spectral indices, detecting breakpoints that correspond to disturbance and recovery events
- **Developer**: Robert Kennedy, Oregon State University
- **How it works**: Takes annual Landsat surface reflectance composites, computes spectral indices (NDVI, NBR, SWIR, etc.), fits piecewise linear segments to the time series, identifies significant breakpoints
- **What it detects**:
  - **Disturbance events**: Clear-cutting, fire, disease, windthrow
  - **Recovery trajectories**: How quickly vegetation re-establishes after disturbance
  - **Gradual change**: Slow forest degradation, gradual plantation growth
  - **Rotation cycles**: Repeated harvest-replant patterns visible as sawtooth patterns
- **GEE availability**: **YES** — via `users/emaprlab/public:Modules/LandTrendr.js` library
- **Temporal range**: 1984-present (40+ years)
- **Resolution**: 30m (Landsat pixel)

**For our NZ plantation case**: LandTrendr analysis of the 1984-2000 period could detect:
1. A stable grassland/pasture spectral signal from 1984-1995
2. A sudden spectral change in ~1996-1997 (land clearing and planting)
3. A gradual increase in NDVI/NBR from 1997-2000 (young plantation establishment)
4. Continued canopy development through 2000-2026

This would **directly prove** that the location was planted, not natural forest.

#### 2. CCDC (Continuous Change Detection and Classification)
- **What**: Algorithm that continuously monitors Landsat time series for change using harmonic regression models
- **Developer**: Zhe Zhu, University of Connecticut (originally Boston University)
- **How it works**: Fits harmonic (seasonal) models to the full Landsat time series at pixel level. When observations deviate significantly from the model, a break is detected. After the break, a new model is fitted.
- **What it stores**: For each pixel, CCDC stores multiple "segments" — each segment has: start date, end date, harmonic coefficients for each band, and break magnitude
- **GEE availability**: **YES** — `GOOGLE/GLOBAL_CCDC/V1` (global precomputed results)
- **Key advantage**: The harmonic coefficients encode the seasonal cycle of the pixel. Different land cover types have different seasonal patterns. This means CCDC coefficients can be used to classify land cover type AND detect when changes occurred.

**For our NZ plantation case**: The global CCDC product (`GOOGLE/GLOBAL_CCDC/V1`) would contain:
1. A segment from ~1984-1996 with harmonic coefficients consistent with grassland/pasture
2. A break point at ~1996-1997
3. A new segment from ~1997-present with harmonic coefficients transitioning from bare/sparse vegetation to dense conifer forest
4. The change date would be precisely identified, proving plantation establishment

**Critical finding**: `GOOGLE/GLOBAL_CCDC/V1` is a **pre-computed global dataset** already in GEE. We don't need to run the algorithm ourselves — Google has already processed the entire Landsat archive.

#### 3. CODED (COntinuous DEgradation Detection)
- **What**: Extension of CCDC specifically designed for detecting forest degradation in tropical forests
- **Less relevant for NZ plantation detection** but useful for tropical applications of Treekipedia

#### 4. TimeFirst (Temporally Fused Imagery for Forest Change)
- **What**: Newer approach that fuses Landsat and Sentinel-2 time series for higher temporal resolution change detection
- **Relevant**: Would improve detection accuracy from 2015 onwards when both sensors are available

### Using CCDC for Treekipedia
The `GOOGLE/GLOBAL_CCDC/V1` dataset in GEE contains pre-computed CCDC results for every Landsat pixel globally. Here's what we can extract for any location:

```javascript
// Load CCDC
var ccdc = ee.ImageCollection('GOOGLE/GLOBAL_CCDC/V1');

// Get segments for our NZ test location
var point = ee.Geometry.Point([175.10, -41.15]);
var segments = ccdc.filterBounds(point);

// Each pixel has:
// - tStart: start date of each segment
// - tEnd: end date of each segment
// - tBreak: date of break (change event)
// - changeProb: probability that a change occurred
// - BLUE_coefs, GREEN_coefs, RED_coefs, NIR_coefs, SWIR1_coefs, SWIR2_coefs: 
//   harmonic coefficients for each band
// - BLUE_rmse, etc.: fit quality metrics
```

From CCDC we can derive:
- **Number of segments** (number of land cover changes)
- **Date of most recent break** (when was the last change?)
- **Pre-break vs post-break spectral characteristics** (what changed to what?)
- **Harmonic amplitude ratios** (indicator of vegetation type — conifers vs broadleaf vs grassland)

### Implementation Complexity
- **LOW for CCDC** — pre-computed data already in GEE, just need to query segments
- **MEDIUM for LandTrendr** — need to run the algorithm in GEE (available as library, but requires some GEE JavaScript)
- Both produce **per-pixel** results that can be integrated into our existing GEE pipeline

### GEE Availability Summary
| Algorithm | GEE Asset | Pre-computed? | Temporal Range |
|-----------|-----------|---------------|----------------|
| CCDC | `GOOGLE/GLOBAL_CCDC/V1` | Yes (global) | 1985-2024 |
| LandTrendr | Library (need to run) | No | 1984-present |
| Hansen GFC | `UMD/hansen/global_forest_change_2023_v1_11` | Yes (global) | 2000-2023 |
| GLAD GLCLUC | `projects/glad/GLCLU2020/` | Yes (global) | 2000, 2020 |

### Recommendation
**CCDC (`GOOGLE/GLOBAL_CCDC/V1`) should be the SECOND new signal added to Treekipedia's GEE pipeline.** It provides:
- Pre-2000 change detection (solves the Hansen blind spot)
- Segment dates that reveal land use history
- Harmonic coefficients that encode vegetation type
- Already pre-computed globally in GEE
- No external compute needed

Derived variables to add:
- `ccdc_num_segments`: Number of land cover changes detected
- `ccdc_last_break_year`: Year of most recent change
- `ccdc_pre_break_ndvi`: NDVI before last change
- `ccdc_post_break_ndvi`: NDVI after last change
- `ccdc_break_magnitude`: Magnitude of spectral change
- `ccdc_years_since_break`: Time since last detected change

---

## 7. Historical Land Use from Pre-Satellite Era

### HILDA+ (Historic Land Dynamics Assessment, 1960-2019)
- **What**: Global 1km resolution reconstruction of land use/land cover changes from 1960 to 2019
- **Developer**: Karina Winkler, University of Wageningen / Karlsruhe Institute of Technology
- **Resolution**: 1km (very coarse)
- **Classes**: Urban, Cropland, Pasture/rangeland, Forest, Unmanaged grass/shrubland, Sparse/bare vegetation
- **How it works**: Synthesizes multiple data sources including FAO country statistics, historical land use maps, and remote sensing
- **NZ coverage**: Yes, but at 1km resolution the plantation vs natural forest distinction is likely too coarse
- **Useful for**: Understanding regional-scale land use trends, but NOT for pixel-level plantation detection
- **GEE**: Not natively available

### NZ LCDB (Land Cover Database)
- **What**: New Zealand national land cover database produced by Manaaki Whenua (Landcare Research)
- **Versions**: LCDB v1 (1996/97), v2 (2001/02), v3.3 (2008/09), v4.1 (2012/13), v5.0 (2018/19)
- **Resolution**: Based on manual interpretation of aerial/satellite imagery, polygon-based (vector data)
- **Relevant classes**:
  - **Exotic Forest**: Includes planted forest (Pinus radiata, Douglas fir, etc.)
  - **Indigenous Forest**: Native/natural forest
  - **Exotic Grassland**: Pasture (what existed before the plantation was planted)
  - **Harvested Forest**: Recently harvested plantation
- **Critical value**: LCDB v1 (1996/97) would show our test location as either "Exotic Grassland" (if just planted) or "Exotic Forest" (if already classified as plantation by 1996). LCDB v2 (2001/02) would confirm "Exotic Forest."
- **NZ-specific**: Obviously region-specific, but for NZ plantation detection, this is ground truth.
- **GEE**: Not natively available, but can be imported as a GEE asset from the LRIS portal.

### NZ LUCAS (Land Use and Carbon Analysis System)
- **What**: NZ's national system for tracking land use and carbon stock changes under the Kyoto Protocol
- **Developed by**: Ministry for the Environment (MfE)
- **Versions**: Land use maps for 1990, 2008, 2012, 2016
- **Critical value**: The 1990 map would show our test site as grassland/pasture (before planting). The 2008 map would show it as exotic forest.
- **Resolution**: Based on aerial imagery interpretation
- **Limitation**: NZ-specific, but highly authoritative for NZ

### Global Datasets Going Back to 1970s-1980s
1. **Landsat MSS archive (1972-1984)**: Raw imagery available but very limited spectral and spatial resolution (80m, 4 bands). Processing would be complex.
2. **NOAA AVHRR (1981-present)**: Global daily imagery at ~1km resolution. NDVI time series going back to 1981. Too coarse for plantation-level detection but useful for regional trends.
3. **JRC Global Surface Water (1984-present)**: Tracks water extent changes, useful as complementary signal.
4. **Ramankutty & Foley Historical Cropland (1700-1992)**: 0.5° resolution, too coarse.
5. **KK10 Historical Land Use (1000 BC - 2005)**: Very coarse, reconstructed from population/economic data.
6. **HYDE 3.2**: Historical database of the global environment, 5-minute resolution, 10000 BC to 2017.

### Recommendation for NZ Specifically
For our NZ test case, **NZ LCDB is the definitive data source** for distinguishing plantation from natural forest. It provides authoritative polygon-based land cover classification with explicit "Exotic Forest" vs "Indigenous Forest" classes going back to 1996.

For the global Treekipedia system, the approach should be:
1. Use CCDC and LandTrendr for satellite-derived historical land use globally
2. Where available, integrate national/regional datasets like LCDB (NZ), CORINE (Europe), NLCD (US), MapBiomas (Brazil)
3. Use HILDA+ as a coarse contextual layer

---

## 8. TorchGeo Framework

### What It Is
TorchGeo is a PyTorch domain library (like torchvision, but for geospatial data) providing datasets, samplers, transforms, and pre-trained models. It's an OSGeo project with 3.9k GitHub stars, 517 forks, and is published in ACM TOSAS (2025). Current version: v0.9.0 (February 2026).

### Key Capabilities for Forest Classification
1. **Pre-trained weights for multispectral models**: TorchGeo is the first library to provide models pre-trained on different multispectral sensors:
   - ResNet-18/50 pre-trained on Sentinel-2 (all 13 bands) via MoCo
   - Models pre-trained on Landsat, NAIP, and other sensors
   - These weights are much better starting points for RS tasks than ImageNet weights

2. **Geospatial dataset handling**: Automatic CRS reprojection, bounding box intersection, temporal overlap — handles the messy reality of geospatial data

3. **Relevant pre-built datasets**:
   - **EuroSAT**: 10 land cover classes including forest, from Sentinel-2
   - **BigEarthNet**: 19 or 43 LULC classes from Sentinel-1 and Sentinel-2
   - **TreeSatAI**: Multi-label tree species classification from aerial imagery
   - **ForestDamage**: Aerial imagery for forest damage detection
   - **NLCD**: National Land Cover Database (US) — includes forest type classes
   - **EnviroAtlas**: Urban tree canopy mapping
   - **Chesapeake Bay**: High-resolution land cover including forest

4. **Trainers**: Pre-built Lightning training pipelines for classification, regression, segmentation, change detection

### TreeSatAI Dataset
- **What**: Multi-label tree species classification from aerial imagery and Sentinel-1/2
- **Classes**: 20 tree species/genera including Pinus, Picea, Quercus, Fagus, etc.
- **Resolution**: 20cm aerial imagery + 10m Sentinel-2 + SAR
- **Location**: Germany
- **Relevance**: Could be used to train a plantation species classifier, though it's European-focused

### Integration with Treekipedia
TorchGeo could serve as the ML framework for training custom models on top of foundation model embeddings. The workflow would be:

1. Use TorchGeo's `GeoDataset` classes to load Landsat/Sentinel time series
2. Use TorchGeo's `RandomGeoSampler` to sample training patches from known plantation/natural forest locations
3. Fine-tune a classifier (using TorchGeo's `ClassificationTask`) on embeddings from Clay, Prithvi, or DINOv2
4. Use TorchGeo's `SemanticSegmentationTask` for wall-to-wall plantation mapping

### Implementation Complexity
- **LOW** for using pre-trained weights on standard tasks
- **MEDIUM** for custom dataset creation and fine-tuning
- `pip install torchgeo` — straightforward installation

### Key Limitation
- TorchGeo is a framework, not a model. It provides the plumbing but you still need training data and a problem formulation.
- Focused on PyTorch workflows — doesn't integrate with GEE directly.

---

## 9. Land Carbon Lab / WRI Tree Mapping

### What It Is
The Land & Carbon Lab is a WRI initiative that develops global data products for monitoring land cover, carbon, and restoration. Their partnership with Meta produced the landmark 1-meter global canopy height dataset.

### Key Data Products

#### 1. 1-Meter Global Canopy Height (Meta/WRI)
- **Resolution**: 1 meter (sub-tree scale)
- **Coverage**: Global land area
- **Temporal**: Mosaic from 2009-2020 (80% from 2018-2020)
- **Method**: DINOv2 foundation model trained on 18M satellite images, fine-tuned on NEON LIDAR
- **Detection threshold**: Trees >1m tall with canopy diameter >3m
- **Finding**: >1/3 of Earth's land (50M km²) is covered by trees >1m tall
- **GEE**: Available via `meta-forest-monitoring-okw37.projects.earthengine.app/view/canopyheight` and Earth Engine Community Catalog
- **AWS**: `s3://dataforgood-fb-data/forests/v1/`
- **License**: Open, commercial use permitted

#### 2. Tropical Tree Cover
- **Resolution**: 10m (Sentinel-2 based)
- **Key innovation**: Detects trees in non-forest landscapes (agroforestry, drylands, savannas)
- **Versions**: Multiple iterations since 2021

#### 3. Tree Cover Gain
- **What**: Tracks new tree establishment globally
- **Resolution**: 30m (Landsat-based)

#### 4. Land Disturbance Alert Classification System
- **What**: Near-real-time alerts for land disturbance events
- **Classifies**: Deforestation, fire, flooding, agricultural expansion

#### 5. Dynamic World (Google/WRI collaboration)
- **What**: Near-real-time global land cover mapping at 10m resolution using Sentinel-2
- **GEE**: `GOOGLE/DYNAMICWORLD/V1`
- **Classes**: 9 classes including "trees" — but does NOT distinguish plantation from natural forest
- **Temporal**: 2015-present, with new predictions every 5 days

### Can It Distinguish Plantation from Natural Forest?
**Not directly.** The 1m canopy height data shows WHERE trees are and HOW TALL they are, but not:
- Whether they are plantation or natural
- What species they are
- How old they are
- Whether they were planted or naturally regenerated

However, **structural patterns in the 1m data CAN indicate plantations**:
- Plantations have uniform canopy height (all trees the same age)
- Plantations often have visible row spacing at 1m resolution
- Plantations have sharp boundaries with adjacent land uses
- Natural forests have heterogeneous canopy height (multi-aged structure)

A CNN trained on 1m canopy height texture could potentially classify plantation vs natural forest based on these structural patterns.

### WRI Tree Species Work
WRI has NOT published a global tree species dataset. Their focus has been on:
- Tree cover extent (where trees are)
- Canopy height (how tall trees are)
- Tree cover change (gain/loss)
- Carbon stocks (how much carbon)

**This is where Treekipedia goes fundamentally beyond WRI**: Treekipedia answers "WHAT species of tree" not just "IS there a tree" — see Section 14 for detailed comparison.

---

## 10. The Canopy Height Paper (Tolan et al. 2024)

### Paper Details
- **Title**: "Very high resolution canopy height maps from RGB imagery using self-supervised vision transformer and convolutional decoder trained on Aerial Lidar"
- **Journal**: Remote Sensing of Environment, Volume 300, 2024, 113888
- **DOI**: https://doi.org/10.1016/j.rse.2023.113888
- **Authors**: Jamie Tolan, Hung-I Yang, Benjamin Nosarzewski, Guillaume Couairon, Huy V. Vo, John Brandt, Justine Spore, et al. (Meta AI Research + WRI)

### Key Methods
1. **Foundation model approach**: Used DINOv2 ViT-Huge backbone, pre-trained on 18M satellite images via self-supervised learning
2. **Depth estimation adaptation**: Treated canopy height prediction as analogous to monocular depth estimation (the "distance" from satellite to ground minus distance to canopy top = tree height)
3. **Training data**: NEON (National Ecological Observatory Network) airborne LIDAR data from the US as ground truth
4. **Transfer learning**: Model trained on US LIDAR data generalizes to global forests
5. **Scale**: Generated predictions for ~580,000 image tiles covering all global land area — 100 trillion pixels total

### Key Findings
1. Trees >1m tall cover >50 million km² (more than 1/3 of land)
2. Trees >5m tall cover 35 million km²
3. Self-supervised pre-training on satellite imagery dramatically improves generalization compared to ImageNet pre-training
4. The model generalizes well across continents despite being trained only on US LIDAR data
5. Performance: MAE of 3.08m for the compressed model on aerial imagery test sets

### Relevance to Plantation Detection
1. **Structural information**: The 1m canopy height data reveals stand structure. Plantations have uniform height, natural forests have height variation. Computing height standard deviation in a local window would be a direct plantation indicator.

2. **The DINO backbone learns forest-relevant features**: The SSL pre-training on satellite imagery teaches the model visual patterns of forests. These features could be repurposed for forest type classification.

3. **Foundation model pipeline**: The paper demonstrates that SSL pre-training → fine-tuning on a specific task is a viable approach for global-scale forest analysis. We could apply the same pipeline to plantation classification.

### Limitations
- Single-epoch (no temporal change detection)
- Some artifacts: 150x150m square artifacts, edge effects between image tiles, cloud cover gaps
- Canopy height ≠ species identification
- Ground truth only from US NEON data — bias toward US forest types

---

## 11. Foundation Model Comparison Matrix

### For Plantation vs Natural Forest Classification

| Criterion | Clay v1.5 | Prithvi-EO-2.0 | DINOv2 | AlphaEarth |
|-----------|-----------|----------------|--------|------------|
| **Pre-2000 detection** | ❌ (S2 from 2015) | ✅ (HLS/Landsat from 1984) | ❌ | ❌ |
| **Multi-temporal** | ✅ | ✅ (3D architecture) | ❌ | ❌ |
| **SAR for structure** | ✅ (S1) | ❌ | ❌ | ❌ |
| **NZ training data** | ✅ (LINZ) | ❌ | ❌ | Unknown |
| **Forest-specific fine-tuning** | ✅ (Biomasters) | ✅ (carbon flux) | ✅ (canopy height) | N/A |
| **GEE integration** | ❌ | ❌ | ❌ | ✅ |
| **Open source** | ✅ | ✅ | ✅ | ❌ |
| **Implementation ease** | Medium | Medium-High | Low-Medium | Low (API) |
| **Embedding richness** | 1024-D | Varies | 384-1536-D | 64-D |
| **Best signal for plantation** | SAR texture + spectral | Temporal trajectory | Structural texture | Env. niche |

### Recommended Stack for Treekipedia
**Tier 1 (Immediate, GEE-native)**:
1. GLAD Forest Height Change (2000 vs 2020) — direct plantation age signal
2. CCDC break dates — pre-2000 land use history
3. AlphaEarth 64-D embeddings (already integrated)

**Tier 2 (Near-term, external compute)**:
4. Clay embeddings — multi-sensor fusion including SAR structural information
5. Prithvi-EO temporal analysis — Landsat time series for historical change detection

**Tier 3 (Research/future)**:
6. DINOv2 on high-res imagery — structural texture analysis at 1m
7. Custom plantation classifier trained on TorchGeo framework

---

## 12. Dual/Multi-Embedding Strategy for Treekipedia

### Current State
Treekipedia currently uses:
- **AlphaEarth 64-D embeddings**: Capture environmental niche (climate, terrain, soil combined with satellite spectral signature)
- **61 explicit environmental variables**: From GEE pipeline (WorldClim, SoilGrids, SRTM, etc.)
- **11.4M labeled tree occurrences**: Ground truth from GBIF

### Proposed Multi-Embedding Architecture

```
Location (lat, lon) → 
  ├── AlphaEarth 64-D: Environmental niche embedding
  ├── Clay 1024-D: Multi-sensor structural/spectral embedding
  ├── CCDC features 12-D: Historical land use trajectory
  ├── GLAD height change 3-D: Growth rate signal
  └── Hansen 3-D: Tree cover, loss, gain
      ↓
  Fusion MLP/Transformer → 128-D combined embedding
      ↓
  Species Prediction (K-NN or classifier)
```

### Why This Works
Each embedding captures a different aspect of the forest:
- **AlphaEarth**: "What kind of environment is this?" (climate envelope, soil, terrain)
- **Clay**: "What does this forest look/feel like?" (spectral signature, SAR texture, multi-temporal phenology)
- **CCDC**: "What happened here before?" (land use history, change dates)
- **GLAD height**: "How fast is this forest growing?" (age/growth stage proxy)
- **Hansen**: "How much canopy is there?" (baseline density)

For our NZ plantation test case, this multi-embedding approach would produce:
- AlphaEarth: "This environment could support either Pinus radiata plantation or native podocarp forest"
- Clay: "SAR texture shows uniform monoculture structure, consistent with plantation"
- CCDC: "Land was grassland until 1997, then converted to forest — this is a planted forest"
- GLAD height: "Height gained 25m in 20 years — growth rate consistent with Pinus radiata plantation"
- Hansen: "90% canopy cover — this is dense forest"

Combined, the system would correctly identify this as a Pinus radiata plantation with high confidence.

---

## 13. What Could Be Built on Treekipedia's Data

Treekipedia's unique assets:
- **11.4M labeled tree occurrences** across 44K species (from GBIF)
- **64-D AlphaEarth embeddings** for each occurrence
- **61 environmental variables** for each occurrence
- **Botanical research data** across 35 fields for researched species
- **Species knowledge graph** connecting species to environments

### Cutting-Edge Applications

#### 1. Global Species Distribution Modeling at Scale
**What**: Train deep learning SDMs (species distribution models) for all 44K tree species simultaneously using the multi-task learning paradigm.

**Why it's cutting-edge**: Traditional SDMs (MaxEnt, etc.) model one species at a time. A multi-task deep learning SDM would learn shared environmental representations across species, dramatically improving predictions for rare species (which have few observations) by transferring knowledge from common species in similar niches.

**Architecture**: 
```
Environmental features (61 vars + 64-D AlphaEarth) →
  Shared encoder (learn cross-species env representations) →
  Species-specific heads (44K outputs, multi-label) →
  Species suitability scores per location
```

**Reference**: The GeoLifeCLEF competition (2023-2025) explores exactly this approach, and deep learning models have been winning.

#### 2. Forest Carbon Verification System
**What**: A system that uses Treekipedia's species-level data combined with biomass allometry to verify carbon credits.

**How**:
1. For any forest location, predict which species are present (Treekipedia's species predictor)
2. For each predicted species, look up species-specific allometric equations (wood density, growth rates, carbon content)
3. Combine with GLAD canopy height / GEDI biomass to estimate total carbon stock
4. Compare predicted carbon stock against claimed carbon credits
5. Flag discrepancies: e.g., "This carbon credit claims old-growth native forest carbon sequestration, but our species prediction indicates this is a young Pinus radiata plantation with much lower per-hectare carbon stock"

**Why it's valuable**: Carbon credit fraud is a major problem. Species-specific carbon estimation is much more accurate than generic "forest = X tonnes CO2/ha" assumptions.

#### 3. Climate-Adapted Species Selection Engine
**What**: For any planting location, recommend species that will thrive not just under current conditions but under future climate projections (2050, 2070, 2100).

**How**:
1. Use current environmental conditions to find species that grow there now
2. Use CMIP6 climate projections to determine future conditions at the location
3. Find species whose current niche matches the FUTURE conditions of the planting location
4. Rank by climate adaptation potential, growth rate, carbon sequestration, biodiversity value

**Why it's cutting-edge**: Most reforestation projects select species based on current conditions. Treekipedia could recommend "plant X species now, because in 30 years the climate at this location will match where X naturally grows today."

#### 4. Biodiversity Credit Market Infrastructure
**What**: Provide the species-level data needed to price and verify biodiversity credits.

**How**:
1. For any restoration project, predict expected species composition (Treekipedia predictor)
2. Compare predicted composition to the actual baseline (what was there before)
3. Calculate a biodiversity gain score: species richness, functional diversity, phylogenetic diversity
4. Price credits based on marginal biodiversity gain
5. Monitor over time: Are the predicted species actually establishing?

**Why it's cutting-edge**: Biodiversity credit markets are emerging (e.g., Australia's biodiversity market, EU Nature Restoration Law). They need quantitative, verifiable species-level data — exactly what Treekipedia provides.

#### 5. Reforestation Planning Optimization
**What**: Given a degraded landscape and restoration goals (carbon maximization, biodiversity, timber production, watershed protection), optimize the species planting plan.

**How**:
1. Use Treekipedia's species predictor to identify all viable species for the location
2. For each species, query botanical research data: growth rate, wood density, carbon content, nitrogen fixation, shade tolerance, drought tolerance, etc.
3. Apply optimization algorithm (e.g., mixed-integer programming or RL) to select species mix that maximizes the objective function while satisfying constraints (budget, nursery availability, planting density)
4. Output: Georeferenced planting plan with species, density, and spacing recommendations

#### 6. Invasive Species Early Warning
**What**: Use Treekipedia's occurrence data to detect range expansion of invasive tree species before they become established.

**How**:
1. For known invasive tree species, model their current realized niche (where they are now)
2. Model their potential niche (where conditions are suitable but they haven't been recorded)
3. Identify the "invasion front" — locations where conditions are suitable AND the species is present nearby but not yet recorded
4. Alert land managers in these zones

#### 7. Functional Trait Mapping
**What**: Use Treekipedia's species predictions to map functional traits across the landscape.

**How**:
1. For any location, predict species composition
2. For each species, look up functional traits (specific leaf area, wood density, N-fixation, mycorrhizal type, seed size, drought tolerance, etc.)
3. Compute community-weighted mean traits for the location
4. Map functional diversity globally at unprecedented species-resolved detail

#### 8. Phylogenetic Diversity Mapping
**What**: Map the evolutionary diversity of forest communities globally.

**How**: 
1. Predict species composition per location
2. Place species on a phylogenetic tree (available from Open Tree of Life)
3. Compute PD (phylogenetic diversity), NRI (net relatedness index), NTI (nearest taxon index) per location
4. Identify evolutionary hotspots and coldspots

---

## 14. WRI Comparison & Going Beyond

### What WRI Has Done
WRI's forest data portfolio includes:
1. **Global Forest Watch**: Tree cover, loss, gain from Hansen GFC (30m)
2. **Dynamic World**: Near-real-time land cover at 10m
3. **1m Canopy Height**: From Meta partnership (DINOv2-based)
4. **Tropical Tree Cover**: 10m tree detection outside forests
5. **Land Carbon Lab datasets**: Carbon stocks, emissions
6. **TerraFund**: Restoration project monitoring

### What WRI Does NOT Do
- **Species identification**: WRI tells you WHERE trees are, not WHAT species
- **Forest type classification**: WRI does not distinguish plantation from natural forest (though this is an active area of work)
- **Species-specific carbon accounting**: WRI uses generic forest-type carbon factors, not species-specific allometry
- **Future species suitability**: WRI does not project which species will be viable under climate change
- **Biodiversity assessment**: WRI does not compute species richness, functional diversity, or phylogenetic diversity at species resolution

### How Treekipedia Goes Beyond WRI

| Capability | WRI | Treekipedia |
|-----------|-----|-------------|
| Tree presence detection | ✅ (10m-1m) | ✅ (via occurrence data) |
| Tree height | ✅ (1m) | ✅ (via GLAD/Meta data) |
| Forest loss/gain | ✅ | ✅ (via Hansen + CCDC) |
| **Species identification** | ❌ | ✅ (44K species) |
| **Plantation vs natural** | ❌ | ✅ (proposed, via multi-embedding) |
| **Species-specific carbon** | ❌ | ✅ (proposed, via allometry) |
| **Future species suitability** | ❌ | ✅ (proposed, via CMIP6) |
| **Biodiversity metrics** | ❌ | ✅ (proposed, via phylogeny) |
| **Species-specific growth rates** | ❌ | ✅ (proposed, via research data) |
| **Functional trait mapping** | ❌ | ✅ (proposed, via trait databases) |

### The Key Differentiator
**WRI answers: "Is there a forest?" and "How tall is it?"**
**Treekipedia answers: "What species are in this forest, are they natural or planted, how fast are they growing, and what should be planted here next?"**

This is a fundamentally different (and much richer) layer of intelligence.

---

## 15. Novel Applications

### 1. Forest Carbon Verification at Species Resolution
**Problem**: Current carbon credit methodologies use generic emission factors (e.g., "tropical forest = 200 t C/ha"). This leads to significant over- or under-estimation.

**Treekipedia solution**: 
- Predict species composition at the credit site
- Use species-specific wood density, allometric equations, and growth curves
- Produce more accurate carbon estimates
- Flag sites where claimed species don't match predicted species (fraud detection)

**Market**: Voluntary carbon market is ~$2B/year and growing. Verification is the key bottleneck.

### 2. Biodiversity Credit Markets
**Problem**: Emerging biodiversity credit markets (Australia, UK, EU) need quantitative, verifiable biodiversity metrics.

**Treekipedia solution**:
- Species richness prediction for any location
- Change in species richness from baseline to current
- Functional and phylogenetic diversity computation
- Independent monitoring of restoration project biodiversity outcomes

### 3. Reforestation Planning Optimization
**Problem**: Most reforestation projects plant 1-3 species chosen by local knowledge, missing opportunities for higher carbon sequestration, biodiversity, or resilience.

**Treekipedia solution**:
- Input: location, goals (carbon/biodiversity/timber/watershed), constraints (budget, nursery stock)
- Output: Optimized species mix with planting density and spacing
- Climate-future-aware: selects species that will thrive under 2050-2100 conditions

### 4. Forest Health Monitoring at Species Resolution
**Problem**: Forest pest and disease monitoring currently relies on field surveys or generic satellite anomaly detection.

**Treekipedia solution**:
- Know which species are present (Treekipedia prediction)
- Know which pests/diseases affect those species (botanical research data)
- Monitor for spectral anomalies consistent with species-specific diseases
- Alert: "NDVI decline at this location is consistent with Dothistroma needle blight in Pinus radiata"

### 5. Supply Chain Deforestation Verification
**Problem**: EUDR (EU Deforestation Regulation) requires companies to prove that commodities were not produced on recently deforested land.

**Treekipedia solution**:
- For any GPS coordinate, determine if the location was forest or plantation before a cutoff date
- Identify which species were present (if it was a plantation, what was planted?)
- Verify whether the current land use is consistent with legal requirements

---

## 16. Additional Foundation Models & Papers (2023-2025)

### Foundation Models

#### 1. SatMAE (2023)
- **What**: Masked autoencoder pre-trained on satellite imagery (temporal and spectral)
- **Key innovation**: Temporal and spectral positional encodings for multi-temporal satellite data
- **Relevance**: Similar approach to Clay/Prithvi but earlier
- **Paper**: "SatMAE: Pre-training Transformers for Temporal and Multi-Spectral Satellite Imagery"

#### 2. ScaleMAE (2023)
- **What**: MAE that handles multi-scale satellite imagery by encoding GSD
- **Relevance**: Scale-aware representations useful for cross-resolution analysis
- **From**: Berkeley

#### 3. GFM (Towards Geospatial Foundation Models, 2023)
- **What**: Multi-objective contrastive pre-training for EO
- **Paper**: "Towards Geospatial Foundation Models via Continual Pretraining"

#### 4. DOFA (2024)
- **What**: Dynamic One-For-All model for multi-sensor EO
- **Key innovation**: Dynamic convolutions that adapt to input sensor specifications
- **From**: TU Munich
- **Relevance**: Like Clay, handles arbitrary sensors/bands

#### 5. Spectral-GPT (2023)
- **What**: Spectral foundation model for remote sensing imagery
- **Key innovation**: Explicitly models spectral dependencies
- **Relevance**: Better spectral understanding could help distinguish conifer plantation from broadleaf forest

#### 6. IBM Granite Geospatial Models
- **What**: Enterprise versions of Prithvi, fine-tuned for commercial applications
- **From**: IBM
- **HuggingFace**: `ibm-granite/granite-geospatial-*`
- **Relevance**: Production-ready alternatives to Prithvi for commercial deployment

#### 7. Segment Anything Model 2 (SAM2) for Remote Sensing
- **What**: Meta's SAM2 adapted for geospatial segmentation
- **Relevance**: Could segment individual tree crowns or plantation boundaries in high-res imagery

#### 8. DINOv3 (2025)
- **What**: Next generation of DINOv2, released August 2025
- **Improvement**: More consistent features, better transfer learning
- **Relevance**: If using DINOv2-based approaches, DINOv3 would be the updated backbone

### Key Papers

#### 1. "Remote sensing of forest degradation: a review" (2024)
- Reviews all methods for detecting forest degradation (more subtle than deforestation)
- Key finding: Temporal trajectory analysis (LandTrendr/CCDC) is the most reliable method for detecting historical degradation

#### 2. "Global Plantation Forests: Current Status and Projected Changes" (Payn et al., 2023)
- Updates on global plantation forest area: ~131M ha globally
- Key finding: Plantations are concentrated in China, US, Russia, Brazil — and NZ ranks surprisingly high per-capita

#### 3. "Machine learning for global forest monitoring" (Nature Reviews Earth & Environment, 2024)
- Reviews ML approaches for forest monitoring
- Key finding: Foundation models are becoming the dominant paradigm, replacing task-specific models
- Recommends multi-sensor fusion (optical + SAR + LIDAR) for best results

#### 4. "Tree species classification using satellite imagery and deep learning" (various, 2023-2025)
- Multiple papers demonstrate species-level classification from Sentinel-2 and high-res imagery
- Best results: 70-85% accuracy for 10-30 species in temperate forests
- Key limitation: Accuracy drops rapidly for tropical forests with higher species diversity

### Key Datasets

#### 1. Global Forest Biodiversity Initiative (GFBI)
- **What**: 1.3M ground truth forest inventory plots globally
- **Variables**: Species composition, diameter, height, basal area
- **Access**: Restricted (research consortium)
- **Relevance**: Could be used to validate Treekipedia species predictions

#### 2. FOS (Forest Observation System)
- **What**: Ground truth forest monitoring plots in the tropics
- **Access**: Open
- **Relevance**: Tropical forest validation data

#### 3. sPlotOpen
- **What**: Open vegetation plot database with species composition
- **Size**: 95K plots globally
- **Access**: Open
- **Relevance**: Additional training/validation data for species prediction

#### 4. MapBiomas
- **What**: Annual land use and land cover maps for Brazil, Indonesia, and pan-tropics
- **Resolution**: 30m
- **Key feature**: Distinguishes "forest plantation" from "natural forest" — one of the few datasets that does this
- **Relevance**: Training data for plantation detection model

---

## 17. Implementation Roadmap

### Phase 1: Quick Wins (1-2 weeks)
**All GEE-native, no external compute needed**

1. **Add GLAD Forest Height Change variables to GEE pipeline**:
   - `forest_height_2000`: from `projects/glad/GLCLU2020/Forest_height_2000`
   - `forest_height_2020`: from `projects/glad/GLCLU2020/Forest_height_2020`
   - `forest_height_change`: computed as `height_2020 - height_2000`
   - `forest_type_dynamics`: from `projects/glad/GLCLU2020/Forest_type` (4 classes: stable, loss, gain, disturbed)

2. **Add CCDC break point variables**:
   - `ccdc_num_breaks`: Number of detected land cover changes
   - `ccdc_last_break_year`: Year of most recent change
   - `ccdc_years_since_break`: Time since last change

3. **Add Dynamic World forest class**:
   - `dynamic_world_trees_prob`: Probability of "trees" class from `GOOGLE/DYNAMICWORLD/V1`

### Phase 2: Enhanced Discrimination (1-2 months)
**GEE-native with some external processing**

4. **CCDC harmonic coefficient extraction** for forest type classification
5. **LandTrendr analysis** for pre-2000 disturbance detection
6. **SAR-based texture metrics** from Sentinel-1 for monoculture detection:
   - `sar_vv_variance`: Local variance of VV backscatter (low = uniform plantation)
   - `sar_texture_homogeneity`: GLCM homogeneity (high = plantation)

### Phase 3: Foundation Model Integration (2-4 months)
**Requires external GPU compute**

7. **Clay embedding computation** for training/validation locations
8. **Prithvi temporal analysis** for historical change detection
9. **Multi-embedding fusion model** training:
   - Input: AlphaEarth 64-D + Clay 1024-D + CCDC features + GLAD heights
   - Output: Improved species predictions with plantation/natural forest discrimination

### Phase 4: Cutting-Edge Applications (6-12 months)

10. **Carbon verification engine** using species-specific allometry
11. **Climate-adapted species recommendation** using CMIP6 projections
12. **Biodiversity credit assessment** using predicted species composition
13. **Global plantation vs natural forest classification** using trained multi-embedding model

---

## 18. Conclusions & Recommendations

### The Plantation Detection Problem Is Solvable
The pre-Hansen plantation detection problem has multiple viable solutions:
1. **CCDC pre-computed data** (GEE-native) can detect the land clearing and planting event in the 1990s
2. **GLAD forest height change** (GEE-native) can distinguish fast-growing plantations from slow-growing natural forests
3. **SAR texture** (GEE-native) can detect uniform monoculture structure
4. **Foundation model embeddings** (Clay, Prithvi) can capture multi-sensor, multi-temporal signatures

### The Most Cost-Effective Approach
Start with **GEE-native data** (GLAD + CCDC + SAR texture) before investing in foundation model compute. These provide strong plantation discrimination signals at zero additional infrastructure cost.

### The Most Powerful Approach
A **multi-embedding architecture** combining AlphaEarth (environmental niche) + Clay (structural/spectral) + CCDC (historical trajectory) + GLAD height change (growth rate) would be the most comprehensive approach, but requires more infrastructure investment.

### Treekipedia's Strategic Position
Treekipedia occupies a unique position in the ecosystem:
- **WRI/GFW**: WHERE are forests? → Already answered
- **Meta/WRI**: HOW TALL are forests? → Already answered
- **Hansen**: IS forest changing? → Already answered (post-2000)
- **Treekipedia**: WHAT SPECIES are in this forest, and IS IT NATURAL OR PLANTED? → Uniquely positioned to answer

The combination of 11.4M labeled occurrences + 44K species + 64-D embeddings + 61 environmental variables is unmatched. Adding plantation detection capability and carbon verification would make Treekipedia the definitive tool for species-resolved forest intelligence.

### Top 3 Immediate Actions
1. **Add GLAD Forest Height Change to GEE pipeline** — direct plantation age signal, zero ML needed
2. **Add CCDC break dates to GEE pipeline** — pre-2000 land use history, pre-computed in GEE
3. **Prototype Clay embeddings** for a sample of NZ locations with known plantation/natural status — evaluate whether the dual-embedding approach (AlphaEarth + Clay) improves plantation discrimination

---

*Report prepared February 18, 2026. Sources include primary documentation from Clay Foundation, NASA/IBM Prithvi, Meta DINOv2, WRI Land Carbon Lab, GLAD Lab (UMD), and multiple research papers from 2023-2025.*
