import React, { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Insight } from "@/lib/types";
import { InsightItem } from "./InsightItem";

interface InsightFieldProps {
  label: string;
  insights: Insight[];
  maxVisible?: number;
}

/**
 * InsightField - Displays a field with multiple insights
 *
 * Features:
 * - Shows top N insights (default 3) sorted by confidence
 * - "Show X more insights" button when overflow exists
 * - Insights displayed with confidence bars
 */
export function InsightField({
  label,
  insights,
  maxVisible = 3,
}: InsightFieldProps) {
  const [expanded, setExpanded] = useState(false);

  // If no insights, don't render
  if (!insights || insights.length === 0) {
    return null;
  }

  // Sort by confidence (should already be sorted, but ensure)
  const sortedInsights = [...insights].sort(
    (a, b) => (b.confidence || 0) - (a.confidence || 0)
  );

  const visibleInsights = expanded
    ? sortedInsights
    : sortedInsights.slice(0, maxVisible);

  const hasMore = sortedInsights.length > maxVisible;
  const hiddenCount = sortedInsights.length - maxVisible;

  return (
    <div className="p-3 rounded-xl bg-black/40 border border-white/15">
      {/* Field label */}
      <h4 className="font-medium text-white/60 mb-3">{label}:</h4>

      {/* Insights list */}
      <div className="space-y-2">
        {visibleInsights.map((insight, index) => (
          <InsightItem key={insight.id || index} insight={insight} />
        ))}
      </div>

      {/* Show more/less button */}
      {hasMore && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-3 text-sm text-emerald-400 hover:text-emerald-300 flex items-center transition-colors"
        >
          {expanded ? (
            <>
              <ChevronUp className="w-4 h-4 mr-1" />
              Show less
            </>
          ) : (
            <>
              <ChevronDown className="w-4 h-4 mr-1" />
              Show {hiddenCount} more insight{hiddenCount !== 1 ? "s" : ""}
            </>
          )}
        </button>
      )}
    </div>
  );
}
