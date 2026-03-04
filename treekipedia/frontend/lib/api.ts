import axios from 'axios';
import { getSession } from 'next-auth/react';
import { TreeSpecies, ResearchData, SpeciesImagesResponse, SpeciesInsightsResponse, GeoJSONPolygon, PlotAnalysisResponse, BulkResearchStatusResponse, SavedAnalysis } from './types';

// Set base URL for API - use the confirmed HTTPS endpoint
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://treekipedia-api.silvi.earth';

// Configure axios instance with headers - match the test script setup
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json'
  }
});

// Add auth interceptor: attaches Django JWT from NextAuth session
apiClient.interceptors.request.use(async (config) => {
  try {
    const session = await getSession();
    const token = (session?.user as any)?.access;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  } catch {
    // No session available — continue without auth
  }
  return config;
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
 * Fund research for a species
 *
 * @deprecated Use triggerResearch() instead. This function is kept for backwards
 * compatibility but now just adds to research_queue (no payment/NFT).
 *
 * NOTE (Jan 2026): NFT minting and blockchain features are disabled.
 * Research uses queue-based Claude Code CLI workflow.
 */
export const fundResearch = async (
  taxon_id: string,
  _wallet_address: string,  // No longer used
  _chain: string,           // No longer used
  _transaction_hash: string, // No longer used
  _ipfs_cid: string,        // No longer used
  scientific_name: string
): Promise<ResearchData> => {
  try {
    // Now just adds to queue - same as triggerResearch
    const { data } = await apiClient.post('/research/fund-research', {
      taxon_id,
      scientific_name
    });
    return data;
  } catch (error) {
    console.error('Error funding research:', error);
    if (axios.isAxiosError(error) && error.response?.status === 409) {
      return {
        taxon_id,
        message: 'This species has already been researched'
      } as ResearchData;
    }
    throw error;
  }
};

/**
 * Trigger AI research for a species (simple endpoint, no web3)
 *
 * New architecture: Checks for insights in the database.
 * If insights exist, syncs them to species.*_ai columns.
 * If no insights exist, returns message about using Claude Code CLI.
 */
export const triggerResearch = async (taxon_id: string, force: boolean = false): Promise<{
  success: boolean;
  taxon_id: string;
  scientific_name?: string;
  message?: string;
  insights_count?: number;
  avg_confidence?: number;
  research_version?: number;
  current_version?: number;
  can_reresearch?: boolean;
  queued?: boolean;
  queue_status?: 'pending' | 'processing' | 'completed' | 'failed';
  fields_filled?: number;
  fields_total?: number;
  duration_ms?: number;
  error?: string;
  data?: ResearchData;
}> => {
  console.log(`[API] triggerResearch called - taxon_id=${taxon_id}, force=${force}`);
  const { data } = await apiClient.post(`/species/${taxon_id}/research`, { force });
  console.log(`[API] triggerResearch response:`, data);
  return data;
};

/**
 * Get insights metadata for a species (research version, confidence, sources)
 */
export interface InsightsMetadata {
  version: number;
  research_date: string;
  model: string;
  insight_count: number;
  field_count: number;  // Number of unique claim_types (fields)
  avg_confidence: number;
  source_count: number;
  session_id?: string;
}

export interface InsightSource {
  url: string;
  title: string;
  type: string;
  credibility: number;
}

export interface ConfidenceBreakdown {
  source_score: number;
  agreement_score: number;
  specificity_score: number;
  source_count: number;
  source_diversity: number;
  methodology: string;
}

export interface Corroboration {
  sources_agree: boolean;
  agreement_note: string;
  cross_referenced?: string[];
  conflicting_info?: string;
}

export interface InsightDetail {
  claim_type: string;
  claim_value: string | object;
  confidence: number;
  confidence_breakdown?: ConfidenceBreakdown | null;
  corroboration?: Corroboration | null;
  sources: InsightSource[];
  model: string;
  agent_type: string;
  created_at: string;
}

export interface InsightsResponse {
  taxon_id: string;
  has_insights: boolean;
  metadata: InsightsMetadata | null;
  insights: InsightDetail[];
}

export const getInsightsMetadata = async (taxon_id: string): Promise<InsightsResponse> => {
  try {
    const { data } = await apiClient.get(`/species/${taxon_id}/insights?_=${Date.now()}`);
    return { ...data, insights: data.insights || [] };
  } catch (error) {
    console.error('Error fetching insights metadata:', error);
    return {
      taxon_id,
      has_insights: false,
      metadata: null,
      insights: []
    };
  }
};

export const getFullInsights = async (taxon_id: string): Promise<InsightsResponse> => {
  try {
    const { data } = await apiClient.get(`/species/${taxon_id}/insights?full=true&_=${Date.now()}`);
    return data;
  } catch (error) {
    console.error('Error fetching full insights:', error);
    return {
      taxon_id,
      has_insights: false,
      metadata: null,
      insights: []
    };
  }
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

/**
 * Ecoregion Guide API endpoints
 */

export interface EcoregionSearchResult {
  eco_id: number;
  eco_name: string;
  biome_name: string;
  realm: string;
  area_km2: number;
}

export interface EcoregionGuideSpecies {
  taxon_id: string;
  scientific_name: string | null;
  common_name: string | null;
  popular_common_name_ai?: string | null;
  family: string | null;
  genus: string | null;
  leaf_score: number;
  tier: 'BEST' | 'GOOD' | 'ACCEPTABLE' | 'LOW';
  is_native: boolean;
  occurrence_count: number;
  tile_count: number;
  general_description_ai?: string | null;
  habitat_ai?: string | null;
  ecological_function_ai?: string | null;
  maximum_height_ai?: string | null;
  conservation_status_ai?: string | null;
}

export interface EcoregionGuideSynthesized {
  overview_intro: string | null;
  planting_strategy: string | null;
  climate_context: string | null;
  conservation_notes: string | null;
  generated_at: string;
  model_used: string;
  synthesis_version: number;
  species_count: number;
}

export interface EcoregionGuideResponse {
  ecoregion: EcoregionSearchResult;
  synthesized_content: EcoregionGuideSynthesized | null;
  statistics: {
    total_species: number;
    by_tier: { BEST: number; GOOD: number; ACCEPTABLE: number; LOW: number };
  };
  top_species: EcoregionGuideSpecies[];
  species_by_tier: {
    BEST: EcoregionGuideSpecies[];
    GOOD: EcoregionGuideSpecies[];
    ACCEPTABLE: EcoregionGuideSpecies[];
    LOW: EcoregionGuideSpecies[];
  };
  countries: string[];
}

export const searchEcoregions = async (query: string): Promise<EcoregionSearchResult[]> => {
  if (!query || query.length < 2) return [];
  try {
    const { data } = await apiClient.get(`/api/geospatial/ecoregions/search?q=${encodeURIComponent(query)}`);
    return data;
  } catch (error) {
    console.error('Error searching ecoregions:', error);
    return [];
  }
};

export const getEcoregionGuide = async (eco_id: string | number): Promise<EcoregionGuideResponse> => {
  const { data } = await apiClient.get(`/api/guides/ecoregion/${eco_id}`);
  return data;
};

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

// ============================================
// Unified Analysis Modal API Functions
// ============================================

/**
 * Predict suitable species for a polygon area (AlphaEarth satellite-based)
 */
export const predictPolygonSpecies = async (
  geometry: GeoJSONPolygon,
  sampleCount: number = 9
) => {
  const { data } = await apiClient.post('/api/prediction/polygon', {
    geometry,
    sample_count: sampleCount,
    strategy: 'grid',
    min_similarity: 0.70
  });
  return data;
};

/**
 * Get LEAF recommendation for a polygon (ecological scoring)
 */
export const getLeafRecommendation = async (geometry: GeoJSONPolygon, strategy?: string) => {
  const params: Record<string, any> = { geometry };
  if (strategy) params.strategy = strategy;
  const { data } = await apiClient.post('/api/prediction/polygon', {
    ...params,
    sample_count: 9,
    min_similarity: 0.70
  });
  return data;
};

/**
 * Check research status for multiple species at once
 */
export const checkBulkResearchStatus = async (taxonIds: string[]): Promise<BulkResearchStatusResponse> => {
  const { data } = await apiClient.post('/species/bulk-research-status', { taxon_ids: taxonIds });
  return data;
};

/**
 * Save an analysis session
 */
export const saveAnalysis = async (analysisData: Partial<SavedAnalysis>): Promise<SavedAnalysis> => {
  const { data } = await apiClient.post('/api/analyses', analysisData);
  return data;
};

/**
 * Get user's saved analyses
 */
export const getUserAnalyses = async (): Promise<SavedAnalysis[]> => {
  const { data } = await apiClient.get('/api/analyses');
  return data;
};

/**
 * Update a saved analysis with new results
 */
export const updateAnalysis = async (id: number, updates: Partial<SavedAnalysis>): Promise<SavedAnalysis> => {
  const { data } = await apiClient.patch(`/api/analyses/${id}`, updates);
  return data;
};

