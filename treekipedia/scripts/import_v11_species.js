#!/usr/bin/env node
/**
 * Treekipedia V11 Species Data Import Script
 *
 * Imports species data from V11 CSV file (1.3 GB)
 * - Updates existing species by taxon_full (matching key)
 * - Preserves NFT research data (ipfs_cid, researched flag)
 * - Handles new species with INSERT
 * - Maps CSV column names to database column names (lowercase)
 * - Streams CSV to handle large file size
 *
 * Usage:
 *   node import_v11_species.js <csv_file_path> [--dry-run] [--batch-size=1000]
 *
 * Key differences from V10:
 * - V11 has 133 columns (V10 had 130)
 * - New columns: wcvp_native, wcvp_introduced, climate data, GloBI
 * - Uses taxon_full as primary matching key
 */

const fs = require('fs');
const path = require('path');
const { Pool } = require('pg');
const csv = require('csv-parser');
const { Transform } = require('stream');
require('dotenv').config({ path: path.join(__dirname, '../backend/.env') });

// Parse command line arguments
const args = process.argv.slice(2);
const csvFilePath = args.find(arg => !arg.startsWith('--')) ||
  path.join(__dirname, '../../Treekipedia_V11_Native_introduced_December_09d (1).csv');
const isDryRun = args.includes('--dry-run');
const batchSizeArg = args.find(arg => arg.startsWith('--batch-size='));
const BATCH_SIZE = batchSizeArg ? parseInt(batchSizeArg.split('=')[1]) : 1000;
const LOG_INTERVAL = 5000;

// Database connection
const pool = new Pool({
  connectionString: process.env.DATABASE_URL || 'postgresql://localhost:5432/treekipedia',
  ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false
});

// Track statistics
const stats = {
  totalRows: 0,
  updatedSpecies: 0,
  newSpecies: 0,
  skippedRows: 0,
  errors: 0,
  preservedNFTData: 0,
  newSpeciesList: [],
  errorList: [],
  wcvpNativeCount: 0,
  wcvpIntroducedCount: 0,
  climateDataCount: 0,
  globiDataCount: 0
};

// Cache for species with NFT data (to preserve their ipfs_cid and researched status)
let nftSpeciesCache = null;

/**
 * Load list of species that have NFT data (must be preserved)
 */
async function loadNFTSpecies() {
  const query = `
    SELECT DISTINCT taxon_id
    FROM contreebution_nfts
  `;
  try {
    const result = await pool.query(query);
    nftSpeciesCache = new Set(result.rows.map(r => r.taxon_id));
    console.log(`📋 Loaded ${nftSpeciesCache.size} species with NFT data to preserve`);
    return nftSpeciesCache;
  } catch (error) {
    console.error('Error loading NFT species:', error.message);
    nftSpeciesCache = new Set(); // Empty set if table doesn't exist
  }
}

/**
 * Map CSV column names to database column names
 * V11 uses mixed case, database uses lowercase
 */
function mapColumnName(csvColumnName) {
  // Convert to lowercase for database consistency
  const lowerName = csvColumnName.toLowerCase();

  // Special mappings for known column name differences
  const mappings = {
    // V11 uses taxon_id_new as the primary taxon_id
    'taxon_id_new': 'taxon_id',
    // Commercial species column mapping
    'comercialspecies': 'comercialspecies',
    // Climate fields - ensure lowercase
    'climate_type_koppengeiger': 'climate_type_koppengeiger',
    'annual_temperature_range_c': 'annual_temperature_range_c',
    'annual_precipitation_mm': 'annual_precipitation_mm',
    'wettest_month_precipitation_mm': 'wettest_month_precipitation_mm',
    'driest_month_precipitation_mm': 'driest_month_precipitation_mm',
    'precipitation_seasonality_cv': 'precipitation_seasonality_cv',
    'wettest_quarter_precipitation_mm': 'wettest_quarter_precipitation_mm',
    'driest_quarter_precipitation_mm': 'driest_quarter_precipitation_mm',
    // GloBI fields
    'globi_pollinatedby': 'globi_pollinatedby',
    'globi_eatenby': 'globi_eatenby',
    'globi_flowersvisitedby': 'globi_flowersvisitedby',
    'globi_hasparasite': 'globi_hasparasite',
    'globi_haspathogen': 'globi_haspathogen',
    'globi_hasdispersalvector': 'globi_hasdispersalvector',
    'globi_preyeduponby': 'globi_preyeduponby',
    'globi_hasparasitoid': 'globi_hasparasitoid',
    // Other fields
    'sbtn_landcover': 'sbtn_landcover',
    'present_intact_forest': 'present_intact_forest',
    'vegetationtype': 'vegetationtype',
    // WCVP fields (critical for LEAF)
    'wcvp_native': 'wcvp_native',
    'wcvp_introduced': 'wcvp_introduced',
    // Soil/pH/OC fields
    'soil_texture_all': 'soil_texture_all',
    'soil_texture_dominant': 'soil_texture_dominant',
    'soil_texture_prefered': 'soil_texture_prefered',
    'soil_texture_tolerated': 'soil_texture_tolerated',
    'ph_all': 'ph_all',
    'ph_dominant': 'ph_dominant',
    'ph_prefered': 'ph_prefered',
    'ph_tolerated': 'ph_tolerated',
    'oc_all': 'oc_all',
    'oc_dominant': 'oc_dominant',
    'oc_prefered': 'oc_prefered',
    'oc_tolerated': 'oc_tolerated'
  };

  return mappings[lowerName] || lowerName;
}

/**
 * Get columns that exist in the database
 */
async function getDatabaseColumns() {
  const query = `
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'species'
  `;
  const result = await pool.query(query);
  return new Set(result.rows.map(r => r.column_name));
}

/**
 * Build UPDATE query for a species
 */
function buildUpdateQuery(speciesData, oldTaxonId, dbColumns) {
  const hasNFT = nftSpeciesCache.has(oldTaxonId);

  // Get all mapped columns that exist in database, except matching key
  const columns = Object.keys(speciesData).filter(col =>
    col !== 'taxon_full' &&
    col !== 'taxon_id' && // Don't update taxon_id
    dbColumns.has(col)
  );

  // Filter out ipfs_cid and researched if this species has NFT data
  const columnsToUpdate = columns.filter(col => {
    if (hasNFT && (col === 'ipfs_cid' || col === 'researched')) {
      return false; // Skip these columns to preserve NFT data
    }
    return true;
  });

  if (columnsToUpdate.length === 0) {
    return null;
  }

  // Build SET clause
  const setClause = columnsToUpdate
    .map((col, idx) => `${col} = $${idx + 2}`)
    .join(', ');

  // Build values array - match on taxon_full
  const values = [speciesData.taxon_full, ...columnsToUpdate.map(col => speciesData[col])];

  const query = `
    UPDATE species
    SET ${setClause},
        updated_at = NOW()
    WHERE taxon_full = $1
  `;

  return { query, values, hasNFT, oldTaxonId };
}

/**
 * Build INSERT query for new species
 */
function buildInsertQuery(speciesData, dbColumns) {
  // Only include columns that exist in database
  const columns = Object.keys(speciesData).filter(col => dbColumns.has(col));
  const placeholders = columns.map((_, idx) => `$${idx + 1}`).join(', ');
  const values = columns.map(col => speciesData[col]);

  const query = `
    INSERT INTO species (${columns.join(', ')}, created_at, updated_at)
    VALUES (${placeholders}, NOW(), NOW())
  `;

  return { query, values };
}

/**
 * Process a batch of species records
 */
async function processBatch(batch, dbColumns) {
  const client = await pool.connect();

  try {
    await client.query('BEGIN');

    for (const speciesData of batch) {
      try {
        // Match on taxon_full, get the old taxon_id for NFT checking
        const checkResult = await client.query(
          'SELECT taxon_id FROM species WHERE taxon_full = $1',
          [speciesData.taxon_full]
        );

        // Track V11 data population
        if (speciesData.wcvp_native) stats.wcvpNativeCount++;
        if (speciesData.wcvp_introduced) stats.wcvpIntroducedCount++;
        if (speciesData.climate_type_koppengeiger) stats.climateDataCount++;
        if (speciesData.globi_eatenby || speciesData.globi_pollinatedby) stats.globiDataCount++;

        if (checkResult.rows.length > 0) {
          // Species exists - UPDATE
          const oldTaxonId = checkResult.rows[0].taxon_id;
          const updateData = buildUpdateQuery(speciesData, oldTaxonId, dbColumns);

          if (updateData && !isDryRun) {
            await client.query(updateData.query, updateData.values);
          }

          stats.updatedSpecies++;
          if (updateData?.hasNFT) {
            stats.preservedNFTData++;
          }
        } else {
          // New species - INSERT
          const { query, values } = buildInsertQuery(speciesData, dbColumns);

          if (!isDryRun) {
            await client.query(query, values);
          }

          stats.newSpecies++;
          if (stats.newSpeciesList.length < 100) {
            stats.newSpeciesList.push(speciesData.taxon_full);
          }
        }
      } catch (error) {
        stats.errors++;
        if (stats.errorList.length < 50) {
          stats.errorList.push({
            taxon_full: speciesData.taxon_full,
            error: error.message
          });
        }
        // Log first 5 errors in detail
        if (stats.errors <= 5) {
          console.error(`Error processing ${speciesData.taxon_full}:`, error.message);
        }
      }
    }

    await client.query('COMMIT');
  } catch (error) {
    await client.query('ROLLBACK');
    console.error('Batch processing error:', error.message);
    throw error;
  } finally {
    client.release();
  }
}

/**
 * Main import function
 */
async function importV11CSV() {
  console.log('🌳 Treekipedia V11 Species Import');
  console.log('=====================================');
  console.log(`CSV File: ${csvFilePath}`);
  console.log(`Batch Size: ${BATCH_SIZE}`);
  console.log(`Dry Run: ${isDryRun ? 'YES (no changes will be made)' : 'NO (database will be updated)'}`);
  console.log('');

  // Check file exists
  if (!fs.existsSync(csvFilePath)) {
    console.error(`❌ File not found: ${csvFilePath}`);
    process.exit(1);
  }

  const fileStats = fs.statSync(csvFilePath);
  console.log(`📁 File size: ${(fileStats.size / 1024 / 1024 / 1024).toFixed(2)} GB`);
  console.log('');

  // Load database columns
  const dbColumns = await getDatabaseColumns();
  console.log(`📊 Database has ${dbColumns.size} columns in species table`);

  // Load NFT species to preserve their data
  await loadNFTSpecies();
  console.log('');

  const startTime = Date.now();
  let batch = [];

  return new Promise((resolve, reject) => {
    // Create transform stream for batch processing
    const batchProcessor = new Transform({
      objectMode: true,
      transform(row, encoding, callback) {
        stats.totalRows++;

        // Skip rows with missing taxon_full
        if (!row.taxon_full || row.taxon_full.trim() === '') {
          stats.skippedRows++;
          if (stats.skippedRows <= 5) {
            console.warn(`Row ${stats.totalRows}: Missing taxon_full, skipping`);
          }
          callback();
          return;
        }

        // Map CSV columns to database columns (lowercase)
        const mappedRow = {};
        for (const [csvCol, value] of Object.entries(row)) {
          const dbCol = mapColumnName(csvCol);

          // Skip the old taxon_id column (we use taxon_id_new -> taxon_id)
          if (csvCol.toLowerCase() === 'taxon_id' && csvCol !== 'taxon_id_new') {
            continue;
          }

          // Convert empty strings to null
          mappedRow[dbCol] = value === '' ? null : value;
        }

        batch.push(mappedRow);

        // Process batch when full
        if (batch.length >= BATCH_SIZE) {
          const currentBatch = [...batch];
          batch = [];

          processBatch(currentBatch, dbColumns)
            .then(() => callback())
            .catch(err => callback(err));
        } else {
          callback();
        }

        // Log progress
        if (stats.totalRows % LOG_INTERVAL === 0) {
          const elapsed = (Date.now() - startTime) / 1000;
          const rate = stats.totalRows / elapsed;
          const eta = ((67750 - stats.totalRows) / rate / 60).toFixed(1);
          console.log(`📊 Progress: ${stats.totalRows.toLocaleString()} rows | ` +
                     `${stats.updatedSpecies.toLocaleString()} updated | ` +
                     `${stats.newSpecies.toLocaleString()} new | ` +
                     `${rate.toFixed(0)} rows/sec | ` +
                     `ETA: ${eta} min`);
        }
      },

      async flush(callback) {
        // Process remaining batch
        if (batch.length > 0) {
          try {
            await processBatch(batch, dbColumns);
            callback();
          } catch (err) {
            callback(err);
          }
        } else {
          callback();
        }
      }
    });

    // Start streaming CSV
    fs.createReadStream(csvFilePath)
      .pipe(csv())
      .pipe(batchProcessor)
      .on('finish', async () => {
        const elapsed = (Date.now() - startTime) / 1000;

        console.log('');
        console.log('✅ Import Complete!');
        console.log('=====================================');
        console.log(`⏱️  Duration: ${(elapsed / 60).toFixed(2)} minutes`);
        console.log(`📊 Total rows processed: ${stats.totalRows.toLocaleString()}`);
        console.log(`✏️  Species updated: ${stats.updatedSpecies.toLocaleString()}`);
        console.log(`➕ New species added: ${stats.newSpecies.toLocaleString()}`);
        console.log(`🔒 NFT data preserved: ${stats.preservedNFTData.toLocaleString()} species`);
        console.log(`⏭️  Rows skipped: ${stats.skippedRows.toLocaleString()}`);
        console.log(`❌ Errors: ${stats.errors.toLocaleString()}`);
        console.log('');
        console.log('📈 V11 Data Population:');
        console.log(`   WCVP Native: ${stats.wcvpNativeCount.toLocaleString()} species`);
        console.log(`   WCVP Introduced: ${stats.wcvpIntroducedCount.toLocaleString()} species`);
        console.log(`   Climate Data: ${stats.climateDataCount.toLocaleString()} species`);
        console.log(`   GloBI Interactions: ${stats.globiDataCount.toLocaleString()} species`);

        if (stats.newSpecies > 0 && stats.newSpecies <= 20) {
          console.log('');
          console.log('New species added:');
          stats.newSpeciesList.slice(0, 20).forEach(tf => console.log(`  - ${tf}`));
        }

        if (stats.errors > 0 && stats.errors <= 20) {
          console.log('');
          console.log('Errors encountered:');
          stats.errorList.slice(0, 20).forEach(err => console.log(`  - ${err.taxon_full}: ${err.error}`));
        }

        if (isDryRun) {
          console.log('');
          console.log('🔵 DRY RUN - No changes were made to the database');
        }

        await pool.end();
        resolve();
      })
      .on('error', (error) => {
        console.error('❌ CSV parsing error:', error.message);
        reject(error);
      });
  });
}

// Run the import
importV11CSV()
  .then(() => {
    console.log('');
    console.log('🎉 Import script finished successfully');
    process.exit(0);
  })
  .catch((error) => {
    console.error('');
    console.error('💥 Import script failed:', error.message);
    process.exit(1);
  });
