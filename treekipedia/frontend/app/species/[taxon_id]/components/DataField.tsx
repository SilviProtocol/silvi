import React, { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { FieldDefinition } from "../hooks/useFieldDefinitions";

interface DataFieldProps {
  field: FieldDefinition;
  getFieldValue: (fieldName: string) => { value: any; source: "human" | "ai" | "legacy" | null };
  isResearched: boolean;
  isFieldResearched: (fieldName: string) => boolean;
}

export function DataField({ field, getFieldValue, isResearched, isFieldResearched }: DataFieldProps) {
  const [expanded, setExpanded] = useState(false);
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

  // The main return for the component
  return (
    <div className="p-3 rounded-xl bg-black/40 border border-white/15">
      <h4 className="font-medium text-white/60 mb-2">{field.label}:</h4>

      {/* Display content with source indicators */}
      <div className={`text-white/85 ${fieldSource === "ai" ? "bg-emerald-800/20 border-l-4 border-emerald-400 pl-3 py-1 rounded" : fieldSource === "human" ? "border-l-4 border-blue-400 pl-3 py-1 rounded" : ""}`}>
        {formattedValue}
      </div>
    </div>
  );
}