import React from "react";
import { TreeSpecies, Insight } from "@/lib/types";
import { DataField } from "../DataField";
import { FieldDefinition } from "../../hooks/useFieldDefinitions";

interface StewardshipTabProps {
  species: TreeSpecies;
  isResearched: boolean;
  getFieldValue: (fieldName: string) => { value: any; source: "human" | "ai" | "legacy" | null };
  getFieldInsights?: (fieldName: string) => Insight[];
  fields: FieldDefinition[];
}

export function StewardshipTab({ species, isResearched, getFieldValue, getFieldInsights, fields }: StewardshipTabProps) {
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
              insights={getFieldInsights?.(field.key)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}