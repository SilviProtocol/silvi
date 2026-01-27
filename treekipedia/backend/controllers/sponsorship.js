const express = require('express');
const { ethers } = require('ethers');
const crypto = require('crypto');
const { v4: uuidv4 } = require('uuid');
const chains = require('../config/chains');
// NOTE: AI research now performed by Claude Code CLI via orchestrator (port 5003)
// Old Perplexity/OpenAI system removed Jan 2026

const SPONSORSHIP_AMOUNT = 3; // 3 USDC per species

// Webhook functionality removed - using direct transaction monitoring

// Map to store active monitoring tasks by sponsorship ID
const monitoringTasks = new Map();
const MONITORING_INTERVAL = 30000; // 30 seconds

// Set up providers for each chain
const providers = {};

// This function will be called when the module is loaded
const initializeProviders = () => {
  Object.entries(chains).forEach(([chainId, config]) => {
    if (config.rpcUrl) {
      try {
        // Use ethers v6 syntax for JsonRpcProvider
        providers[chainId] = new ethers.JsonRpcProvider(config.rpcUrl);
        console.log(`Initialized provider for ${config.name}`);
      } catch (error) {
        console.error(`Failed to initialize provider for ${config.name}:`, error);
      }
    }
  });
};

// Initialize providers on module load
initializeProviders();

module.exports = (pool) => {
  const router = express.Router();

  /**
   * POST /initiate
   * Initiate a sponsorship payment by registering intent
   */
  router.post('/initiate', async (req, res) => {
    try {
      console.log("Received initiate request with body:", req.body);
      const { taxon_id, wallet_address, chain } = req.body;
      
      console.log("Extracted values:", { taxon_id, wallet_address, chain });
      
      // Validate required fields
      if (!taxon_id || !wallet_address || !chain) {
        console.log("Missing required fields:", { 
          taxon_id_present: !!taxon_id, 
          wallet_address_present: !!wallet_address, 
          chain_present: !!chain 
        });
        return res.status(400).json({
          error: 'Missing required fields',
          required: ['taxon_id', 'wallet_address', 'chain'],
          received: req.body
        });
      }
      
      // Get chain configuration
      console.log(`Looking up chain config for: "${chain}"`);
      console.log("Available chains:", Object.keys(chains));
      
      // Try to map numeric chain ID to a chain key
      let chainKey = chain;
      if (/^\d+$/.test(chain)) {
        // This is a numeric chain ID, map it to a chain key
        const chainIdMapping = {
          '8453': 'base',
          '42220': 'celo',
          '10': 'optimism',
          '42161': 'arbitrum',
          '84532': 'base-sepolia',
          '44787': 'celo-alfajores',
          '11155420': 'optimism-sepolia',
          '421614': 'arbitrum-sepolia'
        };
        chainKey = chainIdMapping[chain] || chain;
        console.log(`Mapped numeric chain ID ${chain} to chain key: ${chainKey}`);
      }
      
      const chainConfig = chains[chainKey];
      console.log("Found chain config:", chainConfig ? "Yes" : "No");
      
      // Store both the original chain ID and the mapped chain key
      const originalChain = chain;
      const mappedChain = chainKey;
      
      if (!chainConfig) {
        return res.status(400).json({ 
          error: 'Invalid chain', 
          supported_chains: Object.keys(chains),
          received_chain: originalChain,
          mapped_chain: mappedChain
        });
      }
      
      // Validate treasury address exists
      const treasuryAddress = chainConfig.treasuryAddress;
      console.log(`Treasury address for chain ${mappedChain}:`, treasuryAddress);
      
      if (!treasuryAddress) {
        return res.status(500).json({ 
          error: 'Treasury address not configured for this chain',
          chain: mappedChain,
          chain_config: chainConfig
        });
      }
      
      // Check if species exists
      console.log(`Checking if species with taxon_id ${taxon_id} exists`);
      const speciesQuery = `
        SELECT taxon_id FROM species WHERE taxon_id = $1
      `;
      const speciesResult = await pool.query(speciesQuery, [taxon_id]);
      console.log(`Species query result for ${taxon_id}:`, speciesResult.rows);
      
      if (speciesResult.rows.length === 0) {
        // If exact match fails, try a diagnostic query to see if there are similar taxon_ids
        console.log(`Exact match for taxon_id ${taxon_id} failed, running diagnostic query`);
        const diagnosticQuery = `
          SELECT taxon_id FROM species WHERE taxon_id LIKE $1 LIMIT 5
        `;
        const diagnosticResult = await pool.query(diagnosticQuery, [`%${taxon_id}%`]);
        console.log(`Similar taxon_ids:`, diagnosticResult.rows);
        
        return res.status(404).json({ 
          error: 'Species not found', 
          taxon_id,
          similar_matches: diagnosticResult.rows 
        });
      }
      
      // Record the sponsorship intent in the database
      const client = await pool.connect();
      try {
        await client.query('BEGIN');
        
        // Insert sponsorship record with pending status - Let PostgreSQL generate the ID
        const sponsorshipInsert = `
          INSERT INTO sponsorships (
            wallet_address, chain, transaction_hash, total_amount, status
          ) VALUES ($1, $2, $3, $4, $5)
          RETURNING id
        `;
        const insertResult = await client.query(sponsorshipInsert, [
          wallet_address,
          mappedChain,
          null, // Transaction hash will be updated when payment is detected
          SPONSORSHIP_AMOUNT,
          'pending' // Status is pending until payment is detected
        ]);
        
        // Get the generated ID
        const sponsorshipId = insertResult.rows[0].id;
        
        // Insert sponsorship item record
        const itemInsert = `
          INSERT INTO sponsorship_items (
            sponsorship_id, taxon_id, amount, research_status
          ) VALUES ($1, $2, $3, $4)
        `;
        await client.query(itemInsert, [
          sponsorshipId,
          taxon_id,
          SPONSORSHIP_AMOUNT,
          'pending'
        ]);
        
        await client.query('COMMIT');
        
        // Return the sponsorship ID and treasury address to the frontend
        res.status(201).json({
          success: true,
          sponsorship_id: sponsorshipId,
          treasury_address: treasuryAddress,
          amount: SPONSORSHIP_AMOUNT,
          message: 'Sponsorship initiated. Please complete the USDC transfer.'
        });
      } catch (error) {
        await client.query('ROLLBACK');
        throw error;
      } finally {
        client.release();
      }
    } catch (error) {
      console.error('Error initiating sponsorship:', error);
      res.status(500).json({ error: 'Internal server error', details: error.message });
    }
  });

  /**
   * POST /report-transaction
   * Report a transaction hash for a previously initiated sponsorship
   */
  router.post('/report-transaction', async (req, res) => {
    try {
      const { sponsorship_id, transaction_hash, taxon_id, wallet_address, chain } = req.body;
      
      // Enhanced logging for debugging
      console.log(`Received report-transaction request:`, {
        sponsorship_id, 
        transaction_hash,
        taxon_id,
        wallet_address,
        chain
      });
      
      // Initialize variables first before any conditional logic
      let foundSponsorshipId = sponsorship_id;
      let foundWalletAddress = wallet_address;
      let foundChain = chain;
      let shouldProcessDirectly = false;
      
      // Map numeric chain ID to chain name if needed
      let chainKey = chain;
      if (chain && /^\d+$/.test(chain)) {
        // This is a numeric chain ID, map it to a chain key
        const chainIdMapping = {
          '8453': 'base',
          '42220': 'celo',
          '10': 'optimism',
          '42161': 'arbitrum',
          '84532': 'base-sepolia',
          '44787': 'celo-alfajores',
          '11155420': 'optimism-sepolia',
          '421614': 'arbitrum-sepolia'
        };
        chainKey = chainIdMapping[chain] || chain;
        console.log(`Mapped numeric chain ID ${chain} to chain key: ${chainKey}`);
        foundChain = chainKey; // Set the mapped chain to foundChain
      }
      
      // Validate required fields
      if (!transaction_hash) {
        return res.status(400).json({
          error: 'Missing transaction_hash',
          required: ['transaction_hash']
        });
      }
      
      // Try to update an existing sponsorship if we have an ID
      if (sponsorship_id) {
        try {
          console.log(`Attempting to update existing sponsorship ${sponsorship_id} with transaction hash ${transaction_hash}`);
          const updateQuery = `
            UPDATE sponsorships
            SET transaction_hash = $1, updated_at = CURRENT_TIMESTAMP
            WHERE id = $2
            RETURNING id, wallet_address, chain
          `;
          const result = await pool.query(updateQuery, [transaction_hash, sponsorship_id]);
          
          if (result.rows.length > 0) {
            console.log(`Successfully updated sponsorship ${sponsorship_id} with transaction hash ${transaction_hash}`);
            foundWalletAddress = result.rows[0].wallet_address;
            foundChain = result.rows[0].chain;
            console.log(`Retrieved wallet address ${foundWalletAddress} and chain ${foundChain} for sponsorship`);
          } else {
            console.log(`Sponsorship ID ${sponsorship_id} not found in database - will process directly`);
            shouldProcessDirectly = true;
          }
        } catch (dbError) {
          console.error(`Database error updating sponsorship:`, dbError);
          console.log(`Due to database error, will attempt to process transaction directly`);
          shouldProcessDirectly = true;
        }
      } else {
        console.log(`No sponsorship_id provided, will process transaction directly with provided information`);
        shouldProcessDirectly = true;
      }
      
      // If we can't find the sponsorship in the database but have enough information,
      // create a new record and process it directly
      if (shouldProcessDirectly && taxon_id && wallet_address && chain) {
        try {
          console.log(`Processing transaction directly for taxon_id ${taxon_id}`);
          
          // NOTE: We should let the sequence generate the ID
          console.log(`Creating new sponsorship record for direct processing`);
          
          const client = await pool.connect();
          try {
            await client.query('BEGIN');
            
            // Insert new sponsorship record - REMOVED id from the fields to let the sequence generate it
            const sponsorshipInsert = `
              INSERT INTO sponsorships (
                wallet_address, chain, transaction_hash, total_amount, status
              ) VALUES ($1, $2, $3, $4, $5)
              RETURNING id
            `;
            const insertResult = await client.query(sponsorshipInsert, [
              wallet_address,
              chain,
              transaction_hash,
              SPONSORSHIP_AMOUNT,
              'confirmed' // Mark as confirmed immediately
            ]);
            
            // Get the generated sponsorship ID from the insert result
            const newSponsorshipId = insertResult.rows[0].id;
            foundSponsorshipId = newSponsorshipId;
            console.log(`Generated sponsorship ID: ${newSponsorshipId}`);
            
            // Insert sponsorship item record
            const itemInsert = `
              INSERT INTO sponsorship_items (
                sponsorship_id, taxon_id, amount, research_status
              ) VALUES ($1, $2, $3, $4)
            `;
            await client.query(itemInsert, [
              newSponsorshipId,
              taxon_id,
              SPONSORSHIP_AMOUNT,
              'pending'
            ]);
            
            await client.query('COMMIT');
            console.log(`Created new sponsorship record ${newSponsorshipId} for transaction ${transaction_hash}`);
            
            // Get species info
            const speciesQuery = `
              SELECT taxon_id, species_scientific_name, common_name 
              FROM species WHERE taxon_id = $1
            `;
            const speciesResult = await pool.query(speciesQuery, [taxon_id]);
            
            if (speciesResult.rows.length > 0) {
              const species = speciesResult.rows[0];
              
              // Trigger research directly
              triggerResearch(
                pool,
                taxon_id,
                wallet_address,
                chain,
                transaction_hash,
                species.species_scientific_name,
                species.common_name
              ).catch(error => {
                console.error(`Background research error for taxon_id ${taxon_id}:`, error);
              });
            }
          } catch (dbError) {
            await client.query('ROLLBACK');
            console.error(`Database error creating sponsorship:`, dbError);
          } finally {
            client.release();
          }
        } catch (processingError) {
          console.error(`Error processing transaction directly:`, processingError);
        }
      } else if (foundSponsorshipId) {
        // Start monitoring the transaction
        console.log(`Starting monitoring for transaction ${transaction_hash}`);
        startTransactionMonitoring(transaction_hash, foundSponsorshipId, foundWalletAddress, foundChain, pool);
      }
      
      res.json({
        success: true,
        sponsorship_id: foundSponsorshipId,
        transaction_hash,
        status: 'processing',
        message: 'Transaction reported and being processed'
      });
    } catch (error) {
      console.error('Error reporting transaction:', error);
      res.status(500).json({ error: 'Internal server error', details: error.message });
    }
  });

  // Webhook route removed - using direct transaction monitoring instead

  /**
   * GET /sponsorships/transaction/:transaction_hash
   * Get details of a sponsorship by transaction hash
   */
  router.get('/transaction/:transaction_hash', async (req, res) => {
    try {
      const { transaction_hash } = req.params;
      console.log(`Fetching sponsorship details for transaction: ${transaction_hash}`);

      try {
        // Query the sponsorship status
        const query = `
          SELECT * FROM get_sponsorship_status($1)
        `;
        console.log(`Executing SQL query with transaction_hash: ${transaction_hash}`);
        const result = await pool.query(query, [transaction_hash]);
        console.log(`get_sponsorship_status result:`, result.rows);

        if (result.rows.length === 0) {
          console.log(`No sponsorship found for transaction hash: ${transaction_hash}`);
          return res.status(404).json({ 
            error: 'Sponsorship not found',
            transaction_hash
          });
        }

        // Get the species funded in this sponsorship
        const speciesQuery = `
          SELECT si.*, s.common_name, s.species_scientific_name
          FROM sponsorship_items si
          JOIN sponsorships sp ON si.sponsorship_id = sp.id
          JOIN species s ON si.taxon_id = s.taxon_id
          WHERE sp.transaction_hash = $1
        `;
        console.log(`Executing species query for transaction: ${transaction_hash}`);
        const speciesResult = await pool.query(speciesQuery, [transaction_hash]);
        console.log(`Species query result:`, speciesResult.rows);

        // Combine data for response
        const sponsorship = result.rows[0];
        sponsorship.species = speciesResult.rows;

        res.json(sponsorship);
      } catch (dbError) {
        console.error(`Database error when fetching sponsorship:`, dbError);
        
        // Handle the specific case where the function might not exist
        if (dbError.message && dbError.message.includes('function get_sponsorship_status')) {
          console.error("Function get_sponsorship_status may not exist or have the wrong parameters");
          
          // Attempt to get the sponsorship directly from the table as a fallback
          const fallbackQuery = `
            SELECT id, wallet_address, chain, transaction_hash, total_amount, payment_timestamp, status 
            FROM sponsorships 
            WHERE transaction_hash = $1
          `;
          console.log("Attempting fallback query:", fallbackQuery);
          const fallbackResult = await pool.query(fallbackQuery, [transaction_hash]);
          
          if (fallbackResult.rows.length > 0) {
            console.log("Found sponsorship via fallback:", fallbackResult.rows[0]);
            return res.json({
              transaction_hash: fallbackResult.rows[0].transaction_hash,
              status: fallbackResult.rows[0].status,
              total_amount: fallbackResult.rows[0].total_amount,
              wallet_address: fallbackResult.rows[0].wallet_address,
              chain: fallbackResult.rows[0].chain,
              payment_timestamp: fallbackResult.rows[0].payment_timestamp,
              species_count: 0,
              completed_count: 0,
              note: "Limited data due to database function error"
            });
          } else {
            return res.status(404).json({ 
              error: 'Sponsorship not found (fallback check)',
              transaction_hash
            });
          }
        }
        
        // If it's not a function error or fallback failed, rethrow
        throw dbError;
      }
    } catch (error) {
      console.error(`Error fetching sponsorship for transaction "${req.params.transaction_hash}":`, error);
      res.status(500).json({ 
        error: 'Internal server error', 
        message: error.message,
        stack: process.env.NODE_ENV === 'development' ? error.stack : undefined
      });
    }
  });

  /**
   * GET /sponsorships/user/:wallet_address
   * Get all sponsorships by a user
   */
  router.get('/user/:wallet_address', async (req, res) => {
    try {
      const { wallet_address } = req.params;
      const { limit = 20, offset = 0 } = req.query;

      // Query sponsorships for this wallet address
      const query = `
        SELECT * FROM sponsorship_summary
        WHERE wallet_address = $1
        ORDER BY payment_timestamp DESC
        LIMIT $2 OFFSET $3
      `;
      const result = await pool.query(query, [wallet_address, limit, offset]);

      res.json(result.rows);
    } catch (error) {
      console.error(`Error fetching sponsorships for wallet "${req.params.wallet_address}":`, error);
      res.status(500).json({ error: 'Internal server error' });
    }
  });

  /**
   * GET /sponsorships/species/:taxon_id
   * Get all sponsorships for a species
   */
  router.get('/species/:taxon_id', async (req, res) => {
    try {
      const { taxon_id } = req.params;
      const { limit = 20, offset = 0 } = req.query;

      // Check if species exists
      const speciesQuery = `
        SELECT taxon_id FROM species WHERE taxon_id = $1
      `;
      const speciesResult = await pool.query(speciesQuery, [taxon_id]);
      if (speciesResult.rows.length === 0) {
        return res.status(404).json({ error: 'Species not found' });
      }

      // Query sponsorships for this species
      const query = `
        SELECT 
          s.id, s.wallet_address, s.transaction_hash, s.chain, 
          s.total_amount, s.payment_timestamp, s.status,
          si.research_status, si.nft_token_id, si.ipfs_cid
        FROM sponsorship_items si
        JOIN sponsorships s ON si.sponsorship_id = s.id
        WHERE si.taxon_id = $1
        ORDER BY s.payment_timestamp DESC
        LIMIT $2 OFFSET $3
      `;
      const result = await pool.query(query, [taxon_id, limit, offset]);

      res.json(result.rows);
    } catch (error) {
      console.error(`Error fetching sponsorships for species "${req.params.taxon_id}":`, error);
      res.status(500).json({ error: 'Internal server error' });
    }
  });

  /**
   * Process a single species sponsorship
   */
  async function processSingleSponsorship(pool, chain, sender, taxon_id, amount, transaction_hash) {
    const client = await pool.connect();
    
    try {
      await client.query('BEGIN');
      
      // Verify the amount is correct (3 USDC per species)
      const amountInUSDC = Number(ethers.formatUnits(amount, 6)); // USDC has 6 decimals - formatUnits works the same in v6
      if (amountInUSDC !== SPONSORSHIP_AMOUNT) {
        throw new Error(`Invalid amount: expected ${SPONSORSHIP_AMOUNT} USDC, got ${amountInUSDC} USDC`);
      }

      // Check if this transaction has already been processed
      const existingCheck = `
        SELECT id FROM sponsorships WHERE transaction_hash = $1
      `;
      const existingResult = await client.query(existingCheck, [transaction_hash]);
      if (existingResult.rows.length > 0) {
        console.log(`Transaction ${transaction_hash} already processed, skipping`);
        await client.query('COMMIT');
        return;
      }

      // Validate taxon_id exists in species table
      const speciesQuery = `
        SELECT taxon_id, species_scientific_name, common_name FROM species WHERE taxon_id = $1
      `;
      const speciesResult = await client.query(speciesQuery, [taxon_id]);
      if (speciesResult.rows.length === 0) {
        throw new Error(`Species with taxon_id ${taxon_id} not found`);
      }
      
      const speciesData = speciesResult.rows[0];

      // Insert sponsorship record
      const sponsorshipInsert = `
        INSERT INTO sponsorships (
          wallet_address, chain, transaction_hash, total_amount, status, payment_timestamp
        ) VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP)
        RETURNING id
      `;
      const sponsorshipResult = await client.query(sponsorshipInsert, [
        sender,
        chain,
        transaction_hash,
        SPONSORSHIP_AMOUNT,
        'confirmed' // Payment has been confirmed on-chain
      ]);
      
      const sponsorshipId = sponsorshipResult.rows[0].id;

      // Insert sponsorship item record
      const itemInsert = `
        INSERT INTO sponsorship_items (
          sponsorship_id, taxon_id, amount, research_status
        ) VALUES ($1, $2, $3, $4)
        RETURNING id
      `;
      await client.query(itemInsert, [
        sponsorshipId,
        taxon_id,
        SPONSORSHIP_AMOUNT,
        'pending' // Research not started yet
      ]);

      await client.query('COMMIT');

      // Map chain ID to name if needed before triggering research
      // This is to ensure we use the correct chain key format (e.g., "base-sepolia" not "84532")
      let chainKey = chain;
      if (/^\d+$/.test(chain)) {
        // This is a numeric chain ID, map it to a chain key
        const chainIdMapping = {
          '8453': 'base',
          '42220': 'celo',
          '10': 'optimism',
          '42161': 'arbitrum',
          '84532': 'base-sepolia',
          '44787': 'celo-alfajores',
          '11155420': 'optimism-sepolia',
          '421614': 'arbitrum-sepolia'
        };
        chainKey = chainIdMapping[chain] || chain;
        console.log(`Mapped numeric chain ID ${chain} to chain key: ${chainKey}`);
      }
      
      // Trigger research process in the background
      triggerResearch(
        pool,
        taxon_id,
        sender,
        chainKey, // Use the mapped chain key
        transaction_hash,
        speciesData.species_scientific_name,
        speciesData.common_name
      ).catch(error => {
        console.error(`Background research error for taxon_id ${taxon_id}:`, error);
      });

    } catch (error) {
      await client.query('ROLLBACK');
      console.error('Error processing single sponsorship:', error);
      throw error;
    } finally {
      client.release();
    }
  }

  /**
   * Process a multi-species sponsorship
   */
  async function processMassSponsorship(pool, chain, sender, taxon_ids, totalAmount, transaction_hash) {
    const client = await pool.connect();
    
    try {
      await client.query('BEGIN');
      
      // Verify the total amount is correct (3 USDC per species)
      const totalAmountInUSDC = Number(ethers.formatUnits(totalAmount, 6)); // USDC has 6 decimals - formatUnits works the same in v6
      const expectedAmount = SPONSORSHIP_AMOUNT * taxon_ids.length;
      if (totalAmountInUSDC !== expectedAmount) {
        throw new Error(`Invalid amount: expected ${expectedAmount} USDC, got ${totalAmountInUSDC} USDC`);
      }

      // Check if this transaction has already been processed
      const existingCheck = `
        SELECT id FROM sponsorships WHERE transaction_hash = $1
      `;
      const existingResult = await client.query(existingCheck, [transaction_hash]);
      if (existingResult.rows.length > 0) {
        console.log(`Transaction ${transaction_hash} already processed, skipping`);
        await client.query('COMMIT');
        return;
      }

      // Insert sponsorship record
      const sponsorshipInsert = `
        INSERT INTO sponsorships (
          wallet_address, chain, transaction_hash, total_amount, status, payment_timestamp
        ) VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP)
        RETURNING id
      `;
      const sponsorshipResult = await client.query(sponsorshipInsert, [
        sender,
        chain,
        transaction_hash,
        totalAmountInUSDC,
        'confirmed' // Payment has been confirmed on-chain
      ]);
      
      const sponsorshipId = sponsorshipResult.rows[0].id;

      // Fetch all species data at once for efficiency
      const speciesQuery = `
        SELECT taxon_id, species_scientific_name, common_name FROM species WHERE taxon_id = ANY($1)
      `;
      const speciesResult = await client.query(speciesQuery, [taxon_ids]);
      
      // Create a map for quick lookups
      const speciesMap = {};
      for (const species of speciesResult.rows) {
        speciesMap[species.taxon_id] = species;
      }

      // Insert sponsorship items for each taxon_id
      for (const taxon_id of taxon_ids) {
        // Skip if species not found
        if (!speciesMap[taxon_id]) {
          console.warn(`Species with taxon_id ${taxon_id} not found, skipping`);
          continue;
        }

        const itemInsert = `
          INSERT INTO sponsorship_items (
            sponsorship_id, taxon_id, amount, research_status
          ) VALUES ($1, $2, $3, $4)
          RETURNING id
        `;
        await client.query(itemInsert, [
          sponsorshipId,
          taxon_id,
          SPONSORSHIP_AMOUNT,
          'pending' // Research not started yet
        ]);
      }

      await client.query('COMMIT');

      // Trigger research process for each species in the background
      for (const taxon_id of taxon_ids) {
        if (speciesMap[taxon_id]) {
          triggerResearch(
            pool,
            taxon_id,
            sender,
            chain,
            transaction_hash,
            speciesMap[taxon_id].species_scientific_name,
            speciesMap[taxon_id].common_name
          ).catch(error => {
            console.error(`Background research error for taxon_id ${taxon_id}:`, error);
          });
        }
      }

    } catch (error) {
      await client.query('ROLLBACK');
      console.error('Error processing mass sponsorship:', error);
      throw error;
    } finally {
      client.release();
    }
  }

  /**
   * Trigger the research process for a sponsored species
   */
  async function triggerResearch(pool, taxon_id, wallet_address, chain, transaction_hash, scientific_name, common_name) {
    try {
      console.log(`Triggering research for ${taxon_id}`);
      
      // Update sponsorship item status to 'researching'
      const updateQuery = `
        UPDATE sponsorship_items si
        SET research_status = 'researching'
        FROM sponsorships s
        WHERE si.sponsorship_id = s.id
        AND s.transaction_hash = $1
        AND si.taxon_id = $2
      `;
      await pool.query(updateQuery, [transaction_hash, taxon_id]);

      // Call the performResearch function directly from research controller
      console.log(`Calling performResearch directly for ${taxon_id}`);
      
      // Import the research controller to get the performResearch function
      const research = require('./research')(pool);
      
      // Call the standalone function directly with all necessary parameters
      const result = await research.performResearch(
        pool, 
        taxon_id, 
        wallet_address, 
        chain, 
        transaction_hash, 
        scientific_name, 
        common_name
      );
      
      // Create a mock response for backward compatibility
      const mockResponse = {
        statusCode: 201,
        data: result
      };

      // Check if research was successful
      if (mockResponse.statusCode !== 201) {
        throw new Error(`Research failed with status ${mockResponse.statusCode}: ${JSON.stringify(mockResponse.data)}`);
      }

      // Update sponsorship item with research results
      const completeQuery = `
        UPDATE sponsorship_items si
        SET 
          research_status = 'completed',
          nft_token_id = $3,
          ipfs_cid = $4
        FROM sponsorships s
        WHERE si.sponsorship_id = s.id
        AND s.transaction_hash = $1
        AND si.taxon_id = $2
      `;
      await pool.query(completeQuery, [
        transaction_hash,
        taxon_id,
        mockResponse.data.nft_details?.global_id || null,
        mockResponse.data.ipfs_cid || null
      ]);

      console.log(`Research completed for ${taxon_id}`);
      return mockResponse.data;
    } catch (error) {
      console.error(`Error triggering research for ${taxon_id}:`, error);
      
      // Update status to 'failed'
      const failureQuery = `
        UPDATE sponsorship_items si
        SET research_status = 'failed'
        FROM sponsorships s
        WHERE si.sponsorship_id = s.id
        AND s.transaction_hash = $1
        AND si.taxon_id = $2
      `;
      await pool.query(failureQuery, [transaction_hash, taxon_id]);
      
      throw error;
    }
  }

  /**
   * Start monitoring a transaction for confirmation
   */
  function startTransactionMonitoring(transactionHash, sponsorshipId, walletAddress, chain, pool) {
    // Skip if already monitoring this transaction
    if (monitoringTasks.has(transactionHash)) {
      console.log(`Already monitoring transaction ${transactionHash}, skipping duplicate request`);
      return;
    }
    
    console.log(`Starting monitoring for transaction ${transactionHash} on ${chain} for sponsorship ID ${sponsorshipId}`);
    
    // Get provider for the specified chain
    const provider = providers[chain];
    if (!provider) {
      console.error(`No provider available for chain ${chain} - unable to monitor transaction`);
      return;
    }
    
    // Get the chain configuration to get the USDC and treasury addresses
    const chainConfig = chains[chain];
    if (!chainConfig) {
      console.error(`No chain configuration found for ${chain} - unable to monitor transaction`);
      return;
    }
    
    const usdcAddress = chainConfig.usdcAddress;
    const treasuryAddress = chainConfig.treasuryAddress;
    
    if (!usdcAddress || !treasuryAddress) {
      console.error(`Missing USDC (${usdcAddress}) or Treasury (${treasuryAddress}) address for chain ${chain}`);
      return;
    }
    
    console.log(`Monitoring transfer of USDC (${usdcAddress}) to treasury (${treasuryAddress}) on ${chain}`);
    
    // Function to check transaction status
    const checkTransaction = async () => {
      try {
        // Log each checking attempt
        console.log(`Checking transaction ${transactionHash} status...`);
        
        // Get transaction receipt
        const receipt = await provider.getTransactionReceipt(transactionHash);
        console.log(`Transaction receipt status:`, receipt ? receipt.status : 'pending');
        
        if (receipt && receipt.status === 1) {
          // Transaction successful - verify it's a USDC transfer
          console.log(`Transaction ${transactionHash} confirmed on chain, retrieving details...`);
          const transaction = await provider.getTransaction(transactionHash);
          
          if (transaction) {
            console.log(`Transaction details retrieved, verifying it's a USDC transfer...`);
            // Create an ERC20 interface to parse the transaction data
            // ethers v6 uses Interface directly instead of utils.Interface
            const erc20Interface = new ethers.Interface([
              'function transfer(address to, uint256 amount) returns (bool)'
            ]);
            
            try {
              // Try to decode the transaction data
              const decodedData = erc20Interface.parseTransaction({ data: transaction.data, value: transaction.value });
              console.log(`Transaction decoded: function=${decodedData.name}, to=${decodedData.args[0]}`);
              
              // Check if it's a transfer to our treasury address
              const toAddressMatches = decodedData.name === 'transfer' && 
                decodedData.args[0].toLowerCase() === treasuryAddress.toLowerCase();
              
              console.log(`Treasury address match: ${toAddressMatches}`);
              
              if (toAddressMatches) {
                // Verify amount is 0.01 USDC (account for 6 decimals)
                // In ethers v6, formatUnits is a direct export, not under utils
                const amount = Number(ethers.formatUnits(decodedData.args[1], 6));
                console.log(`Transaction amount: ${amount} USDC`);
                
                if (Math.abs(amount - SPONSORSHIP_AMOUNT) < 0.15) { // Small tolerance for rounding errors (0.15 is 5% of 3)
                  console.log(`Payment verified: ${amount} USDC to ${treasuryAddress}`);
                  
                  // Confirm the sponsorship in the database
                  console.log(`Confirming sponsorship ${sponsorshipId} in database...`);
                  await confirmSponsorship(pool, sponsorshipId, transactionHash);
                  
                  // Stop monitoring
                  clearTimeout(monitoringTasks.get(transactionHash));
                  monitoringTasks.delete(transactionHash);
                  console.log(`Successfully confirmed sponsorship ${sponsorshipId} and initiated research`);
                  return;
                } else {
                  console.log(`Invalid amount: expected ${SPONSORSHIP_AMOUNT}, got ${amount}`);
                }
              } else {
                console.log('Transaction is not a USDC transfer to our treasury address');
              }
            } catch (decodeError) {
              console.error('Error decoding transaction:', decodeError);
              console.log('Transaction data:', transaction.data);
            }
          }
        } else if (receipt && receipt.status === 0) {
          // Transaction failed - update status
          console.log(`Transaction ${transactionHash} failed on chain, updating sponsorship status to failed`);
          await updateSponsorshipStatus(pool, sponsorshipId, 'failed');
          
          // Stop monitoring
          clearTimeout(monitoringTasks.get(transactionHash));
          monitoringTasks.delete(transactionHash);
          return;
        } else {
          console.log(`Transaction ${transactionHash} is still pending, waiting for confirmation`);
        }
        
        // Continue monitoring if no definitive result yet
        console.log(`Scheduling next check for transaction ${transactionHash} in ${MONITORING_INTERVAL/1000} seconds`);
        
        // Schedule next check
        const timeout = setTimeout(checkTransaction, MONITORING_INTERVAL);
        monitoringTasks.set(transactionHash, timeout);
      } catch (error) {
        console.error(`Error checking transaction ${transactionHash}:`, error);
        
        // Schedule retry
        console.log(`Scheduling retry for transaction ${transactionHash} in ${MONITORING_INTERVAL/1000} seconds due to error`);
        const timeout = setTimeout(checkTransaction, MONITORING_INTERVAL);
        monitoringTasks.set(transactionHash, timeout);
      }
    };
    
    // Start the first check
    console.log(`Starting first check for transaction ${transactionHash} in 5 seconds`);
    const timeout = setTimeout(checkTransaction, 5000); // Start first check sooner (5 seconds)
    monitoringTasks.set(transactionHash, timeout);
  }
  
  /**
   * Confirm a sponsorship and update status in database
   */
  async function confirmSponsorship(pool, sponsorshipId, transactionHash) {
    const client = await pool.connect();
    
    try {
      await client.query('BEGIN');
      
      // Update sponsorship status
      const updateQuery = `
        UPDATE sponsorships
        SET status = 'confirmed', payment_timestamp = CURRENT_TIMESTAMP
        WHERE id = $1
        RETURNING id, wallet_address, chain, total_amount
      `;
      const result = await client.query(updateQuery, [sponsorshipId]);
      
      if (result.rows.length === 0) {
        await client.query('ROLLBACK');
        throw new Error(`Sponsorship not found: ${sponsorshipId}`);
      }
      
      const sponsorship = result.rows[0];
      
      // Get sponsored species
      const itemsQuery = `
        SELECT si.taxon_id, s.species_scientific_name, s.common_name 
        FROM sponsorship_items si
        JOIN species s ON si.taxon_id = s.taxon_id
        WHERE si.sponsorship_id = $1
      `;
      const itemsResult = await client.query(itemsQuery, [sponsorshipId]);
      
      await client.query('COMMIT');
      
      // Map chain ID to name if needed before triggering research
      let chainKey = sponsorship.chain;
      if (/^\d+$/.test(sponsorship.chain)) {
        // This is a numeric chain ID, map it to a chain key
        const chainIdMapping = {
          '8453': 'base',
          '42220': 'celo',
          '10': 'optimism',
          '42161': 'arbitrum',
          '84532': 'base-sepolia',
          '44787': 'celo-alfajores',
          '11155420': 'optimism-sepolia',
          '421614': 'arbitrum-sepolia'
        };
        chainKey = chainIdMapping[sponsorship.chain] || sponsorship.chain;
        console.log(`Mapped numeric chain ID ${sponsorship.chain} to chain key: ${chainKey}`);
      }
      
      // Trigger research process for each species
      for (const item of itemsResult.rows) {
        // Trigger research
        triggerResearch(
          pool,
          item.taxon_id,
          sponsorship.wallet_address,
          chainKey, // Use the mapped chain key
          transactionHash,
          item.species_scientific_name,
          item.common_name
        ).catch(error => {
          console.error(`Background research error for taxon_id ${item.taxon_id}:`, error);
        });
      }
      
      return true;
    } catch (error) {
      await client.query('ROLLBACK');
      console.error('Error confirming sponsorship:', error);
      throw error;
    } finally {
      client.release();
    }
  }
  
  /**
   * Update sponsorship status
   */
  async function updateSponsorshipStatus(pool, sponsorshipId, status) {
    const updateQuery = `
      UPDATE sponsorships
      SET status = $1, updated_at = CURRENT_TIMESTAMP
      WHERE id = $2
    `;
    await pool.query(updateQuery, [status, sponsorshipId]);
  }

  return router;
};