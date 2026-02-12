# Quick Start: GBIF Download for AlphaEarth

**Goal**: Download tree occurrence data from GBIF with accurate temporal data (2017-2024 only)

---

## Why GBIF? (Quick Recap)

❌ **Current CSV**: 96% from 2024 (dump artifact)
✅ **GBIF**: Real collection years, quality-filtered, perfect for AlphaEarth

---

## 🚀 3-Step Quick Start

### Step 1: Register GBIF Account (5 minutes)

1. Go to: https://www.gbif.org/user/profile
2. Click "Register"
3. Fill in:
   - Username
   - Email
   - Password
4. Verify email
5. ✅ Done!

### Step 2: Update Script (1 minute)

Edit `orchestrator/gbif_downloader.py`:

```python
# Line 15-17: Update these
GBIF_USER = 'your_username_here'
GBIF_PWD = 'your_password_here'
GBIF_EMAIL = 'your_email@example.com'
```

### Step 3: Run Download (10-60 minutes)

```bash
cd orchestrator

# Install dependencies (first time only)
pip install pygbif pandas pyarrow

# Run download
python3 gbif_downloader.py
```

**What happens**:
1. Matches 100 species to GBIF taxon keys (~2 min)
2. Requests download from GBIF (~1 min)
3. Waits for GBIF to prepare data (~10-60 min)
4. Downloads ZIP file (~2 min)
5. Parses and saves to Parquet (~1 min)

**Output**: `orchestrator/gbif_data/gbif_occurrences.parquet`

---

## 📊 Expected Results

**Filters Applied**:
- ✅ Years: **2017-2024 only** (matches AlphaEarth)
- ✅ Has coordinates (lat/lon)
- ✅ No geospatial issues
- ✅ Coordinate uncertainty ≤ 1000m

**Estimated Volume** (100 species):
- Records: 20,000 - 200,000
- Download size: 10-100 MB
- Species matched: ~95/100

**Year Distribution** (typical for plants 2017-2024):
```
2017:  8%   (~2K records)
2018: 10%   (~3K)
2019: 11%   (~3.5K)
2020: 13%   (~4K)
2021: 15%   (~5K)
2022: 17%   (~6K)
2023: 20%   (~7K)
2024: 26%   (~9K)  ← Recent citizen science boom
```

**Much better than 96% from 2024!**

---

## 🔍 Monitoring Download Progress

While waiting, you can check status:

1. **GBIF Portal**:
   - Login at: https://www.gbif.org
   - Go to: User menu → Downloads
   - See status: PREPARING → RUNNING → SUCCEEDED

2. **Console Output**:
```
⏳ Waiting for download to complete...
  Download key: 0123456-240321170329656
  Polling every 60s

  Status: RUNNING
  Records: 45,231
  Size: 15.3 MB

  Waiting 60s...
```

3. **Email Notification**:
   - GBIF will email when download is ready
   - Contains download link and DOI

---

## 📁 Output Files

```
orchestrator/gbif_data/
├── gbif_matches.json           # Species → GBIF key mapping
├── gbif_download.json          # Download metadata
├── 0123456-240321170329656.zip # Raw GBIF export (keep for citation)
└── gbif_occurrences.parquet    # Cleaned data ← USE THIS
```

**Parquet Schema**:
```
taxon_id     (string)   - Treekipedia ID
species      (string)   - Scientific name
latitude     (float64)  - Decimal degrees
longitude    (float64)  - Decimal degrees
year         (int64)    - Collection year (2017-2024)
gbif_id      (int64)    - GBIF occurrence ID
```

---

## ✅ Verify Success

Check the Parquet file:

```python
import pandas as pd

df = pd.read_parquet('orchestrator/gbif_data/gbif_occurrences.parquet')

print(f"Total records: {len(df):,}")
print(f"Species: {df['taxon_id'].nunique()}")
print(f"\nYear distribution:")
print(df['year'].value_counts().sort_index())
```

**Expected output**:
```
Total records: 45,231
Species: 95

Year distribution:
2017     3,621
2018     4,523
2019     4,986
2020     5,876
2021     6,785
2022     7,689
2023     9,032
2024    11,719
```

✅ **Success!** Real temporal distribution matching AlphaEarth window.

---

## 🔄 Next: Update Orchestrator

Once GBIF download completes, update `run_pilot.py` to use GBIF data:

```python
# Replace get_occurrences_for_species() function
def get_occurrences_for_species(taxon_id: str, max_points: int = 5000):
    """Fetch occurrences from GBIF Parquet."""
    df = pd.read_parquet('orchestrator/gbif_data/gbif_occurrences.parquet')

    # Filter to this species
    species_df = df[df['taxon_id'] == taxon_id].head(max_points)

    # Convert to dict format for GEE
    return species_df.rename(columns={'year': 'embedding_year'}).to_dict('records')
```

Then run:
```bash
python3 run_pilot.py  # Now uses GBIF data with real years!
```

---

## 🆘 Troubleshooting

### Error: "401 Unauthorized"
- Check GBIF username/password in script
- Verify account is activated (check email)

### Error: "Download failed"
- Too many species? Try with fewer (50 instead of 100)
- Check GBIF portal for error details

### Download taking too long?
- Normal for large requests (can take 1-2 hours)
- Safe to Ctrl+C and restart - script will resume
- Download is queued on GBIF servers, not lost

### Few records returned?
- Some species may be rare in GBIF
- 2017-2024 window is recent (historical specimens may be older)
- This is OK - use what's available

---

## 📞 Support

- **GBIF Help**: https://www.gbif.org/contact
- **pygbif Issues**: https://github.com/gbif/pygbif/issues
- **GBIF Data Blog**: https://data-blog.gbif.org

---

**Ready to run? Just 3 steps:**
1. Register GBIF account
2. Update credentials in `gbif_downloader.py`
3. Run `python3 gbif_downloader.py`

**Then you'll have accurate temporal data for AlphaEarth embeddings!** 🌍
