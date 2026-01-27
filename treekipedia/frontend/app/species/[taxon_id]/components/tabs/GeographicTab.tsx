import React from "react";
import { TreeSpecies, Insight } from "@/lib/types";
import { DataField } from "../DataField";
import { FieldDefinition } from "../../hooks/useFieldDefinitions";
import { ClimateProfile } from "../ClimateProfile";

interface GeographicTabProps {
  species: TreeSpecies;
  isResearched: boolean;
  getFieldValue: (fieldName: string) => { value: any; source: "human" | "ai" | "legacy" | null };
  getFieldInsights?: (fieldName: string) => Insight[];
  fields: FieldDefinition[];
}

export function GeographicTab({ species, isResearched, getFieldValue, getFieldInsights, fields }: GeographicTabProps) {
  return (
    <div className="space-y-6">
      {/* Geographic Distribution Fields */}
      <div>
        <h2 className="text-xl font-semibold mb-4">Geographic Distribution</h2>
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
              insights={getFieldInsights?.(field.key)}
            />
          ))}
        </div>
      </div>

      {/* Climate Profile Section */}
      <ClimateProfile species={species} />
    </div>
  );
}