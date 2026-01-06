# LEAF™ Score Report: Appalachian-Blue Ridge Forests

**Generated**: December 15, 2025
**Endpoint**: `GET /api/geospatial/leaf/score?eco_id=331`

---

## Ecoregion Overview

| Field | Value |
|-------|-------|
| **Eco ID** | 331 |
| **Name** | Appalachian-Blue Ridge forests |
| **Biome** | Temperate Broadleaf & Mixed Forests |
| **Realm** | Nearctic |
| **Countries** | United States |

---

## Methodology

**LEAF™** = Location-based Ecological Aptness Forecast

### Algorithm
```
Pool = (WCVP native species) UNION (species with GBIF occurrences)
     MINUS (species marked as introduced in WCVP)

Affinity = occurrence_count × tile_count × native_multiplier

Where:
  native_multiplier = 2.0 (native species)
                      1.0 (unknown status)

LEAF Score = percentile rank (0-100)
```

### Data Sources
- **Occurrences**: GBIF via 5.3M geohash tiles (Level 7, ~150m resolution)
- **Native Status**: WCVP (World Checklist of Vascular Plants) - Kew Gardens

### Tier Classification
| Tier | Score Range | Meaning |
|------|-------------|---------|
| **BEST** | 90-100 | Top 10% - Highly recommended |
| **GOOD** | 70-89 | Next 20% - Appropriate choice |
| **ACCEPTABLE** | 50-69 | Middle tier - Viable option |
| **LOW** | <50 | Below threshold |

---

## Statistics

| Metric | Count |
|--------|-------|
| **Total Species in Pool** | 3,292 |
| **Introduced Species Excluded** | 468 |
| **Native Species (ACCEPTABLE+)** | 98 |
| **Unknown Status (ACCEPTABLE+)** | 2 |
| **Total Qualifying (score ≥50)** | 100 |

**Key Insight**: 468 introduced species (14%) were automatically excluded, including known invasives like Tree of Heaven (*Ailanthus altissima*), Princess Tree (*Paulownia tomentosa*), and Mimosa (*Albizia julibrissin*).

---

## Top 50 Species (BEST Tier)

| Rank | Scientific Name | Common Name | Family | LEAF Score | Occurrences | Tiles |
|------|-----------------|-------------|--------|------------|-------------|-------|
| 1 | *Quercus alba* | White Oak | Fagaceae | 100.0 | 120,816 | 12,307 |
| 2 | *Acer rubrum* | Red Maple | Sapindaceae | 100.0 | 138,353 | 13,483 |
| 3 | *Quercus rubra* | Red Oak | Fagaceae | 99.9 | 104,306 | 12,581 |
| 4 | *Prunus serotina* | Black Cherry | Rosaceae | 99.9 | 110,586 | 12,173 |
| 5 | *Nyssa sylvatica* | Black Gum | Nyssaceae | 99.9 | 119,450 | 11,851 |
| 6 | *Quercus coccinea* | Scarlet Oak | Fagaceae | 99.8 | 98,508 | 11,484 |
| 7 | *Cornus florida* | Flowering Dogwood | Cornaceae | 99.8 | 99,369 | 11,525 |
| 8 | *Quercus velutina* | Black Oak | Fagaceae | 99.8 | 101,220 | 11,855 |
| 9 | *Fagus grandifolia* | American Beech | Fagaceae | 99.7 | 85,757 | 11,346 |
| 10 | *Juniperus virginiana* | Eastern Red Cedar | Cupressaceae | 99.7 | 90,742 | 10,797 |
| 11 | *Quercus falcata* | Southern Red Oak | Fagaceae | 99.6 | 91,964 | 9,081 |
| 12 | *Sassafras albidum* | Sassafras | Lauraceae | 99.6 | 75,710 | 11,874 |
| 13 | *Pinus strobus* | White Pine | Pinaceae | 99.6 | 70,654 | 12,875 |
| 14 | *Quercus stellata* | Post Oak | Fagaceae | 99.5 | 73,712 | 8,899 |
| 15 | *Pinus echinata* | Shortleaf Pine | Pinaceae | 99.5 | 74,563 | 9,190 |
| 16 | *Carya glabra* | Pignut Hickory | Juglandaceae | 99.5 | 97,230 | 7,179 |
| 17 | *Ilex opaca* | American Holly | Aquifoliaceae | 99.4 | 63,574 | 8,307 |
| 18 | *Acer saccharum* | Sugar Maple | Sapindaceae | 99.4 | 65,431 | 9,909 |
| 19 | *Carpinus caroliniana* | American Hornbeam | Betulaceae | 99.4 | 65,978 | 9,925 |
| 20 | *Cercis canadensis* | Eastern Redbud | Fabaceae | 99.3 | 52,236 | 8,850 |
| 21 | *Tsuga canadensis* | Eastern Hemlock | Pinaceae | 99.3 | 44,448 | 10,749 |
| 22 | *Quercus nigra* | Water Oak | Fagaceae | 99.3 | 63,180 | 7,832 |
| 23 | *Ostrya virginiana* | American Hophornbeam | Betulaceae | 99.2 | 47,591 | 9,145 |
| 24 | *Platanus occidentalis* | American Sycamore | Platanaceae | 99.2 | 48,856 | 9,003 |
| 25 | *Ulmus rubra* | Slippery Elm | Ulmaceae | 99.1 | 38,995 | 7,102 |
| 26 | *Quercus phellos* | Willow Oak | Fagaceae | 99.1 | 46,267 | 8,209 |
| 27 | *Betula lenta* | Sweet Birch | Betulaceae | 99.1 | 50,554 | 7,744 |
| 28 | *Carya ovata* | Shagbark Hickory | Juglandaceae | 99.0 | 45,327 | 5,987 |
| 29 | *Nyssa biflora* | Swamp Tupelo | Nyssaceae | 99.0 | 43,996 | 6,184 |
| 30 | *Magnolia acuminata* | Cucumber Tree | Magnoliaceae | 99.0 | 34,274 | 8,026 |
| 31 | *Magnolia virginiana* | Sweetbay Magnolia | Magnoliaceae | 98.9 | 35,723 | 5,685 |
| 32 | *Quercus pagoda* | Cherrybark Oak | Fagaceae | 98.9 | 30,299 | 7,245 |
| 33 | *Acer negundo* | Box Elder | Sapindaceae | 98.9 | 32,327 | 6,930 |
| 34 | *Quercus laurifolia* | Laurel Oak | Fagaceae | 98.8 | 36,104 | 4,485 |
| 35 | *Celtis occidentalis* | Common Hackberry | Cannabaceae | 98.8 | 32,236 | 5,598 |
| 36 | *Tilia americana* | American Basswood | Malvaceae | 98.8 | 29,782 | 6,772 |
| 37 | *Acer pensylvanicum* | Striped Maple | Sapindaceae | 98.7 | 22,274 | 5,761 |
| 38 | *Carya cordiformis* | Bitternut Hickory | Juglandaceae | 98.7 | 29,587 | 4,606 |
| 39 | *Quercus michauxii* | Swamp Chestnut Oak | Fagaceae | 98.7 | 22,681 | 6,065 |
| 40 | *Betula nigra* | River Birch | Betulaceae | 98.6 | 24,459 | 4,448 |
| 41 | *Quercus muehlenbergii* | Chinkapin Oak | Fagaceae | 98.6 | 25,617 | 4,702 |
| 42 | *Aesculus flava* | Yellow Buckeye | Sapindaceae | 98.5 | 18,738 | 3,892 |
| 43 | *Celtis laevigata* | Sugarberry | Cannabaceae | 98.5 | 20,740 | 3,770 |
| 44 | *Quercus marilandica* | Blackjack Oak | Fagaceae | 98.5 | 19,614 | 5,341 |
| 45 | *Castanea dentata* | American Chestnut | Fagaceae | 98.4 | 12,502 | 4,758 |
| 46 | *Taxodium distichum* | Bald Cypress | Cupressaceae | 98.4 | 14,928 | 4,037 |
| 47 | *Betula alleghaniensis* | Yellow Birch | Betulaceae | 98.4 | 12,770 | 5,101 |
| 48 | *Nyssa aquatica* | Water Tupelo | Nyssaceae | 98.3 | 11,844 | 3,489 |
| 49 | *Magnolia fraseri* | Fraser Magnolia | Magnoliaceae | 98.3 | 14,935 | 3,361 |
| 50 | *Salix nigra* | Black Willow | Salicaceae | 98.3 | 14,798 | 3,449 |

---

## Family Distribution (Top 50)

| Family | Species Count | Notable Species |
|--------|---------------|-----------------|
| **Fagaceae** | 17 | Oaks, American Beech, American Chestnut |
| **Sapindaceae** | 5 | Maples, Yellow Buckeye |
| **Pinaceae** | 4 | White Pine, Hemlock, Shortleaf Pine |
| **Betulaceae** | 4 | Birches, Hornbeams |
| **Magnoliaceae** | 4 | Magnolias, Cucumber Tree |
| **Juglandaceae** | 3 | Hickories |
| **Nyssaceae** | 3 | Tupelos |
| **Cupressaceae** | 2 | Red Cedar, Bald Cypress |
| **Other** | 8 | Various families |

---

## Key Excluded Species (Introduced)

The following species were automatically excluded due to WCVP "introduced" status:

| Scientific Name | Common Name | Origin | Occurrences |
|-----------------|-------------|--------|-------------|
| *Ailanthus altissima* | Tree of Heaven | China | 32,489 |
| *Paulownia tomentosa* | Princess Tree | China/Korea | 11,323 |
| *Albizia julibrissin* | Mimosa | Asia | 4,285 |
| *Morus alba* | White Mulberry | China | 3,651 |
| *Pyrus calleryana* | Callery Pear | China | 857 |

**Note**: Despite high occurrence counts, these species are correctly identified as introduced and excluded from recommendations.

---

## API Usage

```bash
# Get LEAF scores for this ecoregion
curl "https://treekipedia-api.silvi.earth/api/geospatial/leaf/score?eco_id=331"

# Get LEAF scores for a point in the ecoregion
curl "https://treekipedia-api.silvi.earth/api/geospatial/leaf/score?lat=35.5951&lng=-82.5515"

# Get LEAF scores for a polygon
curl -X POST "https://treekipedia-api.silvi.earth/api/geospatial/leaf/score" \
  -H "Content-Type: application/json" \
  -d '{"geometry": {"type": "Polygon", "coordinates": [...]}}'
```

---

## Notes

- All 50 top species are verified native to the Appalachian region via WCVP
- Occurrence data represents GBIF records aggregated into ~150m geohash tiles
- Species appearing in more tiles (higher distribution) score higher than those concentrated in fewer areas
- The native boost (×2.0) ensures native species outrank unknown-status species with similar occurrence patterns

---

**LEAF™** (Location-based Ecological Aptness Forecast) is a Treekipedia feature.
**Data Sources**: GBIF, WCVP (Kew Gardens)
