/**
 * Blockchain Services - EAS Attestations and NFT Minting
 *
 * STATUS: DISABLED (Jan 2026)
 *
 * These functions are preserved for future use but are not currently called.
 * Research is now performed by Claude Code CLI via queue-based workflow.
 *
 * To re-enable:
 * 1. Set PRIVATE_KEY in .env
 * 2. Import createAttestation/mintNFT in research controller
 * 3. Call after research completes
 */

// Import required modules
const path = require('path');
require('dotenv').config({ path: path.resolve(__dirname, '../../.env') });
const { ethers } = require('ethers');
const chains = require('../config/chains');

// Private key from environment variables (used for signing transactions)
const PRIVATE_KEY = process.env.PRIVATE_KEY;

/**
 * Creates an attestation on the Ethereum Attestation Service (EAS)
 * @param {string} chain - Chain for NFT minting ('base', 'celo', 'optimism', 'arbitrum')
 * @param {Object} data - Attestation data to be stored
 * @returns {Promise<string>} - UID of the created attestation
 */
async function createAttestation(chain, data) {
  try {
    // IMPORTANT: Always use Celo for EAS attestations regardless of which chain user is connected to
    const attestationChain = 'celo';
    
    console.log(`Creating attestation on Celo (fixed EAS chain) for ${data.species} - Original request chain: ${chain}`);
    
    // Get Celo chain configuration for attestation
    const celoConfig = chains[attestationChain];
    if (!celoConfig) {
      throw new Error(`Missing configuration for Celo chain which is required for attestations`);
    }
    
    // Check for missing critical configuration
    if (!celoConfig.rpcUrl) {
      throw new Error(`Missing RPC URL for Celo. Please set CELO_RPC_URL in .env file.`);
    }
    
    if (!celoConfig.easContractAddress) {
      throw new Error(`Missing EAS contract address for Celo. Please set CELO_EAS_CONTRACT_ADDRESS in .env file.`);
    }
    
    if (!celoConfig.easSchemaId) {
      throw new Error(`Missing EAS schema ID for Celo. Please set CELO_EAS_SCHEMA_ID in .env file.`);
    }
    
    // Set up provider and signer for Celo (not the user's connected chain)
    const provider = new ethers.JsonRpcProvider(celoConfig.rpcUrl);
    const signer = new ethers.Wallet(PRIVATE_KEY, provider);
    
    // Initialize EAS contract
    const easContractABIFile = require('../config/abis/eas.json');
    // Extract the actual ABI array from the file
    const easContractABI = easContractABIFile.abi;
    // Ensure the address is checksummed
    const checksummedEasAddress = ethers.getAddress(celoConfig.easContractAddress);
    const easContract = new ethers.Contract(
      checksummedEasAddress,
      easContractABI,
      signer
    );
    
    // Prepare attestation data
    // The schema ID is a bytes32 value, not an address, so we don't need to checksum it
    const schema = celoConfig.easSchemaId; // Schema ID for tree species research
    console.log("Using Celo EAS schema ID:", schema);
    
    // Current timestamp for the attestation
    const timestamp = Math.floor(Date.now() / 1000);
    const researchVersion = 1; // Initial version of the research
    
    // Add logging for debugging
    console.log("Input data:", data);
    
    // Encode data according to the new schema:
    // "string taxon_id, string ipfs_cid, address wallet_address, uint256 timestamp, uint256 research_version, string scientific_name, bytes32 refUID"
    const refUID = data.refUID || ethers.ZeroHash; // Default to zero hash if no reference provided
    
    const attestationData = ethers.AbiCoder.defaultAbiCoder().encode(
      ['string', 'string', 'address', 'uint256', 'uint256', 'string', 'bytes32'], 
      [
        data.taxonId, 
        data.ipfsCid, 
        data.researcher, 
        timestamp, 
        researchVersion, 
        data.species,
        refUID
      ]
    );
    
    // Create attestation
    console.log(`Creating EAS attestation on CELO (fixed chain) for species ${data.species}`);
    
    // We already have the refUID defined above, using either data.refUID or ethers.ZeroHash
    
    // Add detailed logging for debugging
    console.log("Schema UID:", schema);
    console.log("Celo EAS Contract Address:", celoConfig.easContractAddress);
    console.log("Recipient (wallet):", data.researcher);
    console.log("Encoded attestation data:", attestationData);
    
    // Skip schema registry check as it's not needed for attestation
    // and may cause errors if the EAS contract doesn't support it
    console.log("Skipping schema registry check and proceeding directly to attestation...")
    
    // Create attestation with detailed error handling
    try {
      const tx = await easContract.attest({
        schema,
        data: {
          recipient: data.researcher,
          expirationTime: 0, // No expiration
          revocable: false,
          refUID: refUID, // Properly formatted bytes32 zero value
          data: attestationData,
          value: 0 // No value being sent with the transaction
        }
      });
      
      console.log("Attestation transaction sent:", tx.hash);
      // Wait for transaction to be confirmed
      const receipt = await tx.wait();
      console.log("Transaction confirmed in block:", receipt.blockNumber);
      
      // Extract attestation UID from transaction receipt with proper error checking
      console.log("Transaction confirmed in block:", receipt.blockNumber);
      console.log("Complete transaction receipt:", JSON.stringify(receipt, null, 2));
      
      // Known EAS attestation event signatures based on EAS ABI
      // These are the keccak256 hashes of the event signatures
      const ATTESTED_EVENT_SIGNATURE = "0x8bf46bf4cfd674fa735a3d63ec1c9ad4153f033c290341f3a588b75685141b35";
      
      // Try to find the attestation event and extract the UID
      let attestationUID = null;
      
      // Based on our test with test-eas-attestation.js, the EAS contract on Celo 
      // emits logs with a specific structure where the UID is in the data field
      if (receipt.logs && receipt.logs.length > 0) {
        console.log(`Found ${receipt.logs.length} logs in transaction receipt`);
        
        // Find logs from the EAS contract with the Attested event signature
        for (const log of receipt.logs) {
          console.log(`Checking log from address: ${log.address}`);
          
          // Check if this log is from the EAS contract
          if (log.address.toLowerCase() === celoConfig.easContractAddress.toLowerCase()) {
            console.log("Found log from Celo EAS contract");
            
            // Check if this is an Attested event based on the first topic (event signature)
            if (log.topics && log.topics.length > 0 && log.topics[0] === ATTESTED_EVENT_SIGNATURE) {
              console.log("Found Attested event log");
              
              // For EAS on Celo, the attestation UID is in the data field of the log
              if (log.data && log.data.length > 2) { // "0x" plus at least one character
                attestationUID = log.data;
                console.log(`Extracted attestation UID from log data: ${attestationUID}`);
                break;
              }
            }
          }
        }
      }
      
      // If we couldn't find the UID in the logs, try parsing events
      // This is for backward compatibility and other chain implementations
      if (!attestationUID && receipt.events) {
        console.log("Checking parsed events for attestation UID");
        
        // Check if events is an array or an object
        const eventsArray = Array.isArray(receipt.events) 
          ? receipt.events 
          : Object.values(receipt.events);
          
        for (const event of eventsArray) {
          // Check if this is an Attested or AttestationCreated event
          if (event.event === 'Attested' || event.event === 'AttestationCreated') {
            console.log(`Found ${event.event} event`);
            
            // Check for UID in different argument structures
            if (event.args) {
              console.log("Event args:", event.args);
              
              if (event.args.uid) {
                attestationUID = event.args.uid;
                console.log(`Found UID in args.uid: ${attestationUID}`);
                break;
              } else if (event.args.attestationUID) {
                attestationUID = event.args.attestationUID;
                console.log(`Found UID in args.attestationUID: ${attestationUID}`);
                break;
              } else if (typeof event.args[0] === 'string' && event.args[0].startsWith('0x')) {
                // Some contracts put the UID as the first unnamed argument
                attestationUID = event.args[0];
                console.log(`Found UID in first argument: ${attestationUID}`);
                break;
              }
            }
          }
        }
      }
      
      // If we found a valid UID, return it
      if (attestationUID) {
        console.log(`Successfully extracted attestation UID: ${attestationUID}`);
        return attestationUID;
      }
      
      // If we reach here, no UID was found - this should never happen after a successful attestation
      // Instead of using a fallback, throw an error to identify and fix the issue
      console.error("ERROR: Could not extract attestation UID from transaction receipt");
      
      // As a last resort for production systems, return ZeroHash instead of throwing
      // This is better than using a string that can cause downstream errors
      console.warn("Using ZeroHash as fallback UID - this should be investigated");
      return ethers.ZeroHash;
    } catch (attestError) {
      console.error("Detailed attestation error:", attestError);
      if (attestError.data) console.log("Revert data:", attestError.data);
      if (attestError.transaction) console.log("Transaction data:", attestError.transaction.data?.substring(0, 66) + "...");
      throw new Error(`Attestation creation failed: ${attestError.message}`);
    }
  } catch (error) {
    console.error(`Error creating attestation on ${chain}:`, error);
    throw new Error(`Attestation creation failed: ${error.message}`);
  }
}

/**
 * Mints a Contreebution NFT on the specified chain
 * @param {string} chain - Chain to mint NFT on ('base', 'celo', 'optimism', 'arbitrum')
 * @param {string} recipient - Wallet address of the recipient
 * @param {number} globalId - The global_id from database to use as token ID
 * @param {string} tokenURI - URI for the NFT metadata (IPFS CID)
 * @returns {Promise<Object>} - Transaction receipt
 */
async function mintNFT(chain, recipient, globalId, tokenURI) {
  try {
    console.log(`DEBUG: mintNFT called with chain=${chain}, recipient=${recipient}, globalId=${globalId}`);

    // Check if this is a testnet request
    const isTestnet = chain.includes('sepolia') || chain.includes('alfajores');
    console.log(`DEBUG: Chain ${chain} isTestnet=${isTestnet}`);
    
    // Get chain configuration
    const chainConfig = chains[chain];
    if (!chainConfig) {
      throw new Error(`Unsupported chain: ${chain}`);
    }
    
    // Debug log the chain configuration 
    console.log(`DEBUG: Chain config for ${chain}:`, {
      chainId: chainConfig.chainId,
      rpcUrl: chainConfig.rpcUrl,
      nftContractAddress: chainConfig.nftContractAddress
    });
    
    // Check for missing critical configuration
    if (!chainConfig.rpcUrl) {
      throw new Error(`Missing RPC URL for chain: ${chain}. Please set ${chain.toUpperCase()}_RPC_URL in .env file.`);
    }
    
    if (!chainConfig.nftContractAddress) {
      throw new Error(`Missing NFT contract address for chain: ${chain}. Please set ${chain.toUpperCase()}_NFT_CONTRACT_ADDRESS in .env file.`);
    }
    
    // Set up provider and signer
    const provider = new ethers.JsonRpcProvider(chainConfig.rpcUrl);
    const signer = new ethers.Wallet(PRIVATE_KEY, provider);
    
    // Initialize NFT contract
    const nftContractABI = require('../config/abis/contreebutionNFT.json');
    // Ensure the address is checksummed
    const checksummedNftAddress = ethers.getAddress(chainConfig.nftContractAddress);
    console.log(`DEBUG: Using NFT Contract Address: ${checksummedNftAddress}`);
    
    const nftContract = new ethers.Contract(
      checksummedNftAddress,
      nftContractABI,
      signer
    );
    
    // Validate input - globalId must be a number
    const tokenId = Number(globalId);
    if (isNaN(tokenId) || tokenId <= 0) {
      throw new Error(`Invalid global_id: ${globalId}. Must be a positive number.`);
    }
    
    // Mint NFT
    console.log(`blockchain.js Minting NFT on ${chain} for recipient ${recipient} with tokenId: ${tokenId}`);
    
    // Add detailed logging of the URI format to diagnose issues
    const uri = `ipfs://${tokenURI}`;
    console.log(`DEBUG: IPFS CID being used: ${tokenURI}`);
    console.log(`DEBUG: Full URI being passed to contract: "${uri}"`);
    console.log(`DEBUG: URI length: ${uri.length} characters`);
    
    const tx = await nftContract.safeMint(recipient, tokenId, uri);
    
    // Wait for transaction to be confirmed
    const receipt = await tx.wait();
    console.log(`NFT minted with tokenId: ${tokenId}, transaction hash: ${receipt.hash}`);
    
    try {
        // Verify the tokenURI after minting to confirm it's stored correctly
        const storedURI = await nftContract.tokenURI(tokenId);
        console.log(`DEBUG: Token URI stored in contract: "${storedURI}"`);
        console.log(`DEBUG: URI matches what we sent: ${storedURI === uri}`);
    } catch (uriError) {
        console.error(`WARNING: Error fetching tokenURI after minting: ${uriError.message}`);
    }
    
    return {
      tokenId,
      tokenURI: `ipfs://${tokenURI}`, // Return the full URI with prefix for consistency
      transactionHash: receipt.hash,
      chain,
      blockNumber: receipt.blockNumber,
      status: 'success'
    };
  } catch (error) {
    console.error(`Error minting NFT on ${chain}:`, error);
    
    // Return a structured error object instead of throwing
    // This allows the calling code to handle the error appropriately
    return {
      status: 'failed',
      error: error.message,
      errorCode: error.code || 'UNKNOWN_ERROR',
      errorData: error.data || null
    };
  }
}

/**
 * Retrieves all NFTs owned by a specific wallet address on a specific chain
 * @param {string} chain - Chain to query ('base', 'celo', 'optimism', 'arbitrum')
 * @param {string} walletAddress - Wallet address to query
 * @returns {Promise<Array>} - Array of NFTs owned by the wallet
 */
async function getUserNFTs(chain, walletAddress) {
  try {
    // Get chain configuration
    const chainConfig = chains[chain];
    if (!chainConfig) {
      throw new Error(`Unsupported chain: ${chain}`);
    }
    
    // Set up provider
    const provider = new ethers.JsonRpcProvider(chainConfig.rpcUrl);
    
    // Initialize NFT contract
    const nftContractABI = require('../config/abis/contreebutionNFT.json');
    // Ensure the address is checksummed
    const checksummedNftAddress = ethers.getAddress(chainConfig.nftContractAddress);
    const nftContract = new ethers.Contract(
      checksummedNftAddress,
      nftContractABI,
      provider
    );
    
    // Query balance
    const balance = await nftContract.balanceOf(walletAddress);
    
    // Return empty array if balance is 0
    if (balance.toNumber() === 0) {
      return [];
    }
    
    // Get NFTs
    const nfts = [];
    for (let i = 0; i < balance.toNumber(); i++) {
      const tokenId = await nftContract.tokenOfOwnerByIndex(walletAddress, i);
      const tokenURI = await nftContract.tokenURI(tokenId);
      
      nfts.push({
        tokenId: tokenId.toString(),
        tokenURI,
        chain
      });
    }
    
    return nfts;
  } catch (error) {
    console.error(`Error retrieving NFTs on ${chain} for wallet ${walletAddress}:`, error);
    throw new Error(`NFT retrieval failed: ${error.message}`);
  }
}

module.exports = {
  createAttestation,
  mintNFT,
  getUserNFTs
};