// Generic interface for all tree species data based on the new database schema
export interface TreeSpecies {
  taxon_id: string;
  species: string; // Kept for backward compatibility
  species_scientific_name: string; // New field replacing 'species'
  family: string;
  genus: string;
  subspecies: string | null;
  specific_epithet: string;
  accepted_scientific_name: string;
  synonyms: string;
  common_name: string;
  common_countries: string;
  countries_introduced: string;
  countries_invasive: string;
  countries_native: string;
  wcvp_native: string;
  wcvp_introduced: string;
  taxonomic_class: string;
  taxonomic_order: string;
  ecoregions: string;
  biomes: string;
  
  // Original fields kept for backward compatibility
  habitat: string;
  elevation_ranges: string;
  compatible_soil_types: string;
  native_adapted_habitats: string;
  agroforestry_use_cases: string;
  growth_form: string;
  leaf_type: string;
  deciduous_evergreen: string;
  flower_color: string;
  fruit_type: string;
  bark_characteristics: string;
  conservation_status: string;
  general_description: string;
  ecological_function: string;
  stewardship_best_practices: string;
  planting_recipes: string;
  pruning_maintenance: string;
  disease_pest_management: string;
  fire_management: string;
  cultural_significance: string;
  
  // New AI-generated content fields
  habitat_ai: string;
  habitat_human: string;
  elevation_ranges_ai: string; 
  elevation_ranges_human: string;
  compatible_soil_types_ai: string;
  compatible_soil_types_human: string;
  native_adapted_habitats_ai: string;
  native_adapted_habitats_human: string;
  agroforestry_use_cases_ai: string;
  agroforestry_use_cases_human: string;
  growth_form_ai: string;
  growth_form_human: string;
  leaf_type_ai: string;
  leaf_type_human: string;
  deciduous_evergreen_ai: string;
  deciduous_evergreen_human: string;
  flower_color_ai: string;
  flower_color_human: string;
  fruit_type_ai: string;
  fruit_type_human: string;
  bark_characteristics_ai: string;
  bark_characteristics_human: string;
  conservation_status_ai: string;
  conservation_status_human: string;
  general_description_ai: string;
  general_description_human: string;
  ecological_function_ai: string;
  ecological_function_human: string;
  stewardship_best_practices_ai: string;
  stewardship_best_practices_human: string;
  planting_recipes_ai: string;
  planting_recipes_human: string;
  pruning_maintenance_ai: string;
  pruning_maintenance_human: string;
  disease_pest_management_ai: string;
  disease_pest_management_human: string;
  fire_management_ai: string;
  fire_management_human: string;
  cultural_significance_ai: string;
  cultural_significance_human: string;
  
  // Numerical fields with AI/human variants
  maximum_height: number | null;
  maximum_height_ai: number | null;
  maximum_height_human: number | null;
  maximum_diameter: number | null;
  maximum_diameter_ai: number | null;
  maximum_diameter_human: number | null;
  lifespan: string;
  lifespan_ai: string;
  lifespan_human: string;
  maximum_tree_age: number | null;
  maximum_tree_age_ai: number | null;
  maximum_tree_age_human: number | null;
  
  // Other fields without AI/human variants
  climate_change_vulnerability: string;
  national_conservation_status: string;
  verification_status: string;
  threats: string;
  timber_value: string;
  non_timber_products: string;
  cultivars: string;
  nutritional_caloric_value: string;
  cultivation_details: string;
  associated_media: string;
  default_image: string;
  
  // Image-related fields from API
  image_count: number;
  primary_image_url: string | null;
  primary_image_license: string | null;
  primary_image_photographer: string | null;
  primary_image_page_url: string | null;
  primary_image_source: string | null;
  
  total_occurrences: number | null;
  allometric_models: string;
  allometric_curve: string;
  reference_list: string;
  data_sources: string;
  ipfs_cid: string;
  researched: boolean; // Flag to indicate if species has been researched
  forest_type: string;
  wetland_type: string;
  urban_setting: string;
  successional_stage: string;
  tolerances: string;
  forest_layers: string;
  
  last_updated_date: string;
  created_at: string;
  updated_at: string;
}

// Species image data structure
export interface SpeciesImage {
  id: number;
  taxon_id: string;
  image_url: string;
  license: string | null;
  photographer: string | null;
  page_url: string | null;
  source: string;
  is_primary: boolean;
  created_at: string;
}

// Response structure for species images endpoint
export interface SpeciesImagesResponse {
  taxon_id: string;
  image_count: number;
  images: SpeciesImage[];
}

// Legacy interface for backward compatibility with existing components
export interface Species {
  id: string;
  species_common_name: string;
  species_scientific_name: string;
  family: string;
  genus: string;
  subspecies?: string;
  taxonomic_class: string;
  taxonomic_order: string;
  description?: string;
}

// Payload for research funding request
export interface ResearchPayload {
  taxon_id: string;
  wallet_address: string;
  chain: string;
  transaction_hash: string;
  ipfs_cid: string;
  scientific_name: string; // Renamed field (previously 'species')
}

// Research data structure with AI/human field variants
export interface ResearchData {
  taxon_id: string;
  species_scientific_name: string;
  researched: boolean; // Flag to indicate if species has been researched
  
  // AI-generated content fields
  general_description_ai: string;
  general_description_human: string;
  native_adapted_habitats_ai: string;
  native_adapted_habitats_human: string;
  stewardship_best_practices_ai: string;
  stewardship_best_practices_human: string;
  planting_recipes_ai: string;
  planting_recipes_human: string;
  ecological_function_ai: string;
  ecological_function_human: string;
  agroforestry_use_cases_ai: string;
  agroforestry_use_cases_human: string;
  elevation_ranges_ai: string;
  elevation_ranges_human: string;
  compatible_soil_types_ai: string;
  compatible_soil_types_human: string;
  conservation_status_ai: string;
  conservation_status_human: string;
  
  // For backward compatibility, include original fields
  general_description: string;
  native_adapted_habitats: string;
  stewardship_best_practices: string;
  planting_methods: string;
  ecological_function: string;
  agroforestry_use_cases: string;
  elevation_ranges: string;
  compatible_soil_types: string;
  conservation_status: string;
  
  verification_status: string;
  ipfs_cid: string;
  researcher_wallet: string;
  created_at: string;
  updated_at: string;
}

// User data from Treederboard
export interface User {
  id: number;
  wallet_address: string;
  display_name: string | null;
  total_points: number;
  contribution_count: number;
  first_contribution_at: string;
  last_contribution_at: string;
  created_at: string;
  updated_at: string;
}

// Contreebution NFT data
export interface ContreebutionNFT {
  id: number;
  global_id: number;
  taxon_id: string;
  wallet_address: string;
  points: number;
  ipfs_cid: string;
  transaction_hash: string;
  metadata: Record<string, unknown>; // Typed as a generic object
  created_at: string;
}

// Chain type matching wagmi's chain structure
export interface Chain {
  id: number;
  name: string;
  network: string;
  nativeCurrency: {
    name: string;
    symbol: string;
    decimals: number;
  };
  rpcUrls: {
    default: {
      http: string[];
    };
  };
  blockExplorers?: {
    default: {
      name: string;
      url: string;
    };
  };
  testnet: boolean;
}

// GeoJSON types for geospatial analysis
export interface GeoJSONPolygon {
  type: 'Polygon';
  coordinates: number[][][];
}

// Plot analysis request/response types
export interface PlotAnalysisRequest {
  geometry: GeoJSONPolygon;
}

export interface PlotAnalysisResponse {
  totalSpecies: number;
  totalOccurrences: number;
  crossAnalysis?: CrossAnalysisData;
  species: PlotSpeciesResult[];
}

export interface CrossAnalysisData {
  country: string | null;
  countryDetected: boolean;

  // Native status breakdown (from WCVP data)
  nativeSpecies: number;
  introducedSpecies: number;
  unknownNativeStatus: number;

  // Intact forest breakdown
  intactForestSpecies: number;
  nonIntactForestSpecies: number;
  unknownForestStatus: number;

  // Commercial breakdown
  commercialSpecies: number;
  nonCommercialSpecies: number;

  // Data source indicator
  dataSource?: string;
}

export interface PlotSpeciesResult {
  taxon_id: string;
  scientific_name: string;
  common_name: string | null;
  family?: string | null;
  genus?: string | null;
  occurrences: number;
  tile_count?: number;

  // Enhanced analysis fields
  nativeStatus?: 'native' | 'introduced' | 'unknown';
  nativePercentage?: number; // Percentage of analysis zone where species is native (0-100)
  intactForestStatus?: 'present' | 'absent' | 'unknown';
  isCommercial?: boolean;
}