import React from "react";
import { TreeSpecies, Insight } from "@/lib/types";
import { DataField } from "../DataField";
import { FieldDefinition } from "../../hooks/useFieldDefinitions";
import { ConservationStatus } from "../display/ConservationStatus";
import { EcologicalInteractions } from "../EcologicalInteractions";

interface EcologicalTabProps {
  species: TreeSpecies;
  isResearched: boolean;
  getFieldValue: (fieldName: string) => { value: any; source: "human" | "ai" | "legacy" | null };
  getFieldInsights?: (fieldName: string) => Insight[];
  fields: FieldDefinition[];
}

export function EcologicalTab({ species, isResearched, getFieldValue, getFieldInsights, fields }: EcologicalTabProps) {
  // Find conservation status field for special treatment
  const conservationStatusField = fields.find(f => f.key === "conservation_status");
  const { value: conservationStatus, source: conservationSource } =
    conservationStatusField ? getFieldValue("conservation_status") : { value: null, source: null };

  return (
    <div className="space-y-6">
      {/* Ecological Characteristics */}
      <div>
        <h2 className="text-xl font-semibold mb-4">Ecological Characteristics</h2>

        {/* Highlight conservation status if available */}
        {conservationStatus && conservationStatus !== "" && conservationStatus !== "NA" && (
          <div className="mb-4">
            <h3 className="text-lg font-semibold mb-3">Conservation Status</h3>
            <ConservationStatus status={conservationStatus} source={conservationSource} />
          </div>
        )}

        {/* Fields display - skip conservation status as it's handled above */}
        <div className="space-y-3">
          {fields.filter(f => f.key !== "conservation_status").map((field) => (
            <DataField
              key={field.key}
              field={field}
              getFieldValue={getFieldValue}
              isResearched={isResearched}
              isFieldResearched={(fieldName) => {
                const { value } = getFieldValue(fieldName);
                return !!value;
              }}
            />
          ))}
        </div>
      </div>

      {/* Ecological Interactions Section */}
      <EcologicalInteractions species={species} />
    </div>
  );
}