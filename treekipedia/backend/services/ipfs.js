/**
 * IPFS Services - Lighthouse Storage
 *
 * STATUS: DISABLED (Jan 2026)
 *
 * These functions are preserved for future use but are not currently called.
 * Research metadata was previously stored on IPFS for NFT minting.
 * Research is now performed by Claude Code CLI and stored in PostgreSQL insights table.
 *
 * To re-enable:
 * 1. Set LIGHTHOUSE_API_KEY in .env
 * 2. Import uploadToIPFS in research controller
 * 3. Call after research completes (before NFT minting)
 */

// Import required modules
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '../../.env') });
const axios = require('axios');
const FormData = require('form-data');

// Lighthouse API key from environment variables
const LIGHTHOUSE_API_KEY = process.env.LIGHTHOUSE_API_KEY;

/**
 * Uploads data to IPFS via Lighthouse
 * @param {Object|string} data - The data to upload to IPFS (object or JSON string)
 * @returns {Promise<string>} - CID (Content Identifier) of the uploaded data
 */
async function uploadToIPFS(data) {
  try {
    console.log('Uploading data to IPFS via Lighthouse');
    
    // Parse data if it's a string (JSON)
    let dataObj;
    if (typeof data === 'string') {
      try {
        dataObj = JSON.parse(data);
      } catch (e) {
        console.error('Error parsing JSON data:', e.message);
        throw new Error('IPFS upload failed: Invalid JSON data');
      }
    } else {
      dataObj = data;
    }
    
    // Log sample of the data to upload, but skip validation
    console.log('Data sample for IPFS upload:', JSON.stringify(dataObj).substring(0, 100) + '...');
    
    // Keep original data structure - skip reformatting and validation
    // Simply use the parsed data as is without enforcing specific field names
    const jsonData = JSON.stringify(dataObj, null, 2);
    
    // Log the data size for debugging
    console.log(`Data size for IPFS upload: ${jsonData.length} bytes`);
    
    // Create FormData object
    const formData = new FormData();
    
    // Append file to FormData
    formData.append(
      'file', 
      Buffer.from(jsonData), 
      {
        filename: `treekipedia_${dataObj.taxon_id || 'metadata'}_${Date.now()}.json`,
        contentType: 'application/json',
      }
    );
    
    // Set Lighthouse API endpoint and headers
    const url = 'https://node.lighthouse.storage/api/v0/add';
    const headers = {
      'Authorization': `Bearer ${LIGHTHOUSE_API_KEY}`,
      ...formData.getHeaders()
    };
    
    // Make POST request to Lighthouse API
    const response = await axios.post(url, formData, { headers });
    
    // Extract CID from response
    const cid = response.data.Hash;
    console.log(`Data uploaded to IPFS with CID: ${cid}`);
    
    // Add detailed logging to help diagnose issues
    console.log(`DEBUG: IPFS CID format check: starts with 'bafk'=${cid.startsWith('bafk')}`);
    console.log(`DEBUG: IPFS CID length: ${cid.length} characters`);
    
    // Verify the CID is valid by attempting to construct a gateway URL
    const gatewayUrl = `https://gateway.lighthouse.storage/ipfs/${cid}`;
    console.log(`DEBUG: IPFS gateway URL: ${gatewayUrl}`);
    
    // Skip validation of critical fields - just log basic info
    console.log(`DEBUG: IPFS upload complete with data size ${jsonData.length} bytes`);
    
    return cid;
  } catch (error) {
    console.error('Error uploading to IPFS:', error);
    throw new Error(`IPFS upload failed: ${error.message}`);
  }
}

/**
 * Retrieves data from IPFS via Lighthouse
 * @param {string} cid - CID (Content Identifier) of the data to retrieve
 * @returns {Promise<Object>} - Retrieved data as JSON object
 */
async function getFromIPFS(cid) {
  try {
    console.log(`Retrieving data from IPFS with CID: ${cid}`);
    
    // Set IPFS gateway URL
    const gatewayUrl = `https://gateway.lighthouse.storage/ipfs/${cid}`;
    
    // Make GET request to IPFS gateway
    const response = await axios.get(gatewayUrl);
    
    // Return data
    return response.data;
  } catch (error) {
    console.error('Error retrieving from IPFS:', error);
    throw new Error(`IPFS retrieval failed: ${error.message}`);
  }
}

/**
 * Exports the entire species database to IPFS as CSV
 * @param {Object} pool - PostgreSQL connection pool
 * @returns {Promise<string>} - CID of the exported CSV
 */
async function exportSpeciesToIPFS(pool) {
  try {
    console.log('Exporting species database to IPFS');
    
    // Query all species data
    const query = 'SELECT * FROM species';
    const result = await pool.query(query);
    
    // Convert to CSV format
    const { parse } = require('json2csv');
    const fields = Object.keys(result.rows[0]);
    const opts = { fields };
    const csv = parse(result.rows, opts);
    
    // Create FormData object
    const formData = new FormData();
    
    // Generate version and timestamp
    const timestamp = new Date().toISOString().split('T')[0]; // YYYY-MM-DD
    const version = '1.0';
    
    // Append file to FormData
    formData.append(
      'file', 
      Buffer.from(csv), 
      {
        filename: `treekipedia_data_v${version}_${timestamp}.csv`,
        contentType: 'text/csv',
      }
    );
    
    // Set Lighthouse API endpoint and headers
    const url = 'https://node.lighthouse.storage/api/v0/add';
    const headers = {
      'Authorization': `Bearer ${LIGHTHOUSE_API_KEY}`,
      ...formData.getHeaders()
    };
    
    // Make POST request to Lighthouse API
    const response = await axios.post(url, formData, { headers });
    
    // Extract CID from response
    const cid = response.data.Hash;
    console.log(`Database exported to IPFS with CID: ${cid}`);
    
    return cid;
  } catch (error) {
    console.error('Error exporting database to IPFS:', error);
    throw new Error(`Database export failed: ${error.message}`);
  }
}

module.exports = {
  uploadToIPFS,
  getFromIPFS,
  exportSpeciesToIPFS
};