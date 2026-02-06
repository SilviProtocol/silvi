import { useCallback, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { getSpeciesById, getFullInsights, InsightDetail } from "@/lib/api";
import { TreeSpecies } from "@/lib/types";

/**
 * Custom hook for fetching and managing species and research data.
 *
 * Two queries:
 * 1. Species base data (includes all _ai and _human columns)
 * 2. Insights (atomic claims with per-field confidence + research metadata)
 *
 * Data priority: human > ai > legacy
 */
export function useSpeciesData(taxonId: string) {
  // Fetch species base data (includes all _ai columns from research)
  const speciesQuery = useQuery({
    queryKey: ["species", taxonId],
    queryFn: () => getSpeciesById(taxonId),
    staleTime: 10000,
  });

  // Fetch insights (metadata + per-field confidence/sources)
  const insightsQuery = useQuery({
    queryKey: ["insights", taxonId],
    queryFn: () => getFullInsights(taxonId),
    staleTime: 10000,
  });

  // Build map for quick lookup of insights by claim_type
  // Atomic model: multiple insights can exist per claim_type
  const insightsByField = useMemo(() => {
    const map = new Map<string, InsightDetail[]>();
    if (insightsQuery.data?.insights) {
      insightsQuery.data.insights.forEach((insight: InsightDetail) => {
        const existing = map.get(insight.claim_type) || [];
        existing.push(insight);
        map.set(insight.claim_type, existing);
      });
    }
    return map;
  }, [insightsQuery.data?.insights]);

  // Get all insights for a specific field (atomic model supports multiple)
  const getInsightsForField = useCallback(
    (fieldName: string): InsightDetail[] => {
      return insightsByField.get(fieldName) || [];
    },
    [insightsByField]
  );

  // Get the primary (highest confidence) insight for a specific field
  const getInsightForField = useCallback(
    (fieldName: string): InsightDetail | null => {
      const insights = insightsByField.get(fieldName);
      if (!insights || insights.length === 0) return null;
      return insights.reduce((best, current) =>
        (current.confidence > best.confidence) ? current : best
      );
    },
    [insightsByField]
  );

  // Determine if the species has been researched
  const isResearched = useMemo(() => {
    const researchedValue = speciesQuery.data?.researched;
    return researchedValue === true ||
           researchedValue === 'YES' ||
           researchedValue === 'yes';
  }, [speciesQuery.data]);

  // Helper to check if a value is valid (not null, not empty, not "NA")
  const isValidValue = (val: any): boolean => {
    if (val === null || val === undefined) return false;
    if (typeof val === 'string') {
      const trimmed = val.trim();
      return trimmed !== '' && trimmed.toUpperCase() !== 'NA';
    }
    return true;
  };

  // Field value accessor with precedence: human > ai > legacy
  const getFieldValue = useCallback(
    (fieldName: string): { value: any; source: "human" | "ai" | "legacy" | null } => {
      const species = speciesQuery.data;
      if (!species) return { value: null, source: null };

      // Check human data first (highest priority)
      const humanValue = species[`${fieldName}_human` as keyof TreeSpecies];
      if (isValidValue(humanValue)) {
        return { value: humanValue, source: "human" };
      }

      // Then check AI data
      const aiValue = species[`${fieldName}_ai` as keyof TreeSpecies];
      if (isValidValue(aiValue)) {
        return { value: aiValue, source: "ai" };
      }

      // Finally check legacy data (no suffix)
      const legacyValue = species[fieldName as keyof TreeSpecies];
      if (isValidValue(legacyValue)) {
        return { value: legacyValue, source: "legacy" };
      }

      return { value: null, source: null };
    },
    [speciesQuery.data]
  );

  // Check if a specific field has been researched
  const isFieldResearched = useCallback(
    (fieldName: string): boolean => {
      const species = speciesQuery.data;
      if (!species) return false;
      const aiValue = species[`${fieldName}_ai` as keyof TreeSpecies];
      const humanValue = species[`${fieldName}_human` as keyof TreeSpecies];
      return isValidValue(aiValue) || isValidValue(humanValue);
    },
    [speciesQuery.data]
  );

  // Count researched fields by category
  const getResearchFieldCount = useCallback(() => {
    const categoryFields: Record<string, string[]> = {
      overview: ["general_description"],
      geographic: ["elevation_ranges", "native_adapted_habitats"],
      ecological: ["conservation_status", "ecological_function", "habitat"],
      physical: [
        "growth_form", "leaf_type", "deciduous_evergreen", "flower_color",
        "fruit_type", "bark_characteristics", "maximum_height", "maximum_diameter",
        "lifespan", "maximum_tree_age"
      ],
      stewardship: [
        "stewardship_best_practices", "agroforestry_use_cases", "compatible_soil_types",
        "planting_recipes", "pruning_maintenance", "disease_pest_management",
        "fire_management", "cultural_significance"
      ]
    };

    const counts = { total: 0, byCategory: {} as Record<string, number> };

    Object.entries(categoryFields).forEach(([category, fields]) => {
      let categoryCount = 0;
      fields.forEach(field => {
        if (isFieldResearched(field)) {
          categoryCount++;
          counts.total++;
        }
      });
      counts.byCategory[category] = categoryCount;
    });

    return counts;
  }, [isFieldResearched]);

  return {
    species: speciesQuery.data,
    researchData: speciesQuery.data,  // Alias for backwards compat
    insightsMetadata: insightsQuery.data?.metadata || null,
    insights: insightsQuery.data?.insights || [],
    hasInsights: insightsQuery.data?.has_insights || false,
    isLoading: speciesQuery.isLoading,
    isInsightsLoading: insightsQuery.isLoading,
    isError: speciesQuery.isError,
    isResearched,
    getFieldValue,
    getInsightForField,
    getInsightsForField,
    isFieldResearched,
    getResearchFieldCount,
    refetchSpecies: speciesQuery.refetch,
    refetchResearch: speciesQuery.refetch,  // Alias for backwards compat
    refetchInsights: insightsQuery.refetch
  };
}
