# Carbon MRV Landscape, Allometric Databases, and the Case for Species-Aware Carbon Estimation

**Research Document — SINR v3 Market Positioning**
**Date: February 2026**
**Status: Living Document**

---

## Table of Contents

1. [Allometric Equation Databases](#1-allometric-equation-databases)
2. [Why Species-Aware Carbon Estimation Matters](#2-why-species-aware-carbon-estimation-matters)
3. [Carbon Credit Methodologies](#3-carbon-credit-methodologies)
4. [Current Carbon Estimation Players](#4-current-carbon-estimation-players)
5. [The Market Opportunity](#5-the-market-opportunity)
6. [MRV Requirements](#6-mrv-requirements)
7. [The "Biggest Error" Problem](#7-the-biggest-error-problem)
8. [How SINR v3 Fits](#8-how-sinr-v3-fits)

---

## 1. Allometric Equation Databases

### 1.1 GlobAllomeTree (FAO)

**URL:** http://www.globallometree.org/
**Maintained by:** FAO (Food and Agriculture Organization of the United Nations), CIRAD, and the French National Research Institute for Sustainable Development (IRD).

- **Number of equations:** Over 12,000 allometric equations as of its latest public release. The database aggregates equations from published scientific literature spanning multiple decades of forestry research.
- **Species coverage:** Approximately 1,200 tree species are represented. However, the distribution is heavily skewed: temperate species (especially European and North American species) are overrepresented, while tropical species — which account for the majority of global tree diversity — are significantly underrepresented.
- **Format:** Web-based searchable database. Equations can be queried by species, genus, family, geographic region, biome, or predictor variable (DBH, height, etc.). Data is downloadable in CSV/spreadsheet formats.
- **Access:** Freely accessible online, though registration may be required for bulk downloads. The database is a public good maintained under FAO's mandate.
- **Key limitation:** Many equations are region-specific and were developed from small sample sizes (sometimes < 30 trees). Extrapolating a regional equation to a different geographic context introduces substantial error. The database contains equations at species, genus, and mixed-species levels — not all are truly species-specific.

### 1.2 Chave et al. (2014) — Improved Pan-Tropical Allometric Equation

**Citation:** Chave, J., Réjou-Méchain, M., Búrquez, A., et al. (2014). "Improved allometric models to estimate the aboveground biomass of tropical trees." *Global Change Biology*, 20(10), 3177–3190.

This is the current **gold standard** pan-tropical allometric equation, widely used in REDD+ projects, national forest inventories, and remote sensing biomass estimation.

**The equation:**
```
AGB_est = 0.0673 × (ρ × D² × H)^0.976
```

Where:
- **ρ** = wood density (g/cm³) — species-specific
- **D** = diameter at breast height (DBH, cm)
- **H** = total tree height (m)

**Key inputs needed:**
1. **DBH** — the primary measurement, typically from field inventory
2. **Total tree height** — often estimated from remote sensing (LiDAR) or field measurement; subject to measurement error
3. **Wood density** — species-specific parameter, looked up from databases (see Section 1.9)

**Critical insight for SINR v3:** The Chave 2014 equation explicitly requires **wood density (ρ)**, which varies by species from ~0.1 to ~1.3 g/cm³. Knowing the species allows you to look up the correct wood density, which is a multiplicative term in the equation. Using the wrong wood density (or a generic average) propagates error directly and proportionally into the AGB estimate.

**Development data:** Based on a pantropical dataset of 4,004 directly harvested (destructively sampled) trees from 58 sites across the tropics. Trees ranged from 5–212 cm DBH.

**Height alternative:** When height is not available, Chave et al. (2014) also provided a version using a bioclimatic stress variable (E) as a proxy:
```
AGB_est = exp(−1.803 − 0.976E + 0.976 ln(ρ) + 2.673 ln(D) − 0.0299 [ln(D)]²)
```
Where E is derived from temperature seasonality, precipitation deficit, and precipitation seasonality — variables derivable from climate datasets without field measurement.

### 1.3 Chave et al. (2005) — Earlier Pan-Tropical Equation

**Citation:** Chave, J., Andalo, C., Brown, S., et al. (2005). "Tree allometry and improved estimation of carbon stocks and balance in tropical forests." *Oecologia*, 145(1), 87–99.

**The equation family** included three models for dry, moist, and wet tropical forests:
- **Dry forests:** AGB = exp(−2.187 + 0.916 × ln(ρD²H))
- **Moist forests:** AGB = exp(−2.977 + ln(ρD²H))  [approximately: AGB = ρ × exp(−2.977 + 2.0 ln(D) + 0.5 ln(H))]
- **Wet forests:** AGB = exp(−2.557 + 0.940 × ln(ρD²H))

**Key differences from Chave 2014:**
- Required forest type classification (dry/moist/wet) as an input
- Based on a smaller dataset (~2,410 trees)
- Higher residual error (especially for large trees)
- The 2014 revision removed the need for forest type classification by introducing the bioclimatic stress variable (E)
- The 2014 version showed ~15% improvement in prediction accuracy

**Both the 2005 and 2014 equations require wood density as a species-linked parameter.** This is the fundamental reason species identification matters for allometric carbon estimation.

### 1.4 Jenkins et al. (2003) — US National Biomass Equations

**Citation:** Jenkins, J.C., Chojnacky, D.C., Heath, L.S., & Birdsey, R.A. (2003). "National-scale biomass estimators for United States tree species." *Forest Science*, 49(1), 12–35.

- **Coverage:** Continental United States; 10 species-group equations covering hardwoods and softwoods
- **Number of equations:** 10 generalized equations by species group, derived from a meta-analysis of >2,600 published biomass equations for individual species
- **Predictor:** DBH only (no height or wood density required) — this simplicity is both a strength and a limitation
- **Format:** Published coefficients for the power-law form: `biomass = exp(β₀ + β₁ × ln(DBH))`
- **Species groups:** Aspen/alder/cottonwood/willow; Soft maple/birch; Mixed hardwood; Hard maple/oak/hickory/beech; Cedar/larch; Douglas-fir; True fir/hemlock; Spruce; Pine; Woodland species
- **Limitation:** By collapsing hundreds of species into 10 groups, species-specific variation (especially in wood density) is averaged out. The Jenkins equations are suitable for national-scale inventory reporting (IPCC Tier 2) but introduce substantial error at the individual tree or plot level.
- **Used by:** US Forest Service Forest Inventory and Analysis (FIA) program, though FIA has since moved to more species-specific equations (Component Ratio Method, CRM equations).

### 1.5 BIOMASS Package (R)

**Citation:** Réjou-Méchain, M., Tanguy, A., Piponiot, C., et al. (2017). "biomass: An R package for estimating above-ground biomass and its uncertainty in tropical forests." *Methods in Ecology and Evolution*, 8(9), 1163–1167.

**What it contains:**
- Implements the Chave et al. (2014) pan-tropical allometric equations
- Includes a **built-in wood density database** derived from the Global Wood Density Database (Chave et al., 2009; Zanne et al., 2009) — containing ~16,467 entries for ~8,412 species
- Provides functions to:
  - Look up species-specific wood density by taxonomic name
  - Fall back to genus-level or family-level means when species data is unavailable
  - Estimate tree height from DBH using region-specific height-diameter models (Feldpausch et al., 2012)
  - Propagate errors through Monte Carlo simulation (accounting for wood density uncertainty, allometric model error, and measurement error)
- **Key feature:** The uncertainty propagation framework explicitly quantifies how much of the total AGB uncertainty comes from wood density (species identity), height estimation, and model selection — directly relevant to our value proposition.

### 1.6 ForestGEO (Smithsonian)

**Full name:** Forest Global Earth Observatory (formerly CTFS-ForestGEO)
**URL:** https://forestgeo.si.edu/

- **Network:** 77 forest dynamics plots across 27 countries on 6 continents
- **Trees monitored:** >7 million individual trees from >12,000 species, re-censused every ~5 years
- **Data:** Species-level identification, DBH at each census, mortality, recruitment, spatial coordinates within plots
- **Relevance:** Provides the ground-truth tree-level data needed to calibrate and validate allometric equations. This is one of the richest sources of species-identified, measured tree data on Earth.
- **Access:** Data access is through a formal proposal process; not openly downloadable, but available for approved research collaborations.
- **Limitation:** Plots are typically 16–50 ha — large by ecological standards but small for remote sensing validation. Coverage is biased toward accessible tropical and temperate forests.

### 1.7 TRY Plant Trait Database

**URL:** https://www.try-db.org/
**Citation:** Kattge, J., et al. (2020). "TRY plant trait database – enhanced coverage and open access." *Global Change Biology*, 26(1), 119–188.

- **Records:** >15 million trait records for >280,000 plant species
- **Relevant traits:** Wood density, specific leaf area, leaf nitrogen content, maximum tree height, seed mass, bark thickness, and more
- **Wood density records:** Substantial overlap with the Global Wood Density Database; TRY provides an integrative platform
- **Access:** Open access for most datasets; some require individual contributor approval
- **Relevance:** The most comprehensive plant functional trait database. When combined with species predictions from SINR v3, TRY enables derivation of any species-linked trait from a geographic prediction.

### 1.8 BAAD — Biomass And Allometry Database

**Citation:** Falster, D.S., Duursma, R.A., Ishihara, M.I., et al. (2015). "BAAD: a Biomass And Allometry Database for woody plants." *Ecology*, 96(5), 1445–1445.

- **Records:** 259,634 measurements from 176 published studies
- **Species:** 597 species from all major vegetation types
- **Variables:** 45 different measurements per plant, including stem diameter, height, crown dimensions, leaf area, and biomass of various organs
- **Access:** Freely available on GitHub and through the Ecological Archives
- **Relevance:** Provides individual-level allometric measurements (not just fitted equation coefficients), enabling custom allometric model fitting for specific species or species groups. Crucial for validating and extending allometric relationships.

### 1.9 Global Wood Density Database

**Primary sources:**
- Chave, J., et al. (2009). "Towards a worldwide wood economics spectrum." *Ecology Letters*, 12(4), 351–366.
- Zanne, A.E., et al. (2009). "Global wood density database." Dryad Digital Repository. doi:10.5061/dryad.234

**Database contents:**
- **~16,467 records** covering **~8,412 tree species** from 5 continents
- Values are reported as specific gravity (oven-dry mass / green volume), equivalent to wood density in g/cm³
- Coverage spans tropical, temperate, and boreal species

**Species coverage analysis:**
- Of the ~60,000–73,000 known tree species globally (Beech et al., 2017), only ~8,400 have directly measured wood density — approximately **11–14% coverage**
- For species without direct measurements, genus-level averages are used (~4,000 genera represented)
- Family-level averages serve as last resort (~230 families)

**Range of wood density values:**
- **Minimum:** ~0.08–0.10 g/cm³ (e.g., *Ochroma pyramidale* — Balsa)
- **Maximum:** ~1.26–1.39 g/cm³ (e.g., *Guaiacum officinale* — Lignum vitae, *Krugiodendron ferreum* — Black ironwood)
- **Global mean (tropical):** ~0.60 g/cm³
- **Global mean (temperate):** ~0.50 g/cm³
- **Global mean (boreal):** ~0.45 g/cm³
- **Standard deviation within genus:** typically 0.05–0.15 g/cm³
- **Standard deviation across species:** ~0.18 g/cm³ globally

**GLOWCAD — Global Woody Tissue Carbon Concentration Database:**
- **3,676 individual records** from **864 tree species** (Doraisami et al., 2022, *Scientific Data*)
- Covers carbon concentration (mass of C per unit dry mass) — not the same as wood density but complementary
- Key finding: the assumption that wood is 50% carbon (commonly used in IPCC Tier 1) overestimates tropical forest carbon stocks by **~8.9%** (Martin et al., 2018, *Nature Geoscience*)
- Actual carbon concentrations range from ~41% to ~55% of dry mass, varying systematically by species and biome
- Available via Dryad: https://doi.org/10.5061/dryad.18931zcxk

### 1.10 How Species-Specific Are These Equations?

A critical analysis of the allometric equation landscape reveals a **species-specificity gap**:

| Database | Total Equations/Records | Truly Species-Specific | Genus-Level | Regional/Mixed |
|---|---|---|---|---|
| GlobAllomeTree | ~12,000 | ~3,000–4,000 (~30%) | ~2,000–3,000 (~20%) | ~5,000–6,000 (~50%) |
| Chave 2014 | 1 pan-tropical | 0 (generic by design) | 0 | 1 (pan-tropical) |
| Jenkins 2003 | 10 (US species groups) | 0 | 0 | 10 (species-group) |
| BIOMASS (R) wood density | ~16,467 | ~8,412 species | ~4,000 genera | ~230 families |
| ForestGEO | Tree-level data | Species-ID'd trees | N/A | N/A |
| BAAD | 259,634 measurements | 597 species | Varied | Varied |

**The key problem:** Even the "species-specific" equations in GlobAllomeTree cover only ~1,200 species out of ~60,000–73,000 known tree species. That's roughly **1.6–2.0%** of global tree species diversity with directly calibrated allometric equations. The remaining ~98% of species must rely on genus-level, family-level, or pantropical generic equations.

**This is precisely where SINR v3 creates value:** By knowing which species are present, we can:
1. Select the best available allometric equation (species-specific if available)
2. Fall back intelligently to genus or family level
3. Apply the correct wood density value
4. Apply the correct carbon concentration value
5. Quantify the uncertainty introduced by each fallback

### 1.11 Key Variables Needed for Allometric Estimation

| Variable | Source | Our Capability |
|---|---|---|
| **DBH** (Diameter at Breast Height) | Field measurement, or estimated from LiDAR-derived crown area | Not directly from SINR v3; would come from field data or partner LiDAR |
| **Height** | LiDAR, photogrammetry, or estimated from DBH via height-diameter relationships | Could be integrated from GEDI/ICESat-2 spaceborne LiDAR |
| **Wood density** | Species-specific lookup from Global Wood Density Database | **SINR v3 provides species → enables wood density lookup** |
| **Crown area** | Drone/aerial imagery, or satellite at ≤1m resolution | Potentially derivable from high-res satellite inputs |
| **Carbon concentration** | Species-specific lookup from GLOWCAD | **SINR v3 provides species → enables C concentration lookup** |
| **Bioclimatic stress (E)** | Derived from WorldClim/climate data | Available at any global location |

---

## 2. Why Species-Aware Carbon Estimation Matters

### 2.1 Error from Using the Wrong Allometric Equation

Multiple studies have quantified the error introduced by allometric equation misspecification:

**Chave et al. (2004)** — "Error propagation and scaling for tropical forest biomass estimates," *Philosophical Transactions of the Royal Society B*, 359(1443), 409–420:
- Demonstrated that **allometric model selection is the single largest source of error** in AGB estimation from field data
- The choice of allometric equation contributed **~20–50% of the total AGB estimation error** at the plot level
- At the individual tree level, errors from equation selection can exceed **100%** for large trees

**Molto et al. (2013)** — "Error propagation in biomass estimation in tropical forests," *Methods in Ecology and Evolution*, 4(2), 175–183:
- Quantified four sources of error in AGB estimation: (1) measurement error in DBH, (2) height estimation error, (3) wood density uncertainty, and (4) allometric model residual error
- Found that **wood density contributes ~6–17% of total AGB uncertainty** at the individual tree level
- **Allometric model residual error** contributes ~30–50% of uncertainty at the tree level
- At the **1-ha plot level**, allometric model error and wood density uncertainty together account for >50% of total uncertainty

**Kearsley et al. (2013)** — "Conventional tree height–diameter relationships significantly overestimate aboveground carbon stocks in the Central Congo Basin," *Nature Communications*, 4, 2269:
- Found that applying allometric equations calibrated in other tropical regions to Central African forests led to AGB overestimates of **up to 96%**
- Highlighted the critical role of regional variation in height-diameter relationships and tree architecture

### 2.2 How Species Identification Improves AGB Estimates

**Bastin et al. (2015)** — "Seeing Central African forests through their largest trees," *Scientific Reports*, 5, 13156:
- Large trees (top 5% by diameter) hold **~50% of aboveground biomass** in tropical forests
- For these trees, species identity is critical because large trees tend to be from a relatively small number of species, many of which have known allometric data
- Correct species identification of large trees improved plot-level AGB estimates by **15–30%**

**Sullivan et al. (2018)** — "Field methods for sampling tree height for tropical forest biomass estimation," *Methods in Ecology and Evolution*, 9(5), 1179–1189:
- Demonstrated that knowing species identity allows better height estimation through species-specific height-diameter relationships
- Generic height-diameter models introduced **10–25% additional error** in AGB compared to species-specific models

**Réjou-Méchain et al. (2017)** — The BIOMASS R package documentation:
- When species identity is known, wood density can be assigned with an uncertainty of ~10% (species-level standard deviation)
- When only genus is known, uncertainty increases to ~15–25%
- When only family is known, uncertainty increases to ~30–50%
- When nothing is known (plot-level average), uncertainty in wood density is ~40–60%

### 2.3 Generic "Tropical Forest" Equation vs. Species-Specific

The scale of error from ignoring species composition:

**Scenario: Same forest, different approaches**

Consider a 1-hectare tropical forest plot with 400 trees ≥ 10 cm DBH:
- **Approach 1 (IPCC Tier 1):** Use a single biome-level biomass density value (e.g., 180 Mg/ha for tropical moist forest) — no species data needed. **Typical uncertainty: ±50–100%**
- **Approach 2 (Generic allometry):** Apply Chave 2014 with average wood density (0.60 g/cm³) for all trees. **Typical uncertainty: ±20–30%**
- **Approach 3 (Species-specific wood density):** Apply Chave 2014 with species-specific wood density. **Typical uncertainty: ±10–20%**
- **Approach 4 (Species-specific allometry):** Use species-specific allometric equations where available, with species-specific wood density. **Typical uncertainty: ±8–15%**

The progression from Tier 1 to species-specific represents **a 3–10× reduction in uncertainty**.

### 2.4 Wood Density Variation and AGB Estimates

Wood density is a **multiplicative parameter** in the Chave et al. equations. This means errors in wood density translate directly and proportionally to errors in AGB.

**The range problem:**
- Lightest commercial timber: *Ochroma pyramidale* (Balsa) — ρ = 0.10–0.20 g/cm³
- Heaviest commercial timber: *Guaiacum officinale* (Lignum vitae) — ρ = 1.05–1.26 g/cm³
- **This represents a 6–12× range in wood density**

**Worked example:**
Consider two trees with identical DBH = 50 cm and Height = 25 m:

Using Chave 2014: AGB = 0.0673 × (ρ × D² × H)^0.976

- **Balsa** (ρ = 0.15): AGB = 0.0673 × (0.15 × 2500 × 25)^0.976 = 0.0673 × (9,375)^0.976 ≈ **478 kg**
- **Lignum vitae** (ρ = 1.26): AGB = 0.0673 × (1.26 × 2500 × 25)^0.976 = 0.0673 × (78,750)^0.976 ≈ **3,725 kg**

**Same dimensions, 7.8× difference in AGB.** If you used the tropical mean wood density (0.60) for both:
- **Generic estimate:** AGB ≈ 2,020 kg
- **Error for Balsa:** Overestimate by **323%** (predicted 2,020 kg vs actual 478 kg)
- **Error for Lignum vitae:** Underestimate by **46%** (predicted 2,020 kg vs actual 3,725 kg)

This is not an exotic edge case. Within a single tropical forest hectare, wood density commonly ranges from 0.25 to 1.0 g/cm³ across the tree community (a 4× range), producing AGB estimation errors of **30–60%** at the individual tree level when species identity is unknown.

### 2.5 Carbon Concentration Variation

Beyond wood density, the carbon concentration of wood (the fraction of dry mass that is carbon) also varies by species:

- **Commonly assumed:** 50% (IPCC Tier 1 default)
- **Actual range:** 41–55% (from GLOWCAD; Martin et al., 2018)
- **Tropical angiosperms mean:** ~47.3% ± 2.4%
- **Temperate gymnosperms mean:** ~50.8% ± 1.1%
- **Net effect:** Using 50% across all species **overestimates tropical forest carbon by ~8.9%** and slightly underestimates boreal conifer carbon

When combined with wood density errors, species misidentification can compound to produce carbon stock errors of **40–80%** at the individual tree level.

---

## 3. Carbon Credit Methodologies

### 3.1 VM0047 (Verra — ARR: Afforestation, Reforestation, Revegetation)

**Status:** Active since September 28, 2023 (v1.0); v1.1 active since May 14, 2025
**Scope:** Afforestation, Reforestation, and Revegetation activities
**Label eligibility:** Carbon removals only (not avoidance)
**ICVCM status:** Approved for Core Carbon Principles (CCP) Label

**Two approaches:**

1. **Area-based approach:** For projects that change land cover from non-forest to forest
   - Uses remote sensing + plot-based sampling
   - Employs a **dynamic performance benchmark (PB)** comparing project plots to matched control plots
   - Uses a **Stocking Index (SI)** derived from remote sensing to quantify changes in vegetative cover
   - **Species relevance:** The methodology does not explicitly require species identification for the area-based approach. It relies on remote-sensing-derived indices and sample plots. However, plot-based sampling for validation **does** involve species identification and species-appropriate allometric equations.

2. **Census-based approach:** For dispersed planting activities (agroforestry, urban forestry, etc.)
   - Requires a full census of planted trees
   - Trees tracked by GPS coordinates or physical markers
   - **Species relevance:** In census-based projects, the species planted is known by definition. Carbon estimation uses species-appropriate growth curves and allometric equations.

**v1.1 Key update (May 2025):** Projects may now use **remote sensing to estimate pre-existing woody biomass at the start date**, under specific conditions. This opens the door for remote sensing-derived AGB estimates (like SINR v3) to play a role in baseline estimation.

**How VM0047 handles species:**
- For plot-based measurement: species identification is standard protocol in field inventories
- Allometric equation selection: projects must justify their choice of allometric model, typically selecting equations validated for the relevant species mix and geographic region
- Wood density: must be sourced from published databases with species-specific values preferred
- **Gap for SINR v3:** VM0047 v1.1 now allows remote sensing for pre-existing biomass measurement, but primarily relies on the Stocking Index for ongoing monitoring. A model that provides species-informed AGB estimates could strengthen both baseline measurement and verification.

### 3.2 VM0006 (Verra — REDD+: Methodology for Carbon Accounting for Mosaic and Landscape-Scale REDD Projects)

**Scope:** Reducing Emissions from Deforestation and Forest Degradation

**How it estimates baseline carbon:**
- Historical deforestation analysis (10-year reference period)
- Stratification of the project area by forest type, land use, and carbon stock
- AGB estimated through **sample plot inventory** using allometric equations
- Baseline carbon stock calculated per stratum, then projected deforestation rates applied

**Species treatment:**
- Field plots require tree identification to species or genus level
- Allometric equations must be appropriate for the species composition
- Wood density assigned by species from published databases
- **Default option:** Use pantropical equations (Chave et al.) with species-specific wood density
- **IPCC Tier approach:** Encourages Tier 2 (country-specific) or Tier 3 (species-specific) where data permits

**Opportunity for SINR v3:** REDD+ projects must establish baseline carbon stocks across often vast and inaccessible forest areas. Remote sensing-based estimation is already widely used for stratification and area analysis. A species-aware model could improve the accuracy of carbon stock estimates in each stratum by correctly weighting the allometric contributions of different species, rather than assuming a single average wood density per forest type.

### 3.3 CDM AR Methodology (Clean Development Mechanism)

**Context:** The CDM was established under the Kyoto Protocol. AR (Afforestation/Reforestation) methodologies under CDM (AR-ACM0003, AR-AMS0007) are now being phased out under Verra's VCS program. Projects using these methodologies must complete validation by June 30, 2025, and transition to VM0047.

**Historical approach:**
- Required establishment of baseline (pre-project) carbon stocks and ex ante projections of carbon accumulation
- Species-specific growth models or published yield tables used for projections
- Conservative default values (IPCC Tier 1) accepted where species data unavailable
- **Species treatment:** Generally required species identification for planted trees; used species-appropriate growth curves; allowed generic values for existing vegetation

**Legacy relevance:** Many active forestry carbon projects were developed under CDM AR methodologies. The transition to VM0047 means these projects will need to align with VM0047's remote sensing + performance benchmark approach.

### 3.4 Gold Standard

**Approach to carbon quantification:**
- Gold Standard's Land Use & Forests Activity Requirements specify quantification methods for ARR and other forestry project types
- Accepts IPCC methodologies, Verra VCS-aligned approaches, and own approved methodologies
- Emphasizes conservative estimation and additionality demonstration

**Species treatment:**
- Field inventories with species identification are the norm
- Allometric equation selection must be justified
- Encourages species-specific or at minimum genus-specific wood density values
- **Biodiversity co-benefits:** Gold Standard's certification framework explicitly values biodiversity, making species-level data directly relevant for premium credit pricing through co-benefit certification (e.g., CCB Standards)

### 3.5 Plan Vivo

**Approach:** Community-based forestry carbon projects, particularly in developing countries
- Focuses on smallholder agroforestry, community forest management, and watershed restoration
- Uses "Plan Vivo Certificates" (PVCs) rather than traditional carbon credits
- Carbon estimation relies on locally calibrated growth models and conservative default factors

**Species treatment:**
- Projects typically involve planting known species (agroforestry species, native restoration species)
- Species selection is documented in the project design
- Growth models and allometric equations are species-specific where possible
- **Emphasis on locally appropriate species** — aligns well with a model that can predict which species thrive where

### 3.6 Which Methodologies Require Species-Level Data?

| Methodology | Species-Level Required? | Where? |
|---|---|---|
| VM0047 (area-based) | Not explicitly for remote sensing; yes for field plots | Field validation plots |
| VM0047 (census-based) | Yes — all trees tracked individually | Census records |
| VM0006 (REDD+) | Yes — in field inventory plots | Baseline carbon stock estimation |
| CDM AR | Yes — for planted trees | Growth projections |
| Gold Standard | Yes — in field inventories | Carbon quantification |
| Plan Vivo | Yes — for planted species | Growth models |
| ART-TREES (jurisdictional) | Not required at tree level; uses emission factors | National/subnational reporting |

**Key insight:** All field-based carbon quantification ultimately requires species identification. The question is whether remote sensing can supplement or partially replace field work. Currently, no MRV methodology explicitly accepts species predictions from remote sensing models as a substitute for field identification. **This is the regulatory frontier where SINR v3 must operate.**

### 3.7 IPCC Tiers and Species Data

The IPCC Guidelines for National Greenhouse Gas Inventories (2006, refined 2019) define three tiers of increasing data specificity:

**Tier 1 — Default Values:**
- Uses IPCC default emission factors and biomass density values
- No species-specific data needed
- Example: "Tropical moist forest = 180–300 Mg/ha aboveground biomass" (varies by continent)
- Carbon fraction assumed at 0.47 for hardwoods, 0.51 for softwoods (2019 Refinement updated from 0.50)
- **Uncertainty: ±50–100%**
- Used by: Countries with limited forest inventory capacity

**Tier 2 — Country-Specific:**
- Uses nationally or regionally derived emission factors, biomass equations, and growth rates
- Typically derived from national forest inventory data
- Allometric equations may be regional or species-group level
- Wood density and carbon fractions may be country-specific averages
- **Uncertainty: ±20–50%**
- Used by: Most developed countries, some developing countries with established inventory programs

**Tier 3 — Detailed / Model-Based:**
- Uses species-specific allometric equations, wood density, and carbon fractions
- Integrates repeated measurements (growth modeling, mortality, recruitment)
- May incorporate process-based models (e.g., CENTURY, BIOME-BGC)
- Spatial explicit, often using GIS-linked inventory data
- **Uncertainty: ±10–20%**
- Used by: Few countries for full national reporting; common for project-level carbon accounting in certified projects

**SINR v3's role in the tier progression:**
- A species-aware remote sensing model bridges the gap between Tier 1 and Tier 3
- For countries currently reporting at Tier 1, SINR v3 could enable a jump to Tier 2 or near-Tier 3 accuracy **without requiring a full national field inventory**
- This is particularly valuable for tropical developing countries that lack extensive field data but host the most carbon-rich and biodiverse forests

---

## 4. Current Carbon Estimation Players

### 4.1 Pachama

**Background:** Founded in 2018, San Francisco. Raised >$79M in funding (Series B in 2021). Named after Pachamama (earth mother in Quechua).

**Methodology:**
- Uses satellite imagery (primarily optical: Sentinel-2, Landsat; some use of synthetic aperture radar SAR) combined with LiDAR data (airborne where available, spaceborne GEDI)
- Machine learning models trained on field inventory data to predict forest carbon stocks
- Provides carbon monitoring for REDD+ and ARR projects
- Operates a marketplace connecting carbon credit buyers with verified projects

**Do they use species information?** No. Pachama's approach is fundamentally **species-agnostic**. Their models predict aggregate biomass/carbon at the pixel or plot level without identifying which species are present. They use canopy height, spectral reflectance, and texture features as proxies.

**Biggest source of error:** Reliance on generic allometric relationships applied uniformly across heterogeneous species compositions. In species-rich tropical forests, this can introduce 20–40% error in AGB estimation. Their LiDAR-derived canopy height models work well for estimating total biomass but cannot distinguish between a 30m tall low-density wood tree and a 30m tall high-density wood tree.

**How species-aware estimation would improve their work:** If species composition were known, Pachama could:
- Apply species-weighted wood density instead of average values
- Reduce reliance on LiDAR height as the dominant predictor
- Better account for structural diversity within forests
- Improve accuracy in mixed-species tropical forests by 15–30%

### 4.2 NCX (Natural Capital Exchange)

**Background:** Founded 2017, San Francisco. Raised >$50M. Originally "SilviaTerra."

**Methodology:**
- Developed the "basemap" — a tree-level map of the continental US using satellite imagery, machine learning, and the US Forest Service FIA dataset
- Estimates individual tree attributes (species, diameter, height) across the US at ~10m resolution
- Their carbon credit approach is unusual: they sell 1-year "tonne-year" credits (harvest deferral credits), where landowners agree not to harvest trees for one additional year
- Does not use traditional REDD+ or ARR methodologies

**Do they use species information?** **Yes, for the US.** NCX's basemap includes predicted species at the tree level, using FIA training data. This is one of the closest analogs to what SINR v3 does, but limited to the continental United States and its ~750 native tree species (vs. SINR v3's global scope of 43,500 species).

**Biggest source of error:** 
- Their 1-year crediting model has faced criticism for questionable additionality (would the trees have been harvested anyway?)
- Species predictions are limited to FIA species in the US — no global capability
- Accuracy of individual tree predictions degrades in dense canopy conditions

**Competitive positioning for SINR v3:** NCX demonstrates that species-level prediction has market value but is geographically limited. SINR v3 would be the first global equivalent.

### 4.3 Sylvera

**Background:** Founded 2020, London. Raised >$96M. Carbon credit rating agency.

**Methodology:**
- Rates existing carbon credits (Verra, Gold Standard, ACR, CAR) on a scale from AAA to D
- Uses satellite-derived deforestation monitoring, biomass estimation, and additionality assessment
- Provides independent verification of carbon project claims
- Uses machine learning on satellite time-series to detect deforestation and degradation

**Do they use species information?** No. Sylvera's biomass estimates are species-agnostic, relying on satellite-derived proxies (vegetation indices, canopy height from GEDI, SAR backscatter).

**Biggest source of error:** As a ratings agency, their error is inherited from the underlying biomass estimation methods. Without species information, their independent carbon stock estimates carry the same generic-allometry uncertainties as other remote sensing approaches. They acknowledge this limitation in their confidence intervals.

**How species-aware estimation would improve their work:** Species-informed estimates would enable Sylvera to:
- Better validate project-reported carbon stocks
- Identify discrepancies between reported species composition and actual composition
- Provide more granular risk ratings based on species-appropriate error bounds
- Detect potential fraud (e.g., a project claiming high-carbon-density species in an area where those species don't naturally occur)

### 4.4 CTrees (UCLA/NASA Spinoff)

**Background:** Launched 2022 from Sassan Saatchi's lab at JPL/UCLA. Led by Saatchi, a pioneer in satellite biomass mapping.

**Methodology:**
- Produces global-scale biomass maps using multiple satellite sensors (Sentinel-1 SAR, Sentinel-2 optical, GEDI LiDAR, ICESat-2)
- Machine learning models trained on global ground-truth data
- Provides near-real-time monitoring of carbon stock changes
- Focuses on national and jurisdictional carbon accounting (relevant for REDD+ and ART-TREES)

**Do they use species information?** No. CTrees operates at the landscape/pixel level, predicting AGB and carbon stock without species identification. Their approach uses statistical relationships between satellite features and field-measured AGB.

**Biggest source of error:** The same fundamental limitation as all species-agnostic approaches: they estimate AGB as a single number per pixel without understanding the species composition that generates that biomass. This means:
- Errors in training data allometry propagate to predictions
- Changes in species composition over time (e.g., due to selective logging of high-value species) may not register as carbon loss
- Difficulty distinguishing between forests of similar height but different wood density (and hence different carbon content)

**How species-aware estimation would improve their work:** Integration of species predictions would allow CTrees to:
- Apply species-weighted allometric corrections to their AGB maps
- Detect compositional changes that alter carbon stocks without changing canopy structure
- Improve accuracy in heterogeneous forests

### 4.5 Chloris Geospatial

**Background:** Founded by Alessandro Baccini (formerly of Woods Hole Research Center). Focused on tropical forest carbon monitoring.

**Methodology:**
- Uses a combination of satellite imagery and machine learning to estimate AGB and carbon stock changes
- Focuses on tropical forests and the carbon implications of land-use change
- Provides data services for REDD+ projects and national forest monitoring

**Do they use species information?** No. Like other satellite-based biomass mappers, Chloris operates at the aggregate level.

**Biggest source of error:** Temporal and spatial resolution limitations; inability to distinguish between species-driven biomass differences and structural differences.

### 4.6 Carbon Direct

**Background:** Founded 2019 by Jonathan Goldberg, backed by Breakthrough Energy (Bill Gates). ~70+ scientists on staff.

**Methodology:**
- Not a remote sensing company per se — they are a **carbon management advisory firm** and credit procurement platform
- Evaluates carbon credit quality using scientific due diligence
- Advises corporate buyers (Microsoft, JPMorgan Chase, etc.) on carbon removal portfolio construction
- Their science team assesses project methodologies, permanence risk, additionality, and MRV quality

**Do they use species information?** Carbon Direct's science team evaluates whether project-level carbon estimates appropriately use species-specific allometric data. They do not generate their own species predictions, but they assess whether others' estimates are scientifically robust.

**Relevance for SINR v3:** Carbon Direct represents a potential **customer or partner** — they advise major corporate carbon credit buyers and would value a tool that improves the accuracy of project-level carbon estimation. Their scientists would likely be early evaluators and validators of a species-aware approach.

### 4.7 Verra / Gold Standard (The Registries)

**What data they require:**
- **Project Design Document (PDD):** Must describe the methodology for carbon quantification, including allometric equations used, wood density values, and their justification
- **Monitoring Reports:** Must document how carbon stocks are measured or modeled over time
- **Validation/Verification:** Independent third-party auditors (VVBs — Validation/Verification Bodies) review the PDD and monitoring reports

**Species data requirements:**
- Field inventory plots: species identification required
- Allometric equation: must be appropriate for the species mix
- Wood density: species-specific values preferred; generic values acceptable with conservative adjustments
- **Neither Verra nor Gold Standard currently requires or accepts species predictions from remote sensing models**

### 4.8 Planet / NICFI (Norway's International Climate and Forest Initiative)

**Background:** Planet (satellite company) partnered with Norway's NICFI to provide free, high-resolution satellite imagery of tropical forests worldwide.

**Imagery:**
- 4.7m resolution daily coverage (PlanetScope)
- Freely available for monitoring tropical forests in 64 countries between 30°N and 30°S
- Used by governments, researchers, and NGOs for deforestation monitoring

**How used for carbon:**
- Planet imagery is a **data input**, not a carbon estimation tool in itself
- Used for: land cover classification, deforestation detection, forest degradation assessment
- Combined with other data sources (LiDAR, SAR) for biomass estimation

**Species relevance:** Planet imagery at 4.7m resolution is insufficient for individual tree species identification (would require ≤1m resolution + spectral bands). However, it provides the spatiotemporal data backbone for forest monitoring that SINR v3's predictions could enhance.

### 4.9 Summary Table: Current Players vs. Species-Awareness

| Company | Uses Species Data? | Geographic Scope | Primary Methodology | Key Limitation |
|---|---|---|---|---|
| Pachama | No | Global (tropical focus) | Satellite + LiDAR ML | No species awareness |
| NCX | Yes (US only) | Continental US only | ML on FIA data | US-only, questionable additionality |
| Sylvera | No | Global (rating agency) | Satellite time-series | Inherited allometric errors |
| CTrees | No | Global | Multi-sensor ML | No species awareness |
| Chloris | No | Tropics | Satellite ML | No species awareness |
| Carbon Direct | Evaluates others | Global (advisory) | Scientific due diligence | Not a measurement tool |
| **SINR v3** | **Yes — 43,500 species** | **Global** | **Species + Carbon prediction** | **Needs validation** |

**SINR v3 would be the only tool that combines global species prediction with carbon estimation.** This is a genuinely unique market position.

---

## 5. The Market Opportunity

### 5.1 Voluntary Carbon Market (VCM) Size

**2023 figures (most recent reliable data):**
- Total VCM value: **$723 million** (Ecosystem Marketplace, 2024) — a decline from the 2021 peak of ~$2 billion
- Volume traded: ~150 million tonnes CO2e
- The market contracted in 2022–2023 due to quality concerns, media scrutiny (Guardian/Die Zeit investigations of Verra REDD+ credits), and buyer hesitancy

**2024 estimates:**
- The market showed signs of recovery in H2 2024
- Estimated value: $800M–$1.2B (multiple sources; final figures pending)
- Volume increasing as post-ICVCM quality framework builds buyer confidence

**2025–2030 projections:**
- McKinsey (2023): VCM could reach **$50 billion by 2030** in a high-growth scenario, **$10–15 billion** in a moderate scenario
- BloombergNEF: Projects $35B by 2030
- The Taskforce on Scaling Voluntary Carbon Markets (TSVCM, chaired by Mark Carney) projected demand of 1.5–2.0 Gt CO2e by 2030 and 7–13 Gt CO2e by 2050

**Key trend:** The market is shifting from "volume" to "quality." Buyers increasingly prefer:
- Credits with higher confidence in quantification
- Credits with co-benefits (biodiversity, community)
- Credits certified under ICVCM Core Carbon Principles
- **This quality shift directly favors more accurate, species-aware approaches**

### 5.2 Compliance Carbon Market Size

**2023 figures:**
- Total compliance market value: **~$881 billion** (World Bank, 2024)
- Dominated by EU ETS (~$750B), with contributions from China ETS, California/Quebec (WCI), South Korea, UK
- **Forestry credits are NOT typically eligible** in most compliance markets (EU ETS excludes them; California allows limited forestry offsets)

**2024 updates:**
- Article 6.4 of the Paris Agreement (the successor to CDM) is operational, creating a new compliance-grade mechanism that could include forestry
- CORSIA (aviation carbon offsetting) allows some forestry-based credits — potential volume of 2.5 Gt CO2e annually by 2035

### 5.3 Price per Tonne CO2

| Market | Price (2024–2025) |
|---|---|
| EU ETS | €60–90/tonne |
| California Cap-and-Trade | $30–40/tonne |
| Article 6 (emerging) | $5–30/tonne (highly variable) |
| VCM — REDD+ (low quality) | $2–8/tonne |
| VCM — REDD+ (high quality, ICVCM-labeled) | $10–25/tonne |
| VCM — ARR (nature-based removals) | $15–40/tonne |
| VCM — Engineered CDR (DAC, BiCRS) | $200–1,000/tonne |
| VCM — High-quality forestry with co-benefits | $20–50/tonne |

**The price premium for quality is significant.** High-integrity credits with robust MRV, additionality evidence, and biodiversity co-benefits can command 2–5× the price of generic credits. Species-aware estimation directly supports this premium positioning.

### 5.4 Forestry-Based Credits as a Share of Total

- **Forestry and land use credits represent ~50–60%** of all VCM credit issuances by volume (Verra registry data)
- REDD+ alone accounts for ~30–35% of all VCM credits
- ARR accounts for ~10–15%
- Improved Forest Management (IFM): ~5–8%
- These percentages have been relatively stable, though REDD+ faced scrutiny in 2023

### 5.5 Main Criticisms of Forestry Carbon Credits

1. **Additionality:** Would the deforestation have occurred anyway? Many REDD+ projects have been criticized for overclaiming by establishing baselines with inflated deforestation rates (West et al., 2023, *Science*).

2. **Permanence:** Carbon stored in trees can be released by fire, disease, illegal logging, or policy changes. A 100-year permanence guarantee is inherently uncertain for biological systems.

3. **Leakage:** Protecting one forest may simply shift deforestation to an adjacent area. Quantifying leakage is methodologically challenging.

4. **Quantification accuracy:** Baseline carbon stocks and carbon stock changes are estimated with substantial uncertainty. The Guardian/Die Zeit investigation (January 2023) suggested many Verra REDD+ projects may have overestimated avoided deforestation by >90%.

5. **Over-crediting:** When carbon stock estimates are biased high (due to generic allometric assumptions), more credits are issued than carbon is actually stored or protected.

### 5.6 How Species-Level Data Addresses These Criticisms

| Criticism | How Species Data Helps |
|---|---|
| **Additionality** | Species composition data can validate baseline conditions and detect whether claimed "forest" is actually forest with the claimed carbon density |
| **Permanence** | Species-specific vulnerability to fire, drought, and pests enables better permanence risk assessment |
| **Leakage** | Species tracking can detect compositional changes in buffer areas that indicate displacement of degradation |
| **Quantification accuracy** | Species-specific allometric equations and wood density directly reduce AGB estimation error by 15–40% |
| **Over-crediting** | Replacing generic tropical-mean wood density with species-specific values reduces systematic upward bias in carbon estimates |

### 5.7 Emerging Biodiversity Credits

**Market context:**
- Biodiversity credits are an emerging market, distinct from but complementary to carbon credits
- Unlike carbon credits (which represent tonnes of CO2), biodiversity credits represent measurable biodiversity outcomes (species protection, habitat restoration, ecosystem integrity)
- Early frameworks: Plan Vivo's Biodiversity Certificates, Wallacea Trust, GreenCollar's NaturePlus, the Biodiversity Credit Alliance

**Market size:** Currently nascent (<$50M annually), but projected to grow significantly:
- The Global Biodiversity Framework (GBF) adopted at COP 15 (Montreal, 2022) calls for $200B/year in biodiversity finance by 2030
- The gap between current funding and the GBF target is ~$700B/year
- Biodiversity credits could fill a portion of this gap

**How species data creates value:**
- **Species richness and composition** are primary metrics for biodiversity credits
- A model that predicts which species are present (and at what probability) provides the foundational data layer for biodiversity credit assessment
- Co-stacking carbon and biodiversity credits on the same project area requires species-level data — something only SINR v3 currently provides at scale
- Species occurrence predictions can be used to verify biodiversity claims in project areas
- Species-aware monitoring can track biodiversity outcomes over time (e.g., is species richness increasing after restoration?)

---

## 6. MRV Requirements

### 6.1 Uncertainty Requirements for Verra Credits

**Standard requirement:** Carbon stock estimates must achieve **≤15% uncertainty at the 90% confidence interval** (per the VCS Standard, v4.5).

In practice, this means:
- The half-width of the 90% confidence interval must be ≤15% of the mean estimate
- If the uncertainty exceeds 15%, a **conservativeness deduction** is applied: the reported carbon stocks are reduced by the amount that the uncertainty exceeds the threshold
- Example: If uncertainty is 25%, the deduction is (25% − 15%) = 10%, so only 90% of the estimated carbon is credited

**What this means for SINR v3:** To be useful in carbon crediting, our model's predictions must either:
1. Meet the ≤15% uncertainty threshold on their own, OR
2. Be combined with field data to achieve the threshold (hybrid approach), OR
3. Be used in a verification/validation role where they don't need to meet the threshold independently but inform whether field-based estimates are reasonable

### 6.2 How Uncertainty Is Currently Estimated in Forestry Carbon Projects

**Field-based uncertainty propagation:**
1. **Measurement error:** DBH measurement has ~1–2% error; height measurement has 5–15% error
2. **Allometric model error:** The residual standard error of the allometric equation — typically 15–30% for pantropical models, 5–15% for species-specific models
3. **Wood density uncertainty:** Typically ±10% if species-specific, ±15–25% if genus-level, ±30–50% if generic
4. **Sampling error:** Depends on number and size of plots; typically 5–15% at 90% CI for well-designed inventories
5. **These errors are propagated** using Monte Carlo simulation (as implemented in the BIOMASS R package) or analytical error propagation formulas

### 6.3 What Would It Take for a Remote Sensing Model to Be Accepted for MRV?

**Current state of acceptance:**
- Remote sensing is widely accepted for **monitoring change** (deforestation detection, land cover classification)
- Remote sensing is increasingly accepted for **stratification** (dividing project areas into homogeneous biomass classes)
- Remote sensing is **not yet accepted as a standalone method** for carbon stock quantification in most VCS/Gold Standard methodologies
- VM0047 v1.1 (May 2025) now allows remote sensing for **pre-existing biomass estimation** under specific conditions — this is a significant step forward

**What's needed for full acceptance:**
1. **Peer-reviewed validation** against field data across multiple biomes and forest types
2. **Published uncertainty estimates** meeting or approaching the ±15% at 90% CI threshold
3. **Demonstrated comparability** with field-based estimates (low bias, quantified precision)
4. **Methodological acceptance:** A VCS-approved tool or module that specifies how the remote sensing model should be applied
5. **Third-party audit trail:** VVBs must be able to independently verify the model's outputs
6. **Temporal consistency:** The model must be applicable across monitoring periods (not just a snapshot)

**Path forward for SINR v3:**
- Phase 1: Publish validation study showing SINR v3 predictions vs. field inventory data at multiple sites
- Phase 2: Propose a VCS "Tool" or "Module" for species-informed remote sensing-based carbon estimation
- Phase 3: Pilot with 3–5 Verra-registered projects, using SINR v3 alongside field data
- Phase 4: Submit for VCS methodology approval

### 6.4 VM0047 Specifics: Remote Sensing for Baseline

**VM0047 v1.1 (May 2025) key provisions:**
- Projects may use remote sensing to estimate pre-existing woody biomass at the project start date
- Conditions: the remote sensing method must be validated against field data in the project region; uncertainty must be quantified and reported
- The area-based approach uses a "Stocking Index" derived from remote sensing (not AGB directly) — this is a normalized vegetation measure, not a direct carbon estimate
- The census-based approach (for dispersed plantings) relies on individual tree tracking, not remote sensing

**Monitoring provisions:**
- Ongoing monitoring uses the dynamic performance benchmark comparing project plots to control plots
- Field plots are still required for calibration and validation
- Remote sensing (specifically, the Stocking Index) serves as the spatial scaling mechanism

**Can remote sensing replace field plots?** Not entirely under VM0047. Field plots remain the "ground truth" for calibrating the Stocking Index. However, the methodology allows progressive integration of remote sensing, and future revisions may further expand this role.

### 6.5 Temporal Requirements for Remeasurement

| Methodology | Monitoring Frequency | Verification Frequency |
|---|---|---|
| VM0047 (Verra ARR) | Continuous monitoring using remote sensing; field plots at each verification | Every 5 years (maximum) |
| VM0006 (Verra REDD+) | At least every 5 years for field plots; annual deforestation monitoring via remote sensing | Every 5 years |
| Gold Standard | Per methodology, typically every 5 years | Per methodology |
| Plan Vivo | Annual monitoring with field-based verification | Annual or biennial |
| ART-TREES | Biennial reporting | Per crediting period |

**Implication for SINR v3:** A model that can provide annual or sub-annual updates (as satellite revisit times allow) has a significant advantage over field-only monitoring, which is typically on a 5-year cycle. Continuous monitoring with species-aware predictions could detect carbon stock changes between field measurements.

---

## 7. The "Biggest Error" Problem

### 7.1 The Single Biggest Source of Error in Carbon Estimation from Remote Sensing

**Answer: Allometric equation selection and application**, followed closely by wood density assignment.

The error budget for remote sensing-based AGB estimation can be decomposed as follows (synthesis from Chave et al., 2004; Molto et al., 2013; Réjou-Méchain et al., 2014; Duncanson et al., 2019):

| Error Source | Contribution to Total AGB Error (Individual Tree) | Contribution to Total AGB Error (1-ha Plot) |
|---|---|---|
| **Allometric model residual error** | 30–50% | 15–30% (partially cancels across trees) |
| **Wood density uncertainty** | 6–20% | 10–25% (systematic, doesn't cancel) |
| **Height estimation error** | 10–20% | 5–15% |
| **DBH measurement error** | 2–5% | 1–3% |
| **Remote sensing calibration** | N/A (field) or 10–30% (RS) | 10–30% (for RS) |
| **Sampling/spatial scaling** | N/A | 10–20% |

**Key insight:** For **field-based** estimation, the allometric model + wood density together account for **40–70%** of total error at the tree level. For **remote sensing-based** estimation, the sensor-to-biomass calibration step (which embeds allometric assumptions) is the largest single contributor.

**The critical realization:** Remote sensing instruments do not measure biomass directly. They measure proxies (canopy reflectance, height, backscatter). Converting these proxies to biomass requires allometric-like relationships, which are trained on field data that itself uses allometric equations. **Errors in the allometric layer propagate through the entire remote sensing estimation chain.**

### 7.2 Allometric Equation Selection Error: 20–50%

**Chave et al. (2004),** *Phil. Trans. R. Soc. B*, 359:
- Showed that substituting one published allometric equation for another (all calibrated for tropical trees) changes predicted AGB by **20–50%** for the same tree
- The equation-to-equation variation was **larger** than the residual prediction error of any single equation
- This means the *choice* of equation matters more than the *precision* of any given equation

**Picard et al. (2012),** "Should tree biomass estimation account for spatial autocorrelation?", *Annals of Forest Science*:
- Found that using locally calibrated equations reduced prediction bias by **25–40%** compared to pantropical equations
- The improvement was primarily driven by better representation of local species composition and wood density

**van Breugel et al. (2011),** *Biogeosciences*:
- In Panamanian secondary forests, compared 10 published allometric equations applied to the same trees
- Results ranged from **87 to 211 Mg/ha** for the same forest plots — a **2.4× range** depending on equation choice

### 7.3 Wood Density Uncertainty Contribution to AGB Error

**Chave et al. (2006),** "Regional and phylogenetic variation of wood density across 2456 neotropical tree species," *Ecological Applications*:
- Wood density varies from 0.08 to 1.39 g/cm³ across neotropical species
- Within a single 1-ha plot, wood density ranges from 0.30 to 0.90 g/cm³ typically
- Coefficient of variation of wood density within a plot: 20–30%
- This translates to **~20–30% uncertainty in plot-level AGB** if a single average wood density is used

**Vieilledent et al. (2012),** *Biotropica*:
- Quantified that wood density contributed **~17% of total AGB uncertainty** in Madagascar tropical forests
- Using species-specific wood density reduced this contribution to **~6%** — nearly a 3× improvement

**Baker et al. (2004),** "Variation in wood density determines spatial patterns in Amazonian forest biomass," *Global Change Biology*:
- Demonstrated that wood density variation across Amazonian forests accounts for **a 30% difference in AGB** between western Amazonia (low wood density, young soils, fast turnover) and eastern/central Amazonia (high wood density, old soils, slow turnover)
- These two regions have similar canopy height and structure but **very different carbon stocks** due to species composition
- **A canopy-height-only model (like most current remote sensing approaches) cannot capture this variation.** Species awareness is required.

### 7.4 The Error Propagation Framework

**Réjou-Méchain et al. (2014),** "Local spatial structure of forest biomass and its consequences for remote sensing of carbon stocks," *Biogeosciences*:

Total AGB variance at a given scale can be decomposed as:
```
Var(AGB_total) = Var(allometric_model) + Var(wood_density) + Var(height) + Var(DBH) + Var(sampling) + 2×Cov(terms)
```

Key properties:
- **Allometric model error and wood density error are partially correlated** (because wood density is an input to the allometric equation)
- **Random errors cancel out** at larger scales (plot → landscape), but **systematic biases do not**
- **Wood density bias is systematic** — if you use the wrong average wood density for a region, the error doesn't decrease with more trees
- **This is why species-aware estimation matters at every scale:** it reduces the systematic component of error

### 7.5 Studies Quantifying Total Error by Approach

**Duncanson et al. (2019),** "The importance of consistent global forest aboveground biomass product validation," *Surveys in Geophysics*:
- Compared 6 global satellite-based AGB maps against field data
- Found **root mean square errors (RMSE) of 30–100% at the pixel level** (0.5–1 ha resolution)
- Systematic biases of **15–40%** depending on the biome
- Concluded that "allometric uncertainty is a dominant source of error in all satellite-based biomass products"

**Avitabile et al. (2016),** "An integrated pan-tropical biomass map using multiple reference datasets," *Global Change Biology*:
- Found that fusing multiple satellite AGB maps reduced random errors but not systematic biases
- The persistent bias was attributed to **allometric assumptions embedded in the training data**

---

## 8. How SINR v3 Fits

### 8.1 Integration into VM0047 or Similar Methodology

**Immediate opportunities:**

1. **Baseline biomass estimation (VM0047 v1.1):** The updated methodology explicitly allows remote sensing for estimating pre-existing woody biomass. SINR v3 could provide species-informed AGB estimates for the project area at the start date, validated against a smaller number of field plots.

2. **Stocking Index enhancement:** VM0047 uses a generic Stocking Index derived from remote sensing. A species-aware index that accounts for the carbon implications of different species compositions would be more informative than a simple vegetation index.

3. **Verification support:** SINR v3 could serve as an independent check on field-reported AGB values. If the model predicts 200 Mg/ha and the project reports 400 Mg/ha, this discrepancy would flag potential over-crediting.

4. **Monitoring between field visits:** With 5-year field measurement cycles, SINR v3 could provide annual species-aware AGB updates, detecting potential issues (illegal logging, fire, degradation) earlier.

### 8.2 Species Predictions → Allometric Equation Selection

**The pipeline:**

```
SINR v3 prediction at location (lat, lon) →
    Species probability distribution (e.g., 30% Tectona grandis, 20% Swietenia macrophylla, ...) →
        For each species: look up wood density from Global Wood Density Database →
        For each species: select best available allometric equation from GlobAllomeTree →
        Weight by species probability →
    Species-weighted AGB estimate with quantified uncertainty
```

**Example implementation:**
1. SINR v3 predicts top-10 species at a location with probabilities
2. For each species, retrieve wood density (species-specific if available, genus-level if not)
3. If height/DBH data is available (from LiDAR or field data), apply species-specific allometry
4. If only canopy height is available (from GEDI), use Chave 2014 with species-weighted wood density
5. Compute weighted-average AGB and uncertainty (incorporating species probability uncertainty + allometric uncertainty + wood density uncertainty)

**This approach is novel and publishable.** No existing system combines species probability predictions with allometric equation selection at global scale.

### 8.3 AGB Predictions as Independent Verification

**Current problem in carbon markets:**
- Project developers self-report carbon stocks
- VVBs (auditors) have limited ability to independently verify these claims, especially in remote tropical locations
- The Guardian/Die Zeit investigation (2023) showed that many REDD+ projects had overestimated their carbon impact

**How SINR v3 helps:**
- Provides an **independent, remotely-derived estimate** of AGB/carbon for any location on Earth
- This estimate is **species-informed**, making it more accurate than generic satellite-based estimates
- Can be compared against project-reported values to flag discrepancies
- Does not replace field verification but provides a powerful screening tool

**Use cases:**
- **Registries (Verra, Gold Standard):** Could integrate SINR v3 as a screening tool in the credit review process
- **Rating agencies (Sylvera, BeZero, Calyx Global):** Could use SINR v3 to improve their independent verification
- **Buyers (via Carbon Direct, South Pole, etc.):** Could use SINR v3 in due diligence before purchasing credits
- **Auditors (VVBs):** Could use SINR v3 as a desk-review tool before field visits

### 8.4 Path from Research Model to Accepted MRV Tool

**Phase 1: Scientific Validation (6–12 months)**
- Publish peer-reviewed validation study comparing SINR v3 species predictions + derived AGB against field inventory data at ≥20 sites across ≥5 biomes
- Target journals: *Nature Climate Change*, *Global Change Biology*, *Remote Sensing of Environment*, *Environmental Research Letters*
- Quantify and publish uncertainty metrics (RMSE, bias, coverage of confidence intervals)
- Compare accuracy against existing tools (Pachama, CTrees, etc.)

**Phase 2: Methodology Development (12–18 months)**
- Develop a VCS "Tool" or "Module" that describes how SINR v3 species-informed AGB estimation should be applied
- The tool would specify:
  - Required input data (satellite imagery dates, SINR v3 version, supplementary data)
  - Species prediction methodology and uncertainty quantification
  - Allometric equation selection protocol
  - Integration with field data (hybrid approach)
  - Quality assurance/quality control procedures
- Submit for VCS public consultation and expert review

**Phase 3: Pilot Projects (12–24 months)**
- Partner with 3–5 project developers to apply SINR v3 alongside conventional MRV
- Demonstrate comparability and added value
- Collect feedback from VVBs
- Document case studies

**Phase 4: Formal Approval (6–12 months)**
- Submit tool/module for formal VCS approval
- If approved, SINR v3 becomes a recognized component of Verra-certified MRV
- Parallel submission to Gold Standard and/or ART-TREES

**Total timeline: ~3–4 years from research model to approved MRV tool**

### 8.5 Which Certification Bodies Need to Approve

| Body | What They Approve | Relevance |
|---|---|---|
| **Verra (VCS)** | Methodologies, tools, modules for carbon quantification | Primary target — largest carbon standard by volume |
| **Gold Standard** | Methodologies for carbon and SDGs | Secondary target — premium market segment |
| **ART (Architecture for REDD+ Transactions)** | TREES standard for jurisdictional REDD+ | Relevant for national/subnational government adoption |
| **ICVCM** | Core Carbon Principles (meta-standard for quality) | Not direct approval, but CCP alignment is important |
| **ISO 14064** | Standards for GHG accounting | Relevant for compliance market pathway |
| **SBTi** | Science Based Targets initiative | Relevant for corporate climate commitments |
| **IPCC** | Not an approval body, but their methods are referenced by all standards | Alignment with IPCC Tier 3 guidance is essential |

### 8.6 The Unique Value Proposition — Summary

**What no other tool in the market provides:**

1. **Global species prediction (43,500 species)** — no competitor has this at scale
2. **Species-informed carbon estimation** — converts species knowledge into improved AGB accuracy
3. **Integrated species + carbon** — a single model that predicts both, enabling consistency
4. **Biodiversity co-benefits quantification** — species predictions directly support biodiversity credit claims
5. **Uncertainty reduction** — species knowledge reduces the systematic component of AGB error that cannot be reduced by sampling alone

**The competitive moat:** Building a global species distribution model for 43,500 species is a multi-year, data-intensive undertaking that is difficult to replicate. The combination with carbon estimation creates a product that is simultaneously valuable for:
- Carbon credit MRV
- Biodiversity credit development
- National forest inventory enhancement
- Conservation planning
- Reforestation/restoration project design
- Academic research

---

## References

### Allometric Databases and Equations
- Chave, J., et al. (2005). Tree allometry and improved estimation of carbon stocks. *Oecologia*, 145, 87–99.
- Chave, J., et al. (2009). Towards a worldwide wood economics spectrum. *Ecology Letters*, 12, 351–366.
- Chave, J., et al. (2014). Improved allometric models to estimate AGB of tropical trees. *Global Change Biology*, 20, 3177–3190.
- Falster, D.S., et al. (2015). BAAD: a Biomass And Allometry Database. *Ecology*, 96, 1445.
- Jenkins, J.C., et al. (2003). National-scale biomass estimators for US tree species. *Forest Science*, 49, 12–35.
- Réjou-Méchain, M., et al. (2017). BIOMASS: an R package for estimating AGB and uncertainty. *Methods in Ecology and Evolution*, 8, 1163–1167.
- Zanne, A.E., et al. (2009). Global wood density database. Dryad. doi:10.5061/dryad.234.
- Doraisami, M., et al. (2022). A global database of woody tissue carbon concentrations. *Scientific Data*, 9, 284.
- Martin, A.R., et al. (2018). Global patterns in wood carbon concentration. *Nature Geoscience*, 11, 915–920.

### Error Propagation and Uncertainty
- Baker, T.R., et al. (2004). Variation in wood density determines spatial patterns in Amazonian forest biomass. *Global Change Biology*, 10, 545–562.
- Chave, J., et al. (2004). Error propagation and scaling for tropical forest biomass estimates. *Phil. Trans. R. Soc. B*, 359, 409–420.
- Chave, J., et al. (2006). Regional and phylogenetic variation of wood density. *Ecological Applications*, 16, 2356–2367.
- Duncanson, L., et al. (2019). The importance of consistent global forest AGB product validation. *Surveys in Geophysics*, 40, 1007–1032.
- Kearsley, E., et al. (2013). Conventional tree height–diameter relationships significantly overestimate AGB in Central Congo. *Nature Communications*, 4, 2269.
- Molto, Q., et al. (2013). Error propagation in biomass estimation in tropical forests. *Methods in Ecology and Evolution*, 4, 175–183.
- Réjou-Méchain, M., et al. (2014). Local spatial structure of forest biomass. *Biogeosciences*, 11, 6827–6840.
- Vieilledent, G., et al. (2012). A universal approach to estimate biomass and carbon stock in tropical forests. *Biotropica*, 44, 831–839.
- van Breugel, M., et al. (2011). Estimating carbon stock in secondary forests. *Biogeosciences*, 8, 859–872.
- Avitabile, V., et al. (2016). An integrated pan-tropical biomass map. *Global Change Biology*, 22, 1406–1420.
- Picard, N., et al. (2012). Should tree biomass estimation account for spatial autocorrelation? *Annals of Forest Science*, 69, 443–457.
- Bastin, J-F., et al. (2015). Seeing Central African forests through their largest trees. *Scientific Reports*, 5, 13156.
- Sullivan, M.J.P., et al. (2018). Field methods for sampling tree height. *Methods in Ecology and Evolution*, 9, 1179–1189.

### Carbon Market
- Ecosystem Marketplace (2024). State of the Voluntary Carbon Markets.
- World Bank (2024). State and Trends of Carbon Pricing.
- McKinsey & Company (2023). Voluntary Carbon Market outlook.
- BloombergNEF (2024). Carbon offset market forecast.
- West, T.A.P., et al. (2023). Action needed to make carbon offsets from tropical forest conservation work for climate change mitigation. *Science*, 381, 873–877.

### Methodologies
- Verra (2025). VM0047 Methodology for Afforestation, Reforestation and Revegetation, v1.1.
- Verra (2022). VM0006 Methodology for Carbon Accounting for Mosaic and Landscape-Scale REDD Projects.
- IPCC (2006, refined 2019). Guidelines for National Greenhouse Gas Inventories, Volume 4: Agriculture, Forestry and Other Land Use.

### Trait Databases
- Kattge, J., et al. (2020). TRY plant trait database. *Global Change Biology*, 26, 119–188.
- Beech, E., et al. (2017). GlobalTreeSearch. *Journal of Sustainable Forestry*, 36, 454–489.

---

*This document should be updated as new data becomes available, particularly as SINR v3 validation results are published and carbon market regulations evolve.*
