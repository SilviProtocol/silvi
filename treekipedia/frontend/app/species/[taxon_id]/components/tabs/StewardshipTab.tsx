import React from "react";
import { TreeSpecies } from "@/lib/types";
import { InsightDetail } from "@/lib/api";
import { DataField } from "../DataField";
import { FieldDefinition } from "../../hooks/useFieldDefinitions";

interface StewardshipTabProps {
  species: TreeSpecies;
  isResearched: boolean;
  getFieldValue: (fieldName: string) => { value: any; source: "human" | "ai" | "legacy" | null };
  getInsightForField: (fieldName: string) => InsightDetail | null;
  getInsightsForField: (fieldName: string) => InsightDetail[];
  fields: FieldDefinition[];
}

export function StewardshipTab({ species, isResearched, getFieldValue, getInsightForField, getInsightsForField, fields }: StewardshipTabProps) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold mb-4">Stewardship & Utility</h2>
        <div className="space-y-3">
          {fields.map((field) => (
            <DataField
              key={field.key}
              field={field}
              getFieldValue={getFieldValue}
              isResearched={isResearched}
              isFieldResearched={(fieldName) => {
                const { value } = getFieldValue(fieldName);
                return !!value;
              }}
              insight={getInsightForField(field.key)}
              insights={getInsightsForField(field.key)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
