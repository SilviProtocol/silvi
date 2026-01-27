import { useState, useCallback, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import { getSpeciesById, getResearchData, getFullInsights, InsightsMetadata, InsightDetail } from "@/lib/api";
import { TreeSpecies, ResearchData } from "@/lib/types";

/**
 * Custom hook for fetching and managing species and research data
 * @param taxonId The ID of the species to fetch
 */
export function useSpeciesData(taxonId: string) {
  // Fetch species base data
  const speciesQuery = useQuery({
    queryKey: ["species", taxonId],
    queryFn: () => getSpeciesById(taxonId),
    staleTime: 10000, // Consider data fresh for 10 seconds
  });

  // Fetch research data (may not exist if species hasn't been researched)
  const researchQuery = useQuery({
    queryKey: ["research", taxonId],
    queryFn: () => getResearchData(taxonId),
    staleTime: 5000, // Consider research data fresh for only 5 seconds
    // Don't retry on 404 - it means research not available yet
    retry: (failureCount, error) => {
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        return false;
      }
      return failureCount < 3;
    },
  });

  // Fetch full insights (metadata + per-field confidence/sources)
  const insightsQuery = useQuery({
    queryKey: ["insights", taxonId],
    queryFn: () => getFullInsights(taxonId),
    staleTime: 10000,
  });

  // Create a map for quick lookup of insight details by claim_type
  // ATOMIC MODEL: Multiple insights can exist per claim_type
  const insightsByField = useMemo(() => {
    const map = new Map<string, InsightDetail[]>();
    if (insightsQuery.data?.insights) {
      insightsQuery.data.insights.forEach(insight => {
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
  // For backwards compatibility with components expecting single insight
  const getInsightForField = useCallback(
    (fieldName: string): InsightDetail | null => {
      const insights = insightsByField.get(fieldName);
      if (!insights || insights.length === 0) return null;
      // Return highest confidence insight as primary
      return insights.reduce((best, current) =>
        (current.confidence > best.confidence) ? current : best
      );
    },
    [insightsByField]
  );

  // Determine if the species has been researched
  const isResearched = useMemo(() => {
    // Check the explicit researched flag from the database
    // Handle both boolean true and string "YES" values
    const researchedValue = speciesQuery.data?.researched;
    const hasResearchedFlag = researchedValue === true ||
                              researchedValue === 'YES' ||
                              researchedValue === 'yes';

    // Log debugging info
    console.log(`Research detection check for ${taxonId}:`, {
      researchedValue,
      hasResearchedFlag,
      researchQueryStatus: researchQuery.status
    });

    return hasResearchedFlag;
  }, [speciesQuery.data, researchQuery.status, taxonId]);

  // Helper to check if a value is valid (not null, not empty, not "NA")
  const isValidValue = (val: any): boolean => {
    if (val === null || val === undefined) return false;
    if (typeof val === 'string') {
      const trimmed = val.trim();
      return trimmed !== '' && trimmed.toUpperCase() !== 'NA';
    }
    return true;
  };

  // Helper for accessing field values with precedence:
  // 1. Human data (if available and valid)
  // 2. AI data (if available and valid)
  // 3. Legacy data (if available and valid)
  const getFieldValue = useCallback(
    (fieldName: string): { value: any; source: "human" | "ai" | "legacy" | null } => {
      const humanField = `${fieldName}_human`;
      const aiField = `${fieldName}_ai`;

      // Check human data first (highest priority)
      const humanValue = speciesQuery.data?.[humanField as keyof TreeSpecies] ??
                         researchQuery.data?.[humanField as keyof ResearchData];
      if (isValidValue(humanValue)) {
        return { value: humanValue, source: "human" };
      }

      // Then check AI data
      const aiValue = speciesQuery.data?.[aiField as keyof TreeSpecies] ??
                      researchQuery.data?.[aiField as keyof ResearchData];
      if (isValidValue(aiValue)) {
        return { value: aiValue, source: "ai" };
      }

      // Finally check legacy data (lowest priority)
      const legacyValue = speciesQuery.data?.[fieldName as keyof TreeSpecies];
      if (isValidValue(legacyValue)) {
        return { value: legacyValue, source: "legacy" };
      }

      return { value: null, source: null };
    },
    [speciesQuery.data, researchQuery.data]
  );

  // Helper to check if a specific field has been researched
  const isFieldResearched = useCallback(
    (fieldName: string): boolean => {
      const aiField = `${fieldName}_ai`;
      const humanField = `${fieldName}_human`;

      // Check if either AI or human data exists and is valid for this field
      const aiValue = speciesQuery.data?.[aiField as keyof TreeSpecies] ??
                      researchQuery.data?.[aiField as keyof ResearchData];
      const humanValue = speciesQuery.data?.[humanField as keyof TreeSpecies] ??
                         researchQuery.data?.[humanField as keyof ResearchData];

      return isValidValue(aiValue) || isValidValue(humanValue);
    },
    [speciesQuery.data, researchQuery.data]
  );

  // Helper to count researched fields by category
  const getResearchFieldCount = useCallback(() => {
    // Define the categories to check
    const categoryFields = {
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

    const counts: {
      total: number;
      byCategory: Record<string, number>;
    } = {
      total: 0,
      byCategory: {
        overview: 0,
        geographic: 0,
        ecological: 0,
        physical: 0,
        stewardship: 0
      }
    };

    // Check each category
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
    researchData: researchQuery.data,
    insightsMetadata: insightsQuery.data?.metadata || null,
    insights: insightsQuery.data?.insights || [],
    hasInsights: insightsQuery.data?.has_insights || false,
    isLoading: speciesQuery.isLoading || researchQuery.isLoading,
    isInsightsLoading: insightsQuery.isLoading,
    isError: speciesQuery.isError || researchQuery.isError,
    isResearched,
    getFieldValue,
    getInsightForField,
    getInsightsForField, // NEW: Returns array of all insights for atomic model
    isFieldResearched,
    getResearchFieldCount,
    refetchSpecies: speciesQuery.refetch,
    refetchResearch: researchQuery.refetch,
    refetchInsights: insightsQuery.refetch
  };
}