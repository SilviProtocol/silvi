import React from "react";
import { Insight } from "@/lib/types";

interface InsightItemProps {
  insight: Insight;
}

/**
 * Get confidence bar color based on confidence level
 * - emerald (≥70%): High confidence
 * - amber (50-70%): Medium confidence
 * - red (<50%): Low confidence
 */
function getConfidenceColor(confidence: number): {
  bar: string;
  text: string;
} {
  if (confidence >= 0.7) {
    return { bar: "bg-emerald-500", text: "text-emerald-400" };
  } else if (confidence >= 0.5) {
    return { bar: "bg-amber-500", text: "text-amber-400" };
  } else {
    return { bar: "bg-red-500", text: "text-red-400" };
  }
}

/**
 * Extract display text from insight claim_value
 */
function getInsightText(insight: Insight): string {
  const { claim_value } = insight;

  if (claim_value.text) {
    return claim_value.text;
  }

  if (claim_value.value !== undefined) {
    const unit = claim_value.unit || "";
    return `${claim_value.value}${unit ? ` ${unit}` : ""}`;
  }

  return JSON.stringify(claim_value);
}

/**
 * InsightItem - Displays a single insight with confidence bar
 *
 * Design:
 * - Emerald left border indicating AI-generated
 * - Content text
 * - Small confidence bar + percentage (right-aligned)
 */
export function InsightItem({ insight }: InsightItemProps) {
  const confidence = insight.confidence || 0;
  const confidencePercent = Math.round(confidence * 100);
  const colors = getConfidenceColor(confidence);
  const text = getInsightText(insight);

  return (
    <div className="relative pl-3 py-2 border-l-2 border-emerald-500">
      {/* Insight text */}
      <div className="text-white/85 pr-24">
        {text.split("\n").map((paragraph, idx) => (
          <p key={idx} className={idx > 0 ? "mt-2" : ""}>
            {paragraph}
          </p>
        ))}
      </div>

      {/* Confidence indicator (right-aligned) */}
      <div className="absolute right-0 top-2 flex items-center gap-2">
        {/* Confidence bar */}
        <div className="w-16 h-1.5 bg-white/20 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${colors.bar}`}
            style={{ width: `${confidencePercent}%` }}
          />
        </div>
        {/* Percentage */}
        <span className={`text-xs font-medium ${colors.text} w-8 text-right`}>
          {confidencePercent}%
        </span>
      </div>
    </div>
  );
}
