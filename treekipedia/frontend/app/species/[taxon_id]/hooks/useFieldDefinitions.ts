/**
 * This file contains field definitions for each tab in the species page
 */

// Define the structure for field objects
export interface FieldDefinition {
  label: string;
  key: string;
  hasAiHuman?: boolean;
  type?: "string" | "numeric" | "date";
  isLongText?: boolean;
}

/**
 * Hook to get field definitions organized by tab
 */
export function useFieldDefinitions() {
  // Overview tab fields
  const overviewFields: FieldDefinition[] = [
    { label: "Scientific Name", key: "species_scientific_name" },
    { label: "Common Name", key: "common_name" },
    { label: "General Description", key: "general_description", hasAiHuman: true, isLongText: true },
    { label: "Etymology", key: "etymology", hasAiHuman: true },
    { label: "Identification Features", key: "identification_features", hasAiHuman: true, isLongText: true },
    { label: "Accepted Scientific Name", key: "accepted_scientific_name" },
    { label: "Family", key: "family" },
    { label: "Genus", key: "genus" },
    { label: "Subspecies", key: "subspecies" },
    { label: "Specific Epithet", key: "specific_epithet" },
    { label: "Synonyms", key: "synonyms", hasAiHuman: true },
    { label: "Taxonomic Order", key: "taxonomic_order" },
    { label: "Class", key: "class" }
  ];

  // Geographic tab fields
  const geographicFields: FieldDefinition[] = [
    { label: "Biomes", key: "biomes" },
    { label: "Native Regions", key: "wcvp_native" },
    { label: "Introduced Regions", key: "wcvp_introduced" },
    { label: "Countries Invasive", key: "countries_invasive" },
    { label: "Common Countries", key: "common_countries" },
    { label: "Ecoregions", key: "ecoregions" },
    { label: "Elevation Ranges", key: "elevation_ranges", hasAiHuman: true },
    { label: "Climate Tolerance", key: "climate_tolerance", hasAiHuman: true, isLongText: true }
  ];

  // Ecological tab fields
  const ecologicalFields: FieldDefinition[] = [
    { label: "Ecological Function", key: "ecological_function", hasAiHuman: true, isLongText: true },
    { label: "Conservation Status", key: "conservation_status", hasAiHuman: true },
    { label: "National Conservation Status", key: "national_conservation_status" },
    { label: "Habitat", key: "habitat", hasAiHuman: true, isLongText: true },
    { label: "Native Adapted Habitats", key: "native_adapted_habitats", hasAiHuman: true, isLongText: true },
    { label: "Forest Type", key: "forest_type" },
    { label: "Wetland Type", key: "wetland_type" },
    { label: "Urban Setting", key: "urban_setting" },
    { label: "Climate Change Vulnerability", key: "climate_change_vulnerability" },
    { label: "Associated Species", key: "associated_species", hasAiHuman: true, isLongText: true },
    { label: "Successional Stage", key: "successional_stage" },
    { label: "Tolerances", key: "tolerances", hasAiHuman: true, isLongText: true },
    { label: "Forest Layers", key: "forest_layers" },
    { label: "Threats", key: "threats" }
  ];

  // Physical tab fields
  const physicalFields: FieldDefinition[] = [
    { label: "Growth Form", key: "growth_form", hasAiHuman: true },
    { label: "Leaf Type", key: "leaf_type", hasAiHuman: true },
    { label: "Deciduous/Evergreen", key: "deciduous_evergreen", hasAiHuman: true },
    { label: "Flower Color", key: "flower_color", hasAiHuman: true },
    { label: "Fruit Type", key: "fruit_type", hasAiHuman: true },
    { label: "Bark Characteristics", key: "bark_characteristics", hasAiHuman: true },
    { label: "Maximum Height (m)", key: "maximum_height", hasAiHuman: true, type: "numeric" },
    { label: "Maximum Diameter (m)", key: "maximum_diameter", hasAiHuman: true, type: "numeric" },
    { label: "Lifespan", key: "lifespan", hasAiHuman: true },
    { label: "Maximum Tree Age (Years)", key: "maximum_tree_age", hasAiHuman: true, type: "numeric" },
    { label: "Allometric Models", key: "allometric_models" },
    { label: "Allometric Curve", key: "allometric_curve" }
  ];

  // Stewardship tab fields
  const stewardshipFields: FieldDefinition[] = [
    { label: "Stewardship Best Practices", key: "stewardship_best_practices", hasAiHuman: true, isLongText: true },
    { label: "Agroforestry Use Cases", key: "agroforestry_use_cases", hasAiHuman: true, isLongText: true },
    { label: "Compatible Soil Types", key: "compatible_soil_types", hasAiHuman: true, isLongText: true },
    { label: "Planting Recipes", key: "planting_recipes", hasAiHuman: true, isLongText: true },
    { label: "Pruning & Maintenance", key: "pruning_maintenance", hasAiHuman: true, isLongText: true },
    { label: "Disease & Pest Management", key: "disease_pest_management", hasAiHuman: true, isLongText: true },
    { label: "Fire Management", key: "fire_management", hasAiHuman: true, isLongText: true },
    { label: "Cultural Significance", key: "cultural_significance", hasAiHuman: true, isLongText: true },
    { label: "Propagation Methods", key: "propagation_methods", hasAiHuman: true, isLongText: true },
    { label: "Timber Value", key: "timber_value", hasAiHuman: true },
    { label: "Non-Timber Products", key: "non_timber_products", hasAiHuman: true, isLongText: true },
    { label: "Cultivars", key: "cultivars" },
    { label: "Nutritional/Caloric Value", key: "nutritional_caloric_value", hasAiHuman: true },
    { label: "Cultivation Details", key: "cultivation_details" }
  ];

  // Research data tab fields
  const researchDataFields: FieldDefinition[] = [
    { label: "Total Occurrences", key: "total_occurrences", type: "numeric" },
    { label: "Verification Status", key: "verification_status" },
    { label: "Data Sources", key: "data_sources" },
    { label: "Reference List", key: "reference_list" },
    { label: "IPFS CID", key: "ipfs_cid" },
    { label: "Last Updated", key: "last_updated_date", type: "date" }
  ];

  return {
    overviewFields,
    geographicFields,
    ecologicalFields,
    physicalFields,
    stewardshipFields,
    researchDataFields
  };
}