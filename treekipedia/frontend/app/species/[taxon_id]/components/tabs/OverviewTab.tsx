import React from "react";
import { Leaf } from "lucide-react";
import { TreeSpecies, Insight } from "@/lib/types";
import { DataField } from "../DataField";
import { FieldDefinition } from "../../hooks/useFieldDefinitions";
import { SubspeciesSection } from "../SubspeciesSection";
import { SpeciesInfobox } from "../SpeciesInfobox";
import { InsightField } from "../InsightField";

interface OverviewTabProps {
  species: TreeSpecies;
  isResearched: boolean;
  getFieldValue: (fieldName: string) => { value: any; source: "human" | "ai" | "legacy" | null };
  getFieldInsights?: (fieldName: string) => Insight[];
  fields: FieldDefinition[];
}

export function OverviewTab({ species, isResearched, getFieldValue, getFieldInsights, fields }: OverviewTabProps) {
  // Get general description field
  const generalDescriptionField = fields.find(
    (field) => field.key === "general_description"
  );

  // Get other taxonomy fields
  const taxonomyFields = fields.filter(
    (field) => field.key !== "species_scientific_name" && 
               field.key !== "common_name" && 
               field.key !== "general_description"
  );

  // Get description data
  const { value: descriptionValue, source: descriptionSource } = generalDescriptionField
    ? getFieldValue("general_description")
    : { value: null, source: null };

  return (
    <div className="space-y-6">
      {/* Quick Facts Infobox */}
      <SpeciesInfobox species={species} />

      {/* General Description - Special treatment */}
      {descriptionValue && descriptionValue !== "" && descriptionValue !== "NA" && (
        <div>
          <h2 className="text-xl font-semibold mb-4 flex items-center">
            <Leaf className="w-5 h-5 mr-2 text-green-400" />
            General Description
          </h2>
          <div className="p-4 rounded-xl bg-black/40 backdrop-blur-md border border-white/15">
            <div
              className={`text-white/85 leading-relaxed ${
                descriptionSource === "ai"
                  ? "bg-emerald-800/20 border-l-4 border-emerald-400 pl-3 py-1 rounded"
                  : descriptionSource === "human"
                  ? "border-l-4 border-blue-400 pl-3 py-1 rounded"
                  : ""
              }`}
            >
              {typeof descriptionValue === "string" &&
                descriptionValue.split("\n").map((paragraph, idx) => (
                  <p key={idx} className={idx > 0 ? "mt-2" : ""}>
                    {paragraph}
                  </p>
                ))}
            </div>
          </div>
        </div>
      )}

      {/* Taxonomy Information */}
      <div>
        <h2 className="text-xl font-semibold mb-4">Taxonomy & Classification</h2>
        <div className="space-y-3">
          {taxonomyFields.map((field) => (
            <DataField
              key={field.key}
              field={field}
              getFieldValue={getFieldValue}
              isResearched={isResearched}
              isFieldResearched={() => true} // These fields aren't researched
            />
          ))}
        </div>
      </div>

      {/* Subspecies & Varieties Section */}
      <SubspeciesSection taxonId={species.taxon_id} />
    </div>
  );
}