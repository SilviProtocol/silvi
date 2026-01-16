import React from "react";
import { TreeSpecies } from "@/lib/types";
import { InsightDetail } from "@/lib/api";
import { DataField } from "../DataField";
import { FieldDefinition } from "../../hooks/useFieldDefinitions";

interface ResearchDataTabProps {
  species: TreeSpecies;
  isResearched: boolean;
  getFieldValue: (fieldName: string) => { value: any; source: "human" | "ai" | "legacy" | null };
  getInsightForField: (fieldName: string) => InsightDetail | null;
  getInsightsForField: (fieldName: string) => InsightDetail[];
  fields: FieldDefinition[];
}

export function ResearchDataTab({ species, isResearched, getFieldValue, getInsightForField, getInsightsForField, fields }: ResearchDataTabProps) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold mb-4">Research & Data</h2>

        {/* Research info if IPFS CID is available */}
        {isResearched && species.ipfs_cid && species.ipfs_cid !== "" && species.ipfs_cid !== "NA" && (
          <div className="p-4 rounded-lg bg-emerald-900/20 border border-emerald-500/20 mb-4">
            <h3 className="font-semibold text-emerald-300 mb-2">Research Status</h3>
            <p className="text-white/80 mb-2">
              This species has been researched using our AI research process. The data has been stored
              permanently on IPFS and is available to everyone in the tree knowledge commons.
            </p>
            <div className="mt-4 text-sm">
              <span className="text-white/60">IPFS CID: </span>
              <a
                href={`https://ipfs.io/ipfs/${species.ipfs_cid}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-emerald-400 hover:text-emerald-300 break-all"
              >
                {species.ipfs_cid}
              </a>
            </div>
          </div>
        )}

        {/* Fields display */}
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