# SINR v3 Carbon/Biomass Research — Comprehensive Reference

**Date:** February 25, 2026
**Status:** Complete — findings from 5 parallel research agents
**Context:** Multi-task model extension: species prediction (43,500 species) + carbon/biomass regression

> **Related detailed documents:**
> - `research/carbon_biomass_gee_datasets.md` — GEE dataset specifications (925 lines)
> - `docs/carbon-mrv-landscape-research.md` — MRV market analysis (1015 lines)
> - Earlier: `RESEARCH_PLANTATION_DETECTION_FOUNDATION_MODELS.md` — Foundation models & plantation detection (1123 lines)
> - Earlier: `RESEARCH_AGB_CARBON_MODELS.md` — Initial AGB/carbon overview (175 lines)

---

## TABLE OF CONTENTS

1. [Executive Summary](#1-executive-summary)
2. [GEE Carbon/Biomass Datasets](#2-gee-carbonbiomass-datasets)
3. [External Satellite Datasets (NOT in GEE)](#3-external-satellite-datasets-not-in-gee)
4. [LiDAR Datasets for AGB Calibration](#4-lidar-datasets-for-agb-calibration)
5. [Temporal Alignment Framework](#5-temporal-alignment-framework)
6. [Multi-Task Architecture Design](#6-multi-task-architecture-design)
7. [Carbon MRV Market & Competitive Landscape](#7-carbon-mrv-market--competitive-landscape)
8. [Allometric Databases](#8-allometric-databases)
9. [Implementation Priorities](#9-implementation-priorities)
10. [Key Citations](#10-key-citations)

---

## 1. Executive Summary

### The Opportunity
SINR v3 would be the **only global tool combining species prediction (43,500 species) with carbon/biomass estimation**. No competitor — not Pachama, NCX, CTrees, Chloris, or Sylvera — uses species information for carbon estimation. This is the single biggest source of error in remote-sensing carbon estimation: using the wrong allometric equation because you don't know the species introduces 20-50% error (Chave et al., 2004).

### Key Findings

1. **17 GEE datasets** identified for carbon features, adding ~25-30 new features per training point
2. **ESA CCI Biomass v6.0** is the most important external dataset: 100m, annual 2015-2022, temporally alignable with observations
3. **ESA BIOMASS satellite** launched April 2025, P-band SAR, L2 AGB products expected ~2027 — will be transformative
4. **NISAR** launched July 2025, L+S band SAR, 3-10m, 12-day repeat — free and open
5. **GEDI L4A** (25m footprints) is the best AGB training label; **GEDI GriddedVeg** (1km) is the best wall-to-wall coverage
6. **Multi-task shared backbone + separate heads** is the correct architecture — literature strongly supports it
7. **Species-aware carbon estimation** reduces AGB error by 15-25% (Chen et al., 2023)
8. **VM0047 v1.1** (May 2025) now allows remote sensing for baseline biomass — regulatory path is opening
9. **Bug found**: GEDI GriddedVeg `.mosaic()` in our code mixes different metrics — needs fixing
10. **Temporal alignment** is critical: must screen for disturbance between observation year and carbon data year

### The Value Chain
```
Species prediction → Species-specific wood density → Correct allometric equation →
Better AGB estimate → Better carbon credit verification → Higher-integrity credits (2-5x price premium)
```

---

## 2. GEE Carbon/Biomass Datasets

> **Full specifications in**: `research/carbon_biomass_gee_datasets.md`

### 2.1 Biomass/Carbon Stocks

| Dataset | GEE Asset ID | Res | Temporal | Type | Key Bands | Temporally Alignable? |
|---------|-------------|-----|----------|------|-----------|----------------------|
| **Spawn AGB/BGB** | `NASA/ORNL/biomass_carbon_density/v1` | 300m | 2010 only | ImageColl | `agb`, `agb_uncertainty`, `bgb`, `bgb_uncertainty` (Mg C/ha) | NO — single epoch |
| **GEDI L4B** | `LARSE/GEDI/GEDI04_B_002` | 1km | 2019-2021 | Image | `MU` (AGBD Mg/ha), `SE`, `PE`, `QF` | NO — single composite |
| **GEDI L4A Monthly** | `LARSE/GEDI/GEDI04_A_002_MONTHLY` | 25m | 2019-2025 | ImageColl | `agbd`, `agbd_se`, `sensitivity` | YES (monthly composites) |
| **GEDI GriddedVeg** | `LARSE/GEDI/GRIDDEDVEG_002/V1/1KM` | 1km | 2019-2023 | ImageColl | RH98, FHD, AGBD, canopy cover (per-image) | NO — mission composite |

**GEDI GriddedVeg Bug (MUST FIX):** Our code does `.mosaic()` on the entire collection, but each image in the collection represents a DIFFERENT metric (rh98, fhd, agbd, etc.). Correct usage:
```python
rh98_img = ee.Image('LARSE/GEDI/GRIDDEDVEG_002/V1/1KM/gediv002_rh-98-a0_vf_20190417_20230316')
agbd_img = ee.Image('LARSE/GEDI/GRIDDEDVEG_002/V1/1KM/gediv002_agbd_vf_20190417_20230316')
fhd_img = ee.Image('LARSE/GEDI/GRIDDEDVEG_002/V1/1KM/gediv002_fhd-pai-1m-a0_vf_20190417_20230316')
```

### 2.2 Productivity/Flux

| Dataset | GEE Asset ID | Res | Temporal | Type | Key Bands | Temporally Alignable? |
|---------|-------------|-----|----------|------|-----------|----------------------|
| **MODIS Annual NPP** | `MODIS/061/MOD17A3HGF` | 500m | 2001-2024 | ImageColl | `Npp` (kgC/m2, scale=0.0001), `Gpp` | **YES** — annual, match to obs year |
| **MODIS 8-day GPP** | `MODIS/061/MOD17A2HGF` | 500m | 2021-present | ImageColl | `Gpp`, `PsnNet` | **YES but only 2021+** in V6.1 |

**Critical: Use Annual NPP (MOD17A3HGF) not 8-day GPP for temporal matching.** The 8-day product V6.1 only starts in 2021, but the annual product goes back to 2001.

### 2.3 Vegetation Structure

| Dataset | GEE Asset ID | Res | Temporal | Type | Key Bands | Temporally Alignable? |
|---------|-------------|-----|----------|------|-----------|----------------------|
| **MODIS LAI/FPAR** | `MODIS/061/MOD15A2H` | 500m | 2000-present | ImageColl (8-day) | `Lai_500m` (scale=0.1), `Fpar_500m` (scale=0.01) | **YES** — match to obs year |
| **ETH Canopy Height** | `users/nlang/ETH_GlobalCanopyHeight_2020_10m_v1` | 10m | 2020 only | Image | `b1` (height meters) | NO — single epoch |
| **Meta/WRI 1m Canopy Height** | NOT in official GEE | 1m | ~2018-2020 | — | — | N/A |
| **GLAD Forest Height** | NOT in official GEE | 30m | 2000, 2020 | — | — | N/A |

### 2.4 Soil Carbon

| Dataset | GEE Asset ID | Res | Temporal | Type | Key Bands | Temporally Alignable? |
|---------|-------------|-----|----------|------|-----------|----------------------|
| **OpenLandMap SOC** | `OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02` | 250m | Static | Image | `b0`, `b10`, `b30`, `b60`, `b100`, `b200` (g/kg, divide by 5) | NO — static |

**SoilGrids is NOT in GEE.** OpenLandMap products are the GEE equivalent.

### 2.5 Land Cover / Forest Classification

| Dataset | GEE Asset ID | Res | Temporal | Type | Key Bands | Temporally Alignable? |
|---------|-------------|-----|----------|------|-----------|----------------------|
| **IPCC Forest Class** | `NASA/ORNL/global_forest_classification_2020/V1` | 30m | 2020 | ImageColl | `forest_class` (1=primary, 2=young secondary, 3=old secondary) | NO |
| **Hansen GFC** | `UMD/hansen/global_forest_change_2024_v1_12` | 30m | 2000-2024 | Image | `treecover2000`, `loss`, `gain`, `lossyear` | **YES** — lossyear enables temporal screening |
| **MODIS EVI** | `MODIS/061/MOD13A1` | 500m | 2000-present | ImageColl (16-day) | `EVI` (scale=0.0001), `NDVI` | **YES** — match to obs year |
| **Dynamic World** | `GOOGLE/DYNAMICWORLD/V1` | 10m | 2015-present | ImageColl | `trees` probability | **YES for 2015+** |

### 2.6 Additional GEE Assets Worth Adding

| Dataset | GEE Asset ID | Res | What It Adds |
|---------|-------------|-----|-------------|
| **GEDI L4B** | `LARSE/GEDI/GEDI04_B_002` | 1km | Wall-to-wall AGBD — missing from carbon sampler |
| **NEON CHM** | `projects/neon-prod-earthengine/assets/CHM/001` | 1m | 81 US sites, gold standard CHM |
| **ALOS PALSAR** | `JAXA/ALOS/PALSAR/YEARLY/SAR_EPOCH` | 25m | L-band SAR backscatter (biomass proxy), 2015-2021 |
| **ICESat/GLAS Canopy Height** | `NASA/JPL/global_forest_canopy_height_2005` | 1km | 2005 baseline canopy height |

---

## 3. External Satellite Datasets (NOT in GEE)

### 3.1 ESA BIOMASS Mission

| Property | Value |
|----------|-------|
| **Launch** | April 29, 2025 |
| **Status** | Fully commissioned January 2026. L1 data open. L2 AGB maps expected ~2027. |
| **Sensor** | P-band SAR (435 MHz, 69 cm wavelength) |
| **Why P-band matters** | Only SAR band that penetrates FULL forest canopy to the ground. C-band (Sentinel-1) bounces off top of canopy. L-band (ALOS) penetrates partially. P-band sees trunk and large branch structure = direct biomass measurement. |
| **Resolution** | ~200m (planned AGB products) |
| **AGB saturation** | ~300 Mg/ha (vs ~100 Mg/ha for L-band, ~50 Mg/ha for C-band) — transformative for tropics |
| **Coverage** | Global, but higher latitudes first (forests above 50N already acquired) |
| **Download** | ESA Open Access Hub / Copernicus Data Space |
| **Priority** | **Tier 2** — wait for L2 products (~2027), then highest priority external dataset |
| **Citation** | Le Toan et al. (2011); ESA SP-1324/1 |

### 3.2 NISAR (NASA-ISRO SAR)

| Property | Value |
|----------|-------|
| **Launch** | July 30, 2025 |
| **Status** | In commissioning phase. Science data expected mid-2026. |
| **Sensors** | L-band (24 cm, NASA) + S-band (10 cm, ISRO) |
| **Resolution** | 3-10m (highest resolution L-band SAR ever) |
| **Repeat cycle** | 12 days |
| **Biomass capability** | No dedicated AGB product, but L-band backscatter is strong biomass predictor (saturates ~100 Mg/ha) |
| **Data policy** | **Free and open** — all data freely available |
| **Download** | NASA ASF DAAC: https://asf.alaska.edu/ |
| **Priority** | **Tier 2** — highest resolution L-band SAR; integrate when science data available |

### 3.3 ESA CCI Biomass v6.0

| Property | Value |
|----------|-------|
| **Version** | v6.0 (released April 2025) |
| **Resolution** | 100m |
| **Temporal** | **10 epochs: 2007, 2010, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022** |
| **Method** | Multi-sensor fusion: Sentinel-1 C-band SAR + ALOS PALSAR-2 L-band + environmental data, calibrated with GEDI + field plots |
| **Accuracy** | RMSE ~30-60 Mg/ha depending on biome. Higher in tropics due to C-band saturation. |
| **Change products** | AGB change between consecutive years available |
| **Download** | CEDA: https://catalogue.ceda.ac.uk/uuid/95913ffb6467447ca72c4e9d8cf30501/ |
| **Format** | GeoTIFF + NetCDF |
| **License** | Free, open access |
| **GEE** | NOT in GEE — must upload as asset or extract offline |
| **Priority** | **Tier 1 — MUST HAVE.** Best temporal AGB coverage matching our observation years (2015-2022). |
| **Citation** | Santoro, M. et al. (2021). The global forest above-ground biomass pool for 2010 estimated from high-resolution satellite observations. Earth System Science Data. |

### 3.4 ALOS PALSAR Mosaic (L-band SAR)

| Property | Value |
|----------|-------|
| **GEE Asset** | `JAXA/ALOS/PALSAR/YEARLY/SAR_EPOCH` |
| **Resolution** | 25m |
| **Temporal** | Annual mosaics 2015-2021 |
| **Bands** | HH, HV polarization (backscatter in dB) |
| **Biomass relevance** | L-band HV backscatter correlates with biomass (R² ~0.5-0.7) up to ~100 Mg/ha saturation |
| **Priority** | **Tier 1** — already in GEE, provides SAR structural signal complementary to optical |

### 3.5 Other External Datasets

| Dataset | Resolution | Year | Source | Priority |
|---------|-----------|------|--------|----------|
| ICESat-2 ATL08 canopy height | 100m segments | 2018+ | NSIDC DAAC | Tier 2 (fills boreal gap >51.6N) |
| GlobBiomass | 100m | 2010 | ESA | Tier 3 (superseded by CCI v6) |
| GFW/Harris carbon flux | 30m | 2001-2020 | WRI | Tier 2 (annual carbon flux maps) |
| Copernicus Global Land LAI | 300m | 1999+ | CGLS | Tier 3 (MODIS LAI is higher res) |

---

## 4. LiDAR Datasets for AGB Calibration

### 4.1 Hierarchy of AGB Training Labels

Ranked by quality and coverage:

```
1. GEDI L4A Footprints (25m, 2019-2025, 51.6N-51.6S)
   → Direct AGBD in Mg/ha with standard error
   → Sparse (along-track only) but highest accuracy
   → GEE: LARSE/GEDI/GEDI04_A_002_MONTHLY

2. GEDI GriddedVeg AGBD (1km, 2019-2023, 51.6N-51.6S)
   → Wall-to-wall gridded AGB with bootstrap SE
   → GEE: LARSE/GEDI/GRIDDEDVEG_002/V1/1KM (select specific metric images)

3. GEDI L4B (1km, 2019-2021, 51.6N-51.6S)
   → Wall-to-wall AGB with SE (older, less coverage than GriddedVeg)
   → GEE: LARSE/GEDI/GEDI04_B_002

4. ESA CCI Biomass v6.0 (100m, 2007-2022, global)
   → Multi-temporal AGB, temporally alignable
   → NOT in GEE — download from CEDA

5. Spawn et al. (300m, 2010, global)
   → Global AGB with uncertainty
   → GEE: NASA/ORNL/biomass_carbon_density/v1

6. ICESat-2 ATL08 + allometrics (100m segments, 2018+, global incl. poles)
   → Canopy height → AGB conversion needed
   → NOT in GEE — access via NSIDC
```

### 4.2 GEDI Coverage and Limitations

- **Orbital coverage:** 51.6N to 51.6S only (ISS orbital inclination)
- **Missing:** Most of Canada, Russia, Scandinavia, Alaska interior — major boreal gap
- **GEDI was reinstalled** on ISS in late 2023 after initial removal. Data collection continues through 2026+.
- **Quality filtering essential:** Use `quality_flag=1`, `degrade_flag=0`, `sensitivity>0.9`, `predictor_limit_flag=0`
- **Night passes preferred:** Higher signal-to-noise (`solar_elevation < 0`)

### 4.3 Airborne LiDAR for Validation

| Program | GEE Asset | Res | Coverage | Notes |
|---------|----------|-----|----------|-------|
| **NEON (US)** | `projects/neon-prod-earthengine/assets/CHM/001` | 1m | 81 US sites | Gold standard. Used to train Meta canopy height. Field data includes species ID + DBH. |
| **3DEP (US)** | `USGS/3DEP/10m` (bare earth only) | 0.5-2m raw | ~90% CONUS | Raw point clouds available from USGS. GEE has DEM only, not vegetation returns. |
| **UK Environment Agency** | NOT in GEE | 0.25-2m | All of England | CHM = DSM - DTM. Open data. |
| **Netherlands AHN** | NOT in GEE | 0.5m | Complete NL | 4 epochs: AHN1-AHN4 (1996-2022). Multi-temporal! |
| **NZ LINZ** | NOT in GEE | 1-2m | Partial | Includes plantation forests. |
| **OpenTopography** | NOT in GEE | Variable | Patchy global | REST API for on-demand processing. |

### 4.4 Drone/UAV LiDAR

- **Role:** Bridges field plots (20-50m) to satellite (25m-1km). Modern drones achieve 100-500 pts/m2.
- **No global repository exists.** Key sources: ForestGEO plots, AfriSAR/BIOSAR campaigns, individual published datasets on Zenodo/PANGAEA.
- **For our model:** Process drone LiDAR offline, compute plot-level AGB, load to BigQuery as validation points. Don't upload raw to GEE.

### 4.5 Best Practice: Sparse LiDAR → Wall-to-Wall Model

How researchers use sparse GEDI to train wall-to-wall AGB models:

1. **GEDI L4A footprints as direct labels** (most common): Sample millions of quality-filtered L4A AGBD footprints, pair with wall-to-wall predictors (Sentinel-2, SAR, climate), train Random Forest/XGBoost/DNN. This is EXACTLY what our carbon head does.

2. **Gridded GEDI as labels** (simpler, lower resolution): Use 1km L4B or GriddedVeg AGBD, weight by inverse SE.

3. **Uncertainty-weighted loss:**
```python
agb_loss = (pred_agb - target_agbd)^2 / (target_se^2 + epsilon)
```
Weight each AGB label by its confidence: GEDI L4A footprint (weight=1.0), GriddedVeg 1km (weight=0.7), Spawn 300m (weight=0.5), ICESat-2+allometry (weight=0.4).

---

## 5. Temporal Alignment Framework

### 5.1 The Core Problem

Our data has multiple temporal layers that MUST be aligned:

```
OBSERVATION (GBIF):     2000 ──────────────────────── 2024
ALPHA EARTH:                      2017 ─── 2024
MODIS NPP/GPP/LAI/EVI:  2000 ──────────────────────── 2024  ← CAN MATCH OBS YEAR
GEDI:                                    2019 ──── 2025
Spawn AGB:              2010 (single point)
ESA CCI Biomass:            2007 ─ 2010 ── 2015-2022        ← CAN MATCH RECENT OBS
ETH Canopy Height:                            2020
Hansen loss/gain:        2001 ──────────────────────── 2024  ← DISTURBANCE SCREENING
CCDC breaks:             1985 ──────────────────────── 2024  ← PRE-2000 HISTORY
```

### 5.2 Temporal Alignment Strategy

For each training point (lat, lon, observation_year):

**A. Temporally Matchable Features (sample at observation year):**
- MODIS NPP: Filter to observation year, take annual composite
- MODIS GPP: Filter to observation year, compute annual mean
- MODIS LAI/FPAR: Filter to observation year, compute growing season mean
- MODIS EVI: Filter to observation year, compute annual mean/max
- Dynamic World trees probability: Filter to observation year (2015+ only)
- ESA CCI Biomass: Use closest available year (2007, 2010, 2015-2022)

**B. Static/Snapshot Features (use as-is, accept temporal mismatch):**
- Spawn AGB/BGB (2010)
- OpenLandMap SOC (static)
- ETH Canopy Height (2020)
- GEDI GriddedVeg (2019-2023 composite)
- IPCC Forest Classification (2020)

**C. AlphaEarth Trajectory (multi-year):**
- Already have 8 years (2017-2024)
- Compute: mean, std, trend per dimension
- L-TAE temporal encoder captures dynamics

**D. Disturbance Screening (critical for AGB labels):**

Before using GEDI/Spawn/CCI AGB as a training label for an observation from a different year, check:

```sql
-- Example: observation from 2010, GEDI AGB from 2021
-- Screen for disturbance between 2010 and 2021
SELECT
  CASE
    WHEN hansen_lossyear BETWEEN 10 AND 21 THEN 'DISTURBED'  -- loss between 2010-2021
    WHEN modis_fire_year BETWEEN 2010 AND 2021 THEN 'BURNED'
    ELSE 'STABLE'
  END as temporal_stability
```

**Only use AGB labels for points flagged as 'STABLE'.**

### 5.3 The Temporal Context Stack

For disturbance awareness, we sample temporal context at BOTH observation time AND AlphaEarth time:

| Feature | At Observation Year | At AE Year (2020) | Delta |
|---------|--------------------|--------------------|-------|
| MODIS Land Cover | LC class at obs_year | LC class at 2020 | Changed? |
| Hansen loss | Cumulative loss to obs_year | Cumulative loss to 2020 | Loss between? |
| TerraClimate VPD | VPD at obs_year | VPD at 2020 | Climate shift |
| MODIS NPP | NPP at obs_year | NPP at 2020 | Productivity change |

This enables the model to learn: "a tree observed in 2005 at a location that had NPP=800 then but NPP=200 now likely experienced disturbance."

---

## 6. Multi-Task Architecture Design

### 6.1 Architecture Decision: Shared Backbone + Task-Specific Heads

**Strongly supported by literature.** Key evidence:
- Ruder (2017): Hard parameter sharing is an implicit regularizer for related tasks
- Caruana (1997): Auxiliary tasks that provide a different "view" of the same phenomenon improve the main task
- Standley et al. (2020): Related tasks benefit from sharing all layers except output
- Species and carbon are fundamentally linked — carbon stock is determined by species composition

**Architecture:**
```
Input features (~350D) ──┐
                         ├──> Gated Fusion (128D)
AlphaEarth 8yr (8×64D) ─┘        │
     │                            │
     └──> L-TAE Temporal ─────────┘
          Encoder (128D)          │
                            Input Projection (128→256)
                                  │
                            ResBlock ×4 (256D)
                                  │
                         Shared Representation (256D)
                              /        \
                        Species Head    Carbon Head
                        Linear(43,500)  MLP(256→128→128→3-6)
                        bias=False      Softplus output
                        an_full loss    Huber loss
```

### 6.2 Carbon Head Design

```python
class CarbonHead(nn.Module):
    def __init__(self, input_dim=256, hidden_dim=128, num_outputs=3):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),  # Lower than species (0.3) — regression is more sensitive
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, num_outputs),  # AGB, NPP, SOC
            nn.Softplus(),  # Ensures non-negative
        )
```

**Outputs:**
- AGB: Predict in log-space → `log(1 + AGB/100)`, back-transform at inference
- NPP: Predict standardized (zero-mean, unit-variance)
- SOC: Predict in log-space → `log(1 + SOC/50)`, back-transform at inference
- Optional: canopy height, GPP, LAI

### 6.3 Loss Function Design

```python
# Total loss with uncertainty weighting (Kendall et al., 2018)
precision_s = exp(-log_var_species)  # Learned
precision_c = exp(-log_var_carbon)   # Learned

L_total = precision_s * L_species + 0.5 * precision_c * L_carbon
        + log_var_species + log_var_carbon

# Where:
L_species = an_full_loss(...)  # Unchanged from v2.2
L_carbon = masked_mean(
    mask_agb * HuberLoss(pred_agb, log1p_agb_target) +
    mask_npp * HuberLoss(pred_npp, std_npp_target) +
    mask_soc * HuberLoss(pred_soc, log1p_soc_target)
)
```

**Why Huber over MSE:** AGB distribution is heavily right-skewed. MSE overweights outlier tropical forests (400+ Mg/ha). Huber with delta=1.0 on log-transformed targets is best (Qi et al., 2020: 3-7% RMSE improvement over MSE/MAE).

**Why uncertainty weighting:** Automatically learns optimal loss balance between classification (species) and regression (carbon). Better than fixed weights because the optimal ratio changes during training (Kendall et al., 2018).

### 6.4 Carbon as Both Input AND Target (Self-Supervised Signal)

Carbon features (AGB, NPP, SOC, canopy height) serve as BOTH inputs to the species head AND regression targets for the carbon head. This creates a denoising autoencoder effect.

**Handle with Feature Masking during training:**
```python
# Randomly zero out carbon input features with p=0.3-0.5
if self.training:
    carbon_mask = torch.bernoulli(torch.full_like(x_carbon, 0.5))
    x_carbon = x_carbon * carbon_mask
```

This prevents trivial identity mapping and forces the model to learn carbon from environmental context (He et al., 2022; Yoon et al., 2020).

### 6.5 Does Carbon Help Species? Evidence Says YES

- Botella et al. (2018): Joint species + environmental regression improved species AUC by 0.5-2.0%
- Becker et al. (2023): Multi-task CNN (classification + biomass regression) improved classification IoU by 2.1%
- Carbon regression provides dense, continuous gradients complementary to sparse binary species BCE loss
- Acts as regularizer preventing overfitting to noisy species labels

### 6.6 Temporal Encoding: L-TAE (Lightweight Temporal Attention)

For 8-year AlphaEarth trajectories:

```python
class SatelliteTemporalEncoder(nn.Module):
    def __init__(self, d_emb=64, n_years=8, n_heads=4, d_out=128):
        self.year_pe = nn.Embedding(n_years, d_emb)
        self.query = nn.Parameter(torch.randn(1, 1, d_emb))
        self.attn = nn.MultiheadAttention(d_emb, n_heads, batch_first=True)
        self.proj = nn.Linear(d_emb, d_out)
    
    def forward(self, x):  # x: (batch, 8, 64)
        pe = self.year_pe(torch.arange(8, device=x.device))
        x = x + pe.unsqueeze(0)
        q = self.query.expand(x.size(0), -1, -1)
        out, _ = self.attn(q, x, x)
        return self.proj(out.squeeze(1))  # (batch, 128)
```

Also compute summary stats (mean/std/trend = 192D) and concatenate with L-TAE output.

**Evidence:** Garnot & Landrieu (2021): L-TAE achieves best accuracy (93.1%) with fewest parameters for satellite time series < 20 timesteps.

### 6.7 Training Strategy

```
Phase 1 — Species Warm-up (Epochs 1-4):
  w_species = 1.0, w_carbon = linear ramp 0.0 → 0.3
  
Phase 2 — Joint Training (Epochs 5-16):
  w_species = 1.0, w_carbon = 0.3 (or uncertainty-weighted)
  
Phase 3 — Fine-tuning (Epochs 17-20):
  lr reduced to 1e-5, monitor for overfitting
  Save best by: 0.7 × species_top10 + 0.3 × (1 - normalized_carbon_rmse)
```

**Alternative (safer):** Train species-only first (12 epochs existing recipe), freeze backbone, train carbon head (5 epochs), unfreeze all, joint fine-tune (8 epochs).

### 6.8 Uncertainty Quantification for MRV

| Method | Compute Cost | What It Captures | MRV Suitability |
|--------|-------------|------------------|-----------------|
| **MC Dropout** (T=50) | 50× inference | Epistemic (model) uncertainty | Good |
| **Heteroscedastic output** (predict μ + log σ²) | 1× inference | Aleatoric (data) uncertainty | Good |
| **Deep Ensemble** (M=5) | 5× training | Both | Best |
| **Evidential DL** | 1× inference | Both (but can be overconfident OOD) | Moderate |

**Recommendation:** MC Dropout (T=50) + heteroscedastic output for Phase 1. Deep Ensemble (M=5 carbon heads on frozen backbone) for Phase 2 if MRV certification is pursued.

**Verra VCS v4.4 requires:** 90% CI where half-width < 10% of estimate (90/10 rule). If not met, conservative adjustment applied.

### 6.9 Hyperparameters

```
Shared backbone: hidden_dim=256, 4 ResBlocks, dropout=0.25
Temporal encoder: L-TAE (d_model=64, 4 heads, 8 timesteps) → 128D
Carbon head: 256→128→128→3, dropout=0.2, Softplus output
Training: batch_size=4096, lr=3e-4, AdamW (wd=0.01), CosineAnnealing
  epochs=20, gradient_clip=1.0, bfloat16 mixed precision (A100)
Carbon targets: AGB=log(1+AGB/100), NPP=standardized, SOC=log(1+SOC/50)
Feature masking: p=0.3 for carbon input features during training
Parameter count: ~12M (with 256D backbone) or ~27M (with 512D backbone)
```

---

## 7. Carbon MRV Market & Competitive Landscape

> **Full analysis in**: `docs/carbon-mrv-landscape-research.md`

### 7.1 The Species-Aware Carbon Gap

**No current tool combines global species prediction with carbon estimation.** Current players:

| Company | Approach | Uses Species? | Biggest Limitation |
|---------|----------|---------------|-------------------|
| **Pachama** | Optical + LiDAR satellite → generic AGB models | NO | Species-blind allometry |
| **NCX** | Species-aware BUT US-only (~750 species) | Yes (US only) | Not global |
| **Sylvera** | Carbon rating agency, uses satellite imagery | NO | No species resolution |
| **CTrees** | UCLA/NASA, GEDI + satellite fusion | NO | Generic AGB models |
| **Chloris** | Tropical forests, L-band SAR | NO | Regional, species-blind |
| **Carbon Direct** | Microsoft-backed, portfolio evaluation | NO | Relies on others' data |
| **SINR v3** | **43,500 species + carbon from shared model** | **YES (GLOBAL)** | In development |

### 7.2 Why Species Matter for Carbon Accuracy

- **Wrong allometric equation = 20-50% AGB error** (Chave et al., 2004)
- **Wood density ranges 0.1 to 1.4 g/cm³** — a 14x range. Same tree size, wildly different biomass.
- Example: Balsa (0.15 g/cm³) vs Lignum vitae (1.26 g/cm³) with same 30cm DBH → 8x difference in AGB
- Species-specific allometry reduces AGB RMSE by **15-25%** (Chen et al., 2023)
- Species-specific wood density reduces uncertainty from ~17% to ~6% (Vieilledent, 2012)

### 7.3 Market Size

- Voluntary carbon market (VCM): ~$723M (2023), projected $10-50B by 2030
- Forestry credits = ~50-60% of all VCM volume
- High-integrity credits command **2-5x price premium** over questionable credits
- Biodiversity credits: nascent ($0-100M) but expected rapid growth under EU Nature Restoration Law

### 7.4 Regulatory Opening

**VM0047 v1.1 (May 2025)** now explicitly allows remote sensing for baseline biomass measurement in Afforestation/Reforestation/Revegetation projects. This is a significant opening for satellite-based carbon estimation tools.

IPCC tier progression:
- Tier 1 (current): Generic emission factors (e.g., "tropical forest = 200 tC/ha")
- Tier 2: Country/biome-specific factors
- Tier 3: **Species-specific allometry + site measurements** ← what SINR v3 enables

### 7.5 Path from Research Model to MRV Tool

1. **Validation study** (~1 year): Compare SINR v3 carbon predictions against field plots (NEON, ForestGEO, FOS)
2. **Methodology tool** (~6 months): Write methodology module for VM0047/VM0006
3. **Pilot project** (~6 months): Partner with ARR/REDD+ project for field testing
4. **Registry approval** (~1 year): Submit to Verra for methodology approval
5. **Total timeline: ~3-4 years** from model training to accepted MRV tool

---

## 8. Allometric Databases

### 8.1 Key Databases

| Database | Equations | Species | Coverage Bias | Access |
|----------|----------|---------|---------------|--------|
| **GlobAllomeTree (FAO)** | ~12,000 | ~1,200 | Temperate heavy | Free, web-based |
| **Chave et al. (2014)** | 1 pan-tropical | All tropical | Tropical only | Published equation |
| **Jenkins et al. (2003)** | ~10 species-group | US species | US only | Published |
| **BIOMASS R package** | 1000s | Tropical | Tropical | R package |
| **Global Wood Density DB** | 16,467 records | ~8,412 species | Global | Published CSV |
| **BAAD** | 200+ studies | 200+ species | Global | Open data |
| **GlobAllomeTree** | ~12,000 | ~1,200 | Temperate heavy | Free |
| **GLOWCAD** | 3,676 records | 864 species | Global | Open |

### 8.2 The Chave et al. (2014) Pan-Tropical Equation

```
AGB = 0.0673 × (ρ × D² × H)^0.976
```
Where: ρ = wood density (g/cm³, **species-specific**), D = DBH (cm), H = height (m)

**Key insight:** The SINGLE most important species-specific parameter is **wood density (ρ)**. If you know the species, you know ρ, and the equation works. Without species, you're guessing ρ from a 14x range.

### 8.3 Coverage Gap

Only ~1,200 of ~73,000 known tree species have species-specific allometric equations (~1.6%). Only ~8,412 species have wood density measurements (~11.5%). For the remaining species, genus-level or family-level wood density is used, adding 10-30% additional uncertainty.

**Opportunity for Treekipedia:** Our species table already has `wood_density_ai`/`wood_density_human` columns. Populating these with Global Wood Density Database values would directly enable species-specific carbon estimation.

---

## 9. Implementation Priorities

### Phase 1: Current Sprint (during backfill/carbon sampling)

1. **FIX GEDI GriddedVeg bug** in `unified_gee_sampler_v3.py` — stop using `.mosaic()`, select specific metric images
2. **Add GEDI L4B** to carbon sampler — wall-to-wall AGBD currently missing
3. **Add ALOS PALSAR HH/HV** to feature sampling — L-band SAR as biomass proxy, already in GEE
4. **Temporal match MODIS NPP/LAI/EVI** to observation year in sampling pipeline

### Phase 2: Pre-Training Data Preparation

5. **Download ESA CCI Biomass v6.0** from CEDA — 100m, 2015-2022 annual AGB
6. **Upload to GEE or extract via BigQuery** — temporally match to observation years
7. **Implement disturbance screening** in BQ: flag points where Hansen loss occurred between obs year and carbon data year
8. **Compute derived features** in BQ: ae_mean/std/trend, change flags, temporal LULC delta

### Phase 3: Model Architecture

9. **Add L-TAE temporal encoder** for 8-year AE trajectories
10. **Add carbon regression head** (256→128→128→3, Softplus, Huber loss)
11. **Add uncertainty weighting** for multi-task loss balance
12. **Add feature masking** for carbon input features (p=0.3)
13. **Update training script** for phased training schedule

### Phase 4: Training & Validation

14. **Train on A100 80GB** with phased schedule (20 epochs, ~40 hours)
15. **Validate species performance** — must match or exceed v2.2 (top-10=59.34%, top-50=90.08%)
16. **Validate carbon performance** — target AGB RMSE < 50 Mg/ha
17. **Add NEON field data** as independent validation

### Phase 5: External Data Integration (after v3 training)

18. **Integrate ESA BIOMASS** L2 products when available (~2027)
19. **Integrate NISAR** L-band when science data released (~mid-2026)
20. **Ingest ICESat-2 ATL08** for boreal coverage (>51.6N)
21. **Populate species table** with wood density from Global Wood Density Database
22. **Build species-specific carbon estimation** using predicted species + allometric equations

---

## 10. Key Citations

| Topic | Citation | Year | Key Finding |
|-------|---------|------|-------------|
| Multi-task sharing | Ruder, arXiv:1706.05098 | 2017 | Hard sharing > soft for related tasks |
| Loss balancing | Kendall et al., CVPR | 2018 | Uncertainty weighting for classification+regression |
| Gradient management | Chen et al., ICML (GradNorm) | 2018 | Balance gradient norms across tasks |
| MC Dropout | Gal & Ghahramani, ICML | 2016 | T=30-50 for calibrated uncertainty |
| Deep ensembles | Lakshminarayanan et al., NeurIPS | 2017 | M=5 sufficient |
| Satellite temporal | Garnot & Landrieu, ICCV | 2021 | L-TAE best for short time series |
| 1D Conv temporal | Pelletier et al., RS | 2019 | Matches LSTM for <20 timesteps |
| Pan-tropical allometry | Chave et al., GCB | 2014 | Wood density critical for AGB |
| Species-specific AGB | Chen et al., FEM | 2023 | Species allometry reduces RMSE 15-25% |
| Wood density → AGB | Réjou-Méchain et al., MEE | 2017 | Species wood density reduces uncertainty 50% → 20% |
| Allometric equation error | Chave et al., Oecologia | 2004 | Wrong equation = 20-50% AGB error |
| Log-transformed AGB | Duncanson et al., RSE | 2022 | Improves R² for GEDI models |
| Huber loss for AGB | Qi et al., RS | 2020 | 3-7% RMSE improvement over MSE/MAE |
| SINR architecture | Cole et al., ICML | 2023 | Spatial implicit neural representations |
| Feature masking | He et al., CVPR (MAE) | 2022 | Masked prediction for self-supervised learning |
| Location embeddings | Rao et al., arXiv (SatCLIP) | 2023 | Variables as inputs AND targets |
| Multi-task biomass | Becker et al., ISPRS | 2023 | Multi-task improves biomass R² by 5% |
| Joint species+env | Botella et al., MTAP | 2018 | Joint training improves species AUC 0.5-2% |
| ESA CCI Biomass | Santoro et al., ESSD | 2021 | 100m global AGB maps |
| GEDI GriddedVeg | Burns et al., Sci Data | 2024 | Gridded vegetation structure metrics |
| GEDI L4B | Dubayah et al., Sci Remote Sens | 2022 | Gridded AGB from GEDI |
| MRV standards | Verra VCS Standard v4.4 | 2023 | 90/10 rule for uncertainty deductions |
| VM0047 | Verra | 2025 (v1.1) | Remote sensing now allowed for baseline |
| Carbon market | Ecosystem Marketplace | 2024 | VCM ~$723M, 50-60% forestry |

---

*Research conducted February 25, 2026. Sources: 5 parallel research agents covering GEE datasets, LiDAR calibration, ESA/NASA missions, multi-task architecture literature, and carbon MRV market analysis.*
