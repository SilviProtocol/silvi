import axios from 'axios';
import { TreeSpecies, ResearchData, SpeciesImagesResponse, SpeciesInsightsResponse, GeoJSONPolygon, PlotAnalysisResponse } from './types';

// Set base URL for API - use the confirmed HTTPS endpoint
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://treekipedia-api.silvi.earth';

// Configure axios instance with headers - match the test script setup
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json'
  }
});

// Define API endpoints based on new backend structure
export interface APITreeSpecies {
  taxon_id: string;
  species: string; // Legacy field
  species_scientific_name: string; // New field
  common_name: string;
  family: string;
  genus: string;
  subspecies: string | null;
  taxonomic_class: string;
  taxonomic_order: string;
  accepted_scientific_name?: string;
  // researched field removed as it's no longer used
}

/**
 * Search for tree species matching a query
 */
export const searchTreeSpecies = async (query: string): Promise<APITreeSpecies[]> => {
  const { data } = await apiClient.get(`/species?search=${query}`);
  return data;
};

/**
 * Get detailed information about a specific tree species by taxon_id
 */
export const getSpeciesById = async (taxon_id: string): Promise<TreeSpecies> => {
  // Add cache busting parameter to avoid browser caching
  const { data } = await apiClient.get(`/species/${taxon_id}?_=${Date.now()}`);
  
  // Ensure the researched flag is explicitly set as a boolean
  if (data.researched === undefined || data.researched === null) {
    data.researched = false;
  }
  
  return data;
};

/**
 * Get all images for a specific species by taxon_id
 */
export const getSpeciesImages = async (taxon_id: string): Promise<SpeciesImagesResponse> => {
  try {
    // Add cache busting parameter to avoid browser caching
    const { data } = await apiClient.get(`/species/${taxon_id}/images?_=${Date.now()}`);
    return data;
  } catch (error) {
    // If we get a 404, it means species not found or has no images
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      console.log(`No images available for taxon_id: ${taxon_id}`);
      // Return empty response structure
      return {
        taxon_id,
        image_count: 0,
        images: []
      };
    }
    // Re-throw other errors
    throw error;
  }
};

/**
 * Fund research for a species (initiates the AI research process)
 */
export const fundResearch = async (
  taxon_id: string, 
  wallet_address: string, 
  chain: string,
  transaction_hash: string,
  ipfs_cid: string,
  scientific_name: string
): Promise<ResearchData> => {
  try {
    const { data } = await apiClient.post('/research/fund-research', {
      taxon_id,
      wallet_address,
      chain,
      transaction_hash,
      ipfs_cid,
      scientific_name
    });
    return data;
  } catch (error) {
    console.error('Error funding research:', error);
    if (axios.isAxiosError(error) && error.response?.status === 409) {
      // If we get a 409 Conflict, it means the species is already researched
      // Return a basic object indicating this to avoid showing an error
      return {
        taxon_id,
        // No researched flag
        message: 'This species has already been researched'
      } as ResearchData;
    }
    throw error;
  }
};

/**
 * Trigger AI research for a species (simple endpoint, no web3)
 */
export const triggerResearch = async (taxon_id: string): Promise<{
  success: boolean;
  taxon_id: string;
  scientific_name?: string;
  fields_filled?: number;
  fields_total?: number;
  duration_ms?: number;
  error?: string;
  data?: ResearchData;
}> => {
  const { data } = await apiClient.post(`/species/${taxon_id}/research`);
  return data;
};

/**
 * Get research data for a specific species
 */
export const getResearchData = async (taxon_id: string): Promise<ResearchData> => {
  try {
    // Use the correct research data endpoint with cache busting
    const { data } = await apiClient.get(`/research/${taxon_id}?_=${Date.now()}`);
    console.log("Research data retrieved successfully");
    
    // Do NOT modify the researched flag here - rely on what the server returns
    
    return data;
  } catch (error) {
    // If we get a 404, it means research hasn't been done yet
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      console.log(`No research data available for taxon_id: ${taxon_id}`);
      // Include more fields to make detection easier but don't set researched flag
      return { 
        taxon_id,
        // No researched flag,
        general_description_ai: null,
        ecological_function_ai: null,
        habitat_ai: null,
      } as ResearchData; // Return basic stub
    }
    // Re-throw other errors
    throw error;
  }
};

/**
 * Get Treederboard data (top contributors)
 */
export const getTreederboard = async (limit = 20) => {
  const { data } = await apiClient.get(`/treederboard?limit=${limit}`);
  return data;
};

/**
 * Get user profile by wallet address
 */
export const getUserProfile = async (wallet_address: string) => {
  const { data } = await apiClient.get(`/treederboard/user/${wallet_address}`);
  return data;
};

/**
 * Update user profile information
 */
export const updateUserProfile = async (wallet_address: string, display_name: string) => {
  const { data } = await apiClient.put('/treederboard/user/profile', {
    wallet_address,
    display_name
  });
  return data;
};

/**
 * Get payment status by transaction hash
 */
export const getPaymentStatus = async (transaction_hash: string) => {
  try {
    console.log(`Getting payment status for transaction: ${transaction_hash}`);
    const { data } = await apiClient.get(`/sponsorships/transaction/${transaction_hash}`);
    console.log(`Payment status response:`, data);
    return data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      console.log(`Transaction ${transaction_hash} not found in database`);
      return { 
        status: 'not_found',
        transaction_hash 
      };
    }
    console.error('Error getting payment status:', error);
    throw error;
  }
};

/**
 * Report transaction hash to backend for monitoring
 */
export const reportTransaction = async (
  sponsorship_id: string, 
  transaction_hash: string,
  taxon_id?: string,
  wallet_address?: string,
  chain?: string
) => {
  try {
    console.log(`Reporting transaction ${transaction_hash} for sponsorship ${sponsorship_id}`);
    
    // Build the payload with all available data
    const payload: any = {
      sponsorship_id,
      transaction_hash
    };
    
    // Add optional fields if they exist
    if (taxon_id) payload.taxon_id = taxon_id;
    if (wallet_address) payload.wallet_address = wallet_address;
    if (chain) payload.chain = chain;
    
    console.log('Sending report-transaction payload:', payload);
    
    const { data } = await apiClient.post('/sponsorships/report-transaction', payload);
    console.log('Report transaction response:', data);
    return data;
  } catch (error) {
    console.error('Error reporting transaction:', error);
    throw error;
  }
};

/**
 * Get all sponsorships by a user's wallet address
 */
export const getUserSponsorships = async (wallet_address: string, limit = 20, offset = 0) => {
  try {
    const { data } = await apiClient.get(`/sponsorships/user/${wallet_address}`, {
      params: { limit, offset }
    });
    return data;
  } catch (error) {
    console.error('Error fetching user sponsorships:', error);
    return [];
  }
};

/**
 * Get all sponsorships for a specific species
 */
export const getSpeciesSponsorships = async (taxon_id: string, limit = 20, offset = 0) => {
  try {
    const { data } = await apiClient.get(`/sponsorships/species/${taxon_id}`, {
      params: { limit, offset }
    });
    return data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      return [];
    }
    console.error('Error fetching species sponsorships:', error);
    return [];
  }
};

/**
 * Get auto-complete suggestions for species search
 * Follows the API.md specification for /species/suggest
 */
export const getSpeciesSuggestions = async (
  query: string, 
  field?: 'common_name' | 'species' | 'species_scientific_name'
) => {
  if (!query || query.length < 2) return [];
  
  try {
    // Create the params object according to API spec
    const params: Record<string, string> = { query };
    if (field) {
      params.field = field;
    }
    
    // Use the get method with params passed separately (not in URL)
    const response = await apiClient.get('/species/suggest', { params });
    
    // Return actual API response
    return response.data;
  } catch (error) {
    console.error("Error fetching species suggestions:", error);
    return []; // Return empty array on error
  }
};

/**
 * Initiate a sponsorship payment (direct USDC transfer)
 */
export async function initiateSponsorshipPayment(data: {
  taxon_id: string;
  wallet_address: string;
  chain: string;
}) {
  try {
    // Add detailed debugging to track API calls
    console.log(`Initiating sponsorship payment to ${API_BASE_URL}/sponsorships/initiate with data:`, {
      taxon_id: data.taxon_id,
      wallet_address: data.wallet_address,
      chain: data.chain
    });
    
    const response = await apiClient.post('/sponsorships/initiate', data);
    
    // Log response for debugging
    console.log('Sponsorship initiation response:', response.data);

    if (!response.data?.success) {
      throw new Error(response.data?.error || 'Failed to initiate sponsorship payment');
    }

    // Make sure we return the full response data
    return response.data;
  } catch (error: any) {
    console.error('Error initiating sponsorship payment:', error);
    
    // Check for 404 errors (endpoint not found)
    if (error.response?.status === 404) {
      throw new Error('Sponsorship API endpoint not found. The system may be in maintenance.');
    }
    
    // For network errors, provide a clearer message
    if (error.message?.includes('Network Error')) {
      throw new Error('Network error while connecting to the server. Please check your internet connection and try again.');
    }
    
    throw error;
  }
}

/**
 * Admin dashboard API endpoints
 */

// Get server statistics
export async function getServerStats() {
  try {
    const response = await apiClient.get('/admin-api/stats');
    return response.data;
  } catch (error) {
    console.error('Error fetching server stats:', error);
    throw error;
  }
}

// Get API call statistics
export async function getApiCallStats() {
  try {
    const response = await apiClient.get('/admin-api/call-stats');
    return response.data;
  } catch (error) {
    console.error('Error fetching API call stats:', error);
    throw error;
  }
}

// Get error logs
export async function getErrorLogs() {
  try {
    const response = await apiClient.get('/admin-api/errors');
    return response.data;
  } catch (error) {
    console.error('Error fetching error logs:', error);
    throw error;
  }
}

/**
 * Geospatial API endpoints
 */

// Analyze species within a polygon plot
export const analyzePlot = async (geometry: GeoJSONPolygon): Promise<PlotAnalysisResponse> => {
  try {
    const { data } = await apiClient.post('/api/geospatial/analyze-plot', { geometry });
    return data;
  } catch (error) {
    console.error('Error analyzing plot:', error);
    throw error;
  }
};

