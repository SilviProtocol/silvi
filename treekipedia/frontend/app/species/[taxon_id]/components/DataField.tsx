import React, { useState } from "react";
import { ChevronDown, ChevronUp, FlaskConical, ExternalLink, BookOpen } from "lucide-react";
import { FieldDefinition } from "../hooks/useFieldDefinitions";
import { InsightDetail, InsightSource } from "@/lib/api";

interface DataFieldProps {
  field: FieldDefinition;
  getFieldValue: (fieldName: string) => { value: any; source: "human" | "ai" | "legacy" | null };
  isResearched: boolean;
  isFieldResearched: (fieldName: string) => boolean;
  insight?: InsightDetail | null;
  insights?: InsightDetail[];
}

export function DataField({ field, getFieldValue, isResearched, isFieldResearched, insight, insights = [] }: DataFieldProps) {
  const [expanded, setExpanded] = useState(false);
  const [showSources, setShowSources] = useState(false);

  const hasInsights = insights.length > 0;
  const { value: fieldValue, source: fieldSource } = getFieldValue(field.key);

  const formatValue = (value: any, type?: string): React.ReactNode => {
    if (value === undefined || value === null || value === "" || value === "NA") {
      return null;
    }

    if (type === "numeric" && typeof value === "number") {
      return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
    }

    if (type === "date" && (typeof value === "string" || value instanceof Date)) {
      try {
        return new Date(value).toLocaleDateString();
      } catch (e) {
        return value;
      }
    }

    if (typeof value === "string") {
      if (field.isLongText && value.length > 300) {
        return expanded ? (
          <div>
            {value.split("\n").map((paragraph, i) => (
              <p key={i} className={i > 0 ? "mt-2" : ""}>{paragraph}</p>
            ))}
            <button
              onClick={(e) => { e.stopPropagation(); setExpanded(false); }}
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
              onClick={(e) => { e.stopPropagation(); setExpanded(true); }}
              className="text-emerald-400 hover:text-emerald-300 flex items-center text-sm"
            >
              <ChevronDown className="w-4 h-4 mr-1" />
              Show More
            </button>
          </div>
        );
      }

      return value.split("\n").map((paragraph, i) => (
        <p key={i} className={i > 0 ? "mt-2" : ""}>{paragraph}</p>
      ));
    }

    return String(value);
  };

  if (!fieldValue || fieldValue === "" || fieldValue === "NA") {
    return null;
  }

  const formattedValue = formatValue(fieldValue, field.type);
  if (!formattedValue) {
    return null;
  }

  // Confidence colors — emerald with opacity scaling
  // Higher confidence = more opaque, lower = more transparent
  const getConfidenceOpacity = (confidence: number) => {
    if (confidence >= 0.90) return "opacity-100";
    if (confidence >= 0.80) return "opacity-80";
    if (confidence >= 0.70) return "opacity-60";
    return "opacity-40";
  };

  const getConfidenceColor = (confidence: number) => {
    return `text-emerald-400 ${getConfidenceOpacity(confidence)}`;
  };

  const getConfidenceBgColor = (confidence: number) => {
    return `bg-emerald-500 ${getConfidenceOpacity(confidence)}`;
  };

  const isAI = fieldSource === "ai";
  const containerClass = isAI
    ? "p-3 rounded-xl bg-black/40 backdrop-blur-md border border-emerald-500/25"
    : "p-3 rounded-xl bg-black/40 backdrop-blur-md border border-white/10";

  // Aggregate confidence: average across all insights for this field, or fallback to single insight
  const confidence = hasInsights
    ? insights.reduce((sum, i) => sum + (i.confidence || 0), 0) / insights.length
    : insight?.confidence;

  // Collect all sources from insights for the sources toggle
  const allSources: InsightSource[] = hasInsights
    ? insights.flatMap(i => i.sources || [])
    : (insight?.sources || []);

  return (
    <div className={containerClass}>
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <h4 className="font-medium text-white/60">{field.label}</h4>
        <div className="flex items-center gap-2">
          {confidence !== undefined && isAI && (
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
          {isAI && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-500/15 text-emerald-400">
              <FlaskConical className="w-3.5 h-3.5" />
              AI
            </span>
          )}
        </div>
      </div>

      {/* Content: if AI with multiple insights, show each claim; otherwise show synthesized value */}
      {hasInsights && isAI && insights.length > 1 ? (
        <div className="space-y-2">
          {insights.map((ins, idx) => {
            const claimValue = ins.claim_value;
            // Extract display text from claim_value variants:
            // {text: "..."} for text claims, {value: N, unit: "..."} for numeric, or plain string
            let displayText: string;
            if (typeof claimValue === 'string') {
              displayText = claimValue;
            } else if (typeof claimValue === 'object' && claimValue !== null) {
              const cv = claimValue as Record<string, any>;
              if (cv.text) {
                displayText = cv.text;
              } else if (cv.value !== undefined) {
                displayText = cv.unit ? `${cv.value} ${cv.unit}` : String(cv.value);
              } else {
                displayText = String(fieldValue);
              }
            } else {
              displayText = String(claimValue);
            }
            const context = typeof claimValue === 'object' ? (claimValue as any)?.context : null;
            const region = typeof claimValue === 'object' ? (claimValue as any)?.region : null;

            return (
              <div key={idx} className="flex items-start justify-between gap-2">
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
                      className={`h-full rounded-full ${getConfidenceBgColor(ins.confidence)}`}
                      style={{ width: `${ins.confidence * 100}%` }}
                    />
                  </div>
                  <span className={`text-[10px] font-medium ${getConfidenceColor(ins.confidence)}`}>
                    {Math.round(ins.confidence * 100)}%
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-white/85">
          {formattedValue}
        </div>
      )}

      {/* Sources toggle — for AI fields */}
      {allSources.length > 0 && isAI && (
        <div className="mt-3 pt-2 border-t border-white/10">
          <button
            onClick={() => setShowSources(!showSources)}
            className="flex items-center gap-1.5 text-xs text-emerald-400/70 hover:text-emerald-400 transition-colors"
          >
            <BookOpen className="w-3.5 h-3.5" />
            <span>{allSources.length} source{allSources.length > 1 ? 's' : ''}</span>
            {showSources ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>

          {showSources && (
            <div className="mt-2 space-y-1.5">
              {allSources.map((source: InsightSource, idx: number) => (
                <a
                  key={idx}
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-start gap-2 p-2 rounded-lg bg-black/30 hover:bg-black/50 transition-colors group"
                >
                  <ExternalLink className="w-3.5 h-3.5 mt-0.5 text-emerald-400/70 group-hover:text-emerald-400 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="text-xs text-white/80 truncate group-hover:text-white">
                      {source.title || 'Source'}
                    </div>
                    {source.type && (
                      <div className="flex items-center gap-2 text-[10px] text-white/40">
                        <span className="capitalize">{source.type}</span>
                        {source.credibility && (
                          <>
                            <span>•</span>
                            <span className={getConfidenceColor(source.credibility)}>
                              {Math.round(source.credibility * 100)}% credibility
                            </span>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                </a>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
