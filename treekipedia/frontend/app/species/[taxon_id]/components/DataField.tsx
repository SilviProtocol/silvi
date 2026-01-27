import React, { useState } from "react";
import { ChevronDown, ChevronUp, FlaskConical, CheckCircle2, ExternalLink, BookOpen, Info, Layers } from "lucide-react";
import { FieldDefinition } from "../hooks/useFieldDefinitions";
import { InsightDetail, InsightSource, ConfidenceBreakdown } from "@/lib/api";

interface DataFieldProps {
  field: FieldDefinition;
  getFieldValue: (fieldName: string) => { value: any; source: "human" | "ai" | "legacy" | null };
  isResearched: boolean;
  isFieldResearched: (fieldName: string) => boolean;
  insight?: InsightDetail | null;
  insights?: InsightDetail[]; // NEW: Array of atomic insights for this field
}

export function DataField({ field, getFieldValue, isResearched, isFieldResearched, insight, insights = [] }: DataFieldProps) {
  const [expanded, setExpanded] = useState(false);
  const [showSources, setShowSources] = useState(false);
  const [showAtomicInsights, setShowAtomicInsights] = useState(false);

  // Determine if this field has atomic insights
  const hasAtomicInsights = insights.length > 0;
  const hasMultipleInsights = insights.length > 1;
  const atomicInsightCount = insights.length;
  const { value: fieldValue, source: fieldSource } = getFieldValue(field.key);

  // Helper method to format values based on type
  const formatValue = (value: any, type?: string): React.ReactNode => {
    if (value === undefined || value === null || value === "" || value === "NA") {
      return null;
    }

    // Handle numeric values
    if (type === "numeric" && typeof value === "number") {
      return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
    }

    // Handle date values
    if (type === "date" && (typeof value === "string" || value instanceof Date)) {
      try {
        return new Date(value).toLocaleDateString();
      } catch (e) {
        return value;
      }
    }

    // Handle string values
    if (typeof value === "string") {
      if (field.isLongText && value.length > 300) {
        return expanded ? (
          <div>
            {value.split("\n").map((paragraph, i) => (
              <p key={i} className={i > 0 ? "mt-2" : ""}>
                {paragraph}
              </p>
            ))}
            <button
              onClick={(e) => {
                e.stopPropagation();
                setExpanded(false);
              }}
              className="mt-2 text-emerald-400 hover:text-emerald-300 flex items-center text-sm"
            >
              <ChevronUp className="w-4 h-4 mr-1" />
              Show Less
            </button>
          </div>
        ) : (
          <div>
            <p>{value.substring(0, 300)}...</p>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setExpanded(true);
              }}
              className="text-emerald-400 hover:text-emerald-300 flex items-center text-sm"
            >
              <ChevronDown className="w-4 h-4 mr-1" />
              Show More
            </button>
          </div>
        );
      }

      // For normal-sized text, just return it with newlines preserved
      return value.split("\n").map((paragraph, i) => (
        <p key={i} className={i > 0 ? "mt-2" : ""}>
          {paragraph}
        </p>
      ));
    }

    // For other types, just convert to string
    return String(value);
  };

  // If no data, don't render anything
  if (!fieldValue || fieldValue === "" || fieldValue === "NA") {
    return null;
  }

  const formattedValue = formatValue(fieldValue, field.type);

  // If formatValue returns null, don't render
  if (!formattedValue) {
    return null;
  }

  // Get confidence color
  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.85) return "text-emerald-400";
    if (confidence >= 0.70) return "text-amber-400";
    return "text-red-400";
  };

  const getConfidenceBgColor = (confidence: number) => {
    if (confidence >= 0.85) return "bg-emerald-500";
    if (confidence >= 0.70) return "bg-amber-500";
    return "bg-red-500";
  };

  // Get source label and styling
  const getSourceInfo = () => {
    if (fieldSource === "human") {
      return {
        label: "Verified",
        icon: <CheckCircle2 className="w-3.5 h-3.5" />,
        bgClass: "bg-emerald-900/30",
        borderClass: "border-emerald-500/40",
        textClass: "text-emerald-400",
        badgeBg: "bg-emerald-500/20",
      };
    } else if (fieldSource === "ai") {
      return {
        label: "Synthetic",
        icon: <FlaskConical className="w-3.5 h-3.5" />,
        bgClass: "bg-violet-900/20",
        borderClass: "border-violet-500/30",
        textClass: "text-violet-400",
        badgeBg: "bg-violet-500/20",
      };
    }
    return null;
  };

  const sourceInfo = getSourceInfo();
  const confidence = insight?.confidence;
  const sources = insight?.sources || [];

  // The main return for the component
  return (
    <div className={`p-3 rounded-xl border ${sourceInfo ? `${sourceInfo.bgClass} ${sourceInfo.borderClass}` : "bg-black/40 border-white/15"}`}>
      <div className="flex items-center justify-between mb-2">
        <h4 className="font-medium text-white/60">{field.label}</h4>
        <div className="flex items-center gap-2">
          {/* Per-field confidence indicator */}
          {confidence !== undefined && fieldSource === "ai" && (
            <div className="flex items-center gap-1.5">
              <div className="w-12 h-1.5 bg-black/40 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${getConfidenceBgColor(confidence)}`}
                  style={{ width: `${confidence * 100}%` }}
                />
              </div>
              <span className={`text-xs font-medium ${getConfidenceColor(confidence)}`}>
                {Math.round(confidence * 100)}%
              </span>
            </div>
          )}
          {/* Source badge */}
          {sourceInfo && (
            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${sourceInfo.badgeBg} ${sourceInfo.textClass}`}>
              {sourceInfo.icon}
              {sourceInfo.label}
            </span>
          )}
        </div>
      </div>

      {/* Display content */}
      <div className="text-white/85">
        {formattedValue}
      </div>

      {/* Atomic Insights Section - shows individual claims */}
      {hasAtomicInsights && fieldSource === "ai" && (
        <div className="mt-3 pt-2 border-t border-white/10">
          <button
            onClick={() => setShowAtomicInsights(!showAtomicInsights)}
            className="flex items-center gap-1.5 text-xs text-amber-400 hover:text-amber-300 transition-colors"
          >
            <Layers className="w-3.5 h-3.5" />
            <span>{atomicInsightCount} atomic insight{atomicInsightCount > 1 ? 's' : ''}</span>
            {showAtomicInsights ? (
              <ChevronUp className="w-3 h-3" />
            ) : (
              <ChevronDown className="w-3 h-3" />
            )}
          </button>

          {showAtomicInsights && (
            <div className="mt-2 space-y-2">
              {insights.map((atomicInsight, idx) => {
                // Extract text value from claim_value
                const claimValue = atomicInsight.claim_value;
                const displayText = typeof claimValue === 'string'
                  ? claimValue
                  : (claimValue as any)?.text || JSON.stringify(claimValue);
                const context = typeof claimValue === 'object' ? (claimValue as any)?.context : null;
                const region = typeof claimValue === 'object' ? (claimValue as any)?.region : null;

                return (
                  <div
                    key={idx}
                    className="p-2.5 rounded-lg bg-amber-900/15 border border-amber-500/20"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1">
                        <p className="text-sm text-white/85">{displayText}</p>
                        {(context || region) && (
                          <div className="flex items-center gap-2 mt-1 text-[10px] text-white/50">
                            {context && <span className="px-1.5 py-0.5 rounded bg-white/10">{context}</span>}
                            {region && <span className="px-1.5 py-0.5 rounded bg-white/10">{region}</span>}
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5 flex-shrink-0">
                        <div className="w-8 h-1.5 bg-black/40 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${getConfidenceBgColor(atomicInsight.confidence)}`}
                            style={{ width: `${atomicInsight.confidence * 100}%` }}
                          />
                        </div>
                        <span className={`text-[10px] font-medium ${getConfidenceColor(atomicInsight.confidence)}`}>
                          {Math.round(atomicInsight.confidence * 100)}%
                        </span>
                      </div>
                    </div>
                    {/* Per-insight sources */}
                    {atomicInsight.sources?.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {atomicInsight.sources.slice(0, 2).map((src, srcIdx) => (
                          <a
                            key={srcIdx}
                            href={src.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-black/30 hover:bg-black/50 text-violet-400 hover:text-violet-300"
                          >
                            <ExternalLink className="w-2.5 h-2.5" />
                            <span className="truncate max-w-[120px]">{src.title || 'Source'}</span>
                          </a>
                        ))}
                        {atomicInsight.sources.length > 2 && (
                          <span className="text-[10px] text-white/40">
                            +{atomicInsight.sources.length - 2} more
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Sources and Evidence section - only for AI/synthetic data without atomic insights */}
      {sources.length > 0 && fieldSource === "ai" && !hasAtomicInsights && (
        <div className="mt-3 pt-2 border-t border-white/10">
          <button
            onClick={() => setShowSources(!showSources)}
            className="flex items-center gap-1.5 text-xs text-violet-400 hover:text-violet-300 transition-colors"
          >
            <BookOpen className="w-3.5 h-3.5" />
            <span>{sources.length} source{sources.length > 1 ? 's' : ''}</span>
            {showSources ? (
              <ChevronUp className="w-3 h-3" />
            ) : (
              <ChevronDown className="w-3 h-3" />
            )}
          </button>

          {showSources && (
            <div className="mt-2 space-y-2">
              {/* Confidence Breakdown - if available */}
              {insight?.confidence_breakdown && (
                <div className="p-2 rounded-lg bg-violet-900/20 border border-violet-500/20">
                  <div className="flex items-center gap-1.5 text-[10px] text-violet-300 mb-1.5">
                    <Info className="w-3 h-3" />
                    <span className="font-medium">Evidence-Based Confidence</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-[10px]">
                    <div>
                      <div className="text-white/40">Sources</div>
                      <div className="text-white/80">
                        {insight.confidence_breakdown.source_count} ({insight.confidence_breakdown.source_diversity} types)
                      </div>
                    </div>
                    <div>
                      <div className="text-white/40">Source Score</div>
                      <div className={getConfidenceColor(insight.confidence_breakdown.source_score)}>
                        {Math.round(insight.confidence_breakdown.source_score * 100)}%
                      </div>
                    </div>
                    <div>
                      <div className="text-white/40">Agreement</div>
                      <div className={getConfidenceColor(insight.confidence_breakdown.agreement_score)}>
                        {Math.round(insight.confidence_breakdown.agreement_score * 100)}%
                      </div>
                    </div>
                  </div>
                  {insight.corroboration?.agreement_note && (
                    <div className="mt-1.5 text-[10px] text-white/50 italic">
                      {insight.corroboration.agreement_note}
                    </div>
                  )}
                </div>
              )}

              {/* Source list */}
              <div className="space-y-1.5">
                {sources.map((source: InsightSource, idx: number) => (
                  <a
                    key={idx}
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-start gap-2 p-2 rounded-lg bg-black/30 hover:bg-black/50 transition-colors group"
                  >
                    <ExternalLink className="w-3.5 h-3.5 mt-0.5 text-violet-400 group-hover:text-violet-300 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-xs text-white/80 truncate group-hover:text-white">
                        {source.title}
                      </div>
                      <div className="flex items-center gap-2 text-[10px] text-white/40">
                        <span className="capitalize">{source.type}</span>
                        <span>•</span>
                        <span className={getConfidenceColor(source.credibility)}>
                          {Math.round(source.credibility * 100)}% credibility
                        </span>
                      </div>
                    </div>
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
