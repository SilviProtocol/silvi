# Future Work: Above-Ground Biomass & Carbon Prediction Models

**Date:** February 18, 2026  
**Status:** Research saved for future implementation  
**Related:** [RESEARCH_PLANTATION_DETECTION_FOUNDATION_MODELS.md](./RESEARCH_PLANTATION_DETECTION_FOUNDATION_MODELS.md) (full research report)

---

## Purpose

This document preserves research findings on tools and models that are NOT being used in the current prediction system but will be valuable for future Treekipedia features:
- Above-ground biomass (AGB) estimation
- Carbon stock prediction
- Carbon sequestration rate modeling
- Growth rate estimation

---

## Key Tools & Models for Future AGB/Carbon Work

### 1. TorchGeo (Microsoft)

**What it is:** PyTorch library for geospatial deep learning. Provides pre-trained models, dataset loaders, and transforms for satellite imagery.

**Why it matters for AGB/Carbon:**
- Pre-built dataset loaders for common remote sensing datasets (Sentinel, Landsat, etc.)
- Integration with PyTorch Lightning for training custom models
- Built-in support for multispectral imagery → biomass regression
- Raster sampling tools for creating training datasets from image patches

**Why NOT used now:** Treekipedia's current architecture uses point-based embeddings (AlphaEarth 64-D per pixel), not image patches. TorchGeo expects image tiles, not pre-computed embeddings. Useful when we move to image-based models.

**Key resources:**
- GitHub: https://github.com/microsoft/torchgeo
- Docs: https://torchgeo.readthedocs.io/
- Relevant datasets: EnviroAtlas, TreeSatAI, So2Sat

### 2. DINOv2 (Meta)

**What it is:** Self-supervised Vision Transformer pre-trained on 142M images. Produces 1024-D embeddings that encode rich visual features without task-specific training.

**Why it matters for AGB/Carbon:**
- Meta's 1m canopy height model (Tolan et al., 2024) was built using DINOv2 internally
- DINOv2 embeddings from Sentinel-2 patches could serve as features for biomass regression
- Captures texture/structure information that correlates with forest density and biomass
- Can detect canopy gaps, crown structure, and forest degradation patterns

**Why NOT used now:** The Meta canopy height product already uses DINOv2 internally — we consume the product (ETH/Meta canopy height), not the raw model. Direct use of DINOv2 would require image patch infrastructure we don't have yet.

**Key resources:**
- Paper: Oquab et al. (2023) "DINOv2: Learning Robust Visual Features without Supervision"
- GitHub: https://github.com/facebookresearch/dinov2
- Canopy height paper: Tolan et al. (2024) "Very high resolution canopy height maps from RGB imagery using self-supervised vision transformer and convolutional decoder trained on Aerial Lidar"

### 3. Clay Foundation Model (Made With Clay)

**What it is:** Open-source geospatial AI model trained on Sentinel-1 (SAR) + Sentinel-2 (optical) + DEM. Produces 1024-D patch embeddings.

**Why it matters for AGB/Carbon:**
- Trained on multispectral + SAR data → captures vegetation structure beyond optical
- SAR penetrates cloud cover and responds to biomass/woody structure
- Could provide complementary embeddings to AlphaEarth for biomass prediction
- Potential dual-embedding approach: AlphaEarth (64-D) for species + Clay (1024-D) for biomass

**Potential architecture:**
```
Query pixel → AlphaEarth embedding → species k-NN prediction
           → Clay embedding → biomass regression model
           → Combined → species + biomass + carbon estimate
```

**Why NOT used now:** Requires significant infrastructure (Sentinel tile download, model inference, embedding storage). Current focus is on species prediction accuracy.

**Key resources:**
- GitHub: https://github.com/Clay-foundation/model
- HuggingFace: https://huggingface.co/made-with-clay/Clay
- Resolution: 10m (Sentinel-2 native)

### 4. Prithvi (NASA/IBM)

**What it is:** NASA-IBM geospatial foundation model (100M params) trained on Harmonized Landsat Sentinel-2 (HLS) data.

**Why it matters for AGB/Carbon:**
- Pre-trained on massive HLS dataset covering all biomes
- Fine-tunable for biomass estimation, burn scar mapping, flood detection
- NASA backing means long-term support and scientific rigor
- Temporal bands (6 HLS bands × multiple timesteps) capture phenology relevant to growth rate estimation

**Key resources:**
- HuggingFace: https://huggingface.co/ibm-nasa-geospatial/Prithvi-100M
- Paper: Jakubik et al. (2023) "Foundation Models for Generalist Geospatial Artificial Intelligence"

---

## Relevant GEE Datasets for AGB/Carbon

### Currently Available (already in our pipeline)
| Dataset | Resolution | Use for AGB/Carbon |
|---------|------------|---------------------|
| ETH Canopy Height 2020 | 10m | Height → allometric biomass estimation |
| Meta 1m Canopy Height | 1m | Fine-grained height; crown delineation |
| Hansen treecover2000 | 30m | Canopy density → biomass proxy |
| SRTM elevation | 30m | Elevation-adjusted allometry |
| WorldClim BIO | 1km | Climate envelope → growth rate bounds |

### To Add in Future
| Dataset | Resolution | Use for AGB/Carbon |
|---------|------------|---------------------|
| **GEDI L4A** | 25m footprint | Direct AGB estimates from lidar waveforms |
| **GLAD Forest Height** | 30m | Multi-temporal height → growth rate |
| **GlobBiomass** (CCI) | 100m | Pre-computed AGB maps (2017) |
| **ESA CCI Biomass** | 100m | Annual AGB maps, global |
| **ALOS PALSAR** | 25m | L-band SAR → woody biomass (penetrates canopy) |
| **ICESat-2 ATL08** | Variable | Canopy height profiles from laser altimetry |

---

## Allometric Approach (Near-Term, No ML Required)

Before building ML models, we can estimate AGB using standard allometric equations:

```
AGB = f(height, diameter, wood_density, species)
```

Where:
- **Height**: ETH canopy height (already sampled)
- **Diameter**: Estimated from height using species-specific H-D relationships
- **Wood density**: Available in species table (`wood_density_ai`/`wood_density_human`)
- **Species**: Known from prediction output

This gives a first-order AGB estimate per pixel without any model training.

**Key allometric databases:**
- GlobAllomeTree (FAO): https://globallometree.org/
- BIOMASS (Chave et al. 2014): Pantropical equations
- ForestGEO: Plot-based allometry data

---

## Carbon Estimation Pipeline (Future Architecture)

```
Stage 1: Species Prediction (CURRENT)
  - AlphaEarth embedding → k-NN → top species
  - Environmental context → scoring

Stage 2: Biomass Estimation (NEAR-TERM)
  - Canopy height (ETH/Meta) → allometric AGB per species
  - Wood density from species table
  - Crown area estimation from canopy height variance

Stage 3: Carbon Stock (NEAR-TERM)
  - AGB × 0.47 (standard carbon fraction)
  - Root biomass ≈ AGB × root:shoot ratio (species-specific)
  - Soil organic carbon from OpenLandMap

Stage 4: Carbon Dynamics (FUTURE)
  - Growth rate from height change (multi-temporal canopy maps)
  - Disturbance from CCDC/Hansen → carbon loss events
  - Recovery curves from time series → carbon accumulation rate
  - Clay/Prithvi embeddings → ML-based carbon flux prediction
```

---

## Notes on Temporal Validity

**Critical principle (from user):** Height and biomass data should only be used with older occurrences when we can confirm no disturbance between the occurrence year and the measurement year. Signals for this:
- Hansen loss/gain = 0 between years
- CCDC num_breaks = 0 between years  
- Canopy height unchanged (requires multi-temporal height data)
- ESA land cover class stable

For current (2020+) occurrences matched with 2020 canopy height, this is less of a concern. For older occurrences (pre-2017), temporal validation is essential.
