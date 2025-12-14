import React, { useState } from "react";
import { TreeSpecies } from "@/lib/types";
import { parseSemicolonList, truncateList } from "@/utils/speciesDataHelpers";
import { Bug, Flower, Bird, Skull } from "lucide-react";

interface EcologicalInteractionsProps {
  species: TreeSpecies;
}

interface InteractionCategory {
  key: keyof TreeSpecies;
  label: string;
  icon: React.ReactNode;
  color: string;
}

export function EcologicalInteractions({ species }: EcologicalInteractionsProps) {
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());

  const toggleCategory = (key: string) => {
    const newSet = new Set(expandedCategories);
    if (newSet.has(key)) {
      newSet.delete(key);
    } else {
      newSet.add(key);
    }
    setExpandedCategories(newSet);
  };

  // Define interaction categories with icons (unified emerald theme)
  const categories: InteractionCategory[] = [
    {
      key: "globi_eatenby",
      label: "Herbivores",
      icon: <Bug className="w-4 h-4" />,
      color: "text-emerald-400"
    },
    {
      key: "globi_pollinatedby",
      label: "Pollinators",
      icon: <Flower className="w-4 h-4" />,
      color: "text-emerald-400"
    },
    {
      key: "globi_flowersvisitedby",
      label: "Flower Visitors",
      icon: <Flower className="w-4 h-4" />,
      color: "text-emerald-400"
    },
    {
      key: "globi_hasdispersalvector",
      label: "Seed Dispersers",
      icon: <Bird className="w-4 h-4" />,
      color: "text-emerald-400"
    },
    {
      key: "globi_hasparasite",
      label: "Parasites",
      icon: <Skull className="w-4 h-4" />,
      color: "text-red-400"
    },
    {
      key: "globi_haspathogen",
      label: "Pathogens",
      icon: <Skull className="w-4 h-4" />,
      color: "text-red-400"
    },
    {
      key: "globi_preyeduponby",
      label: "Predators",
      icon: <Bug className="w-4 h-4" />,
      color: "text-red-400"
    },
    {
      key: "globi_hasparasitoid",
      label: "Parasitoids",
      icon: <Skull className="w-4 h-4" />,
      color: "text-red-400"
    }
  ];

  // Parse interactions for each category
  const interactions = categories.map(category => {
    const speciesList = parseSemicolonList(species[category.key] as string);
    const { visible, remaining } = truncateList(speciesList, 5);
    return {
      ...category,
      species: speciesList,
      visible,
      remaining
    };
  }).filter(interaction => interaction.species.length > 0); // Only show categories with data

  if (interactions.length === 0) {
    return null; // No interaction data available
  }

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-white">
        Ecological Interactions
      </h3>
      <p className="text-sm text-white/60">
        Data from the Global Biotic Interactions Database (GloBI)
      </p>

      <div className="space-y-3">
        {interactions.map((interaction) => {
          const isExpanded = expandedCategories.has(interaction.key);
          const displayList = isExpanded ? interaction.species : interaction.visible;

          return (
            <div
              key={interaction.key}
              className="p-4 rounded-xl bg-black/40 border border-white/15"
            >
              <div className="flex items-center justify-between mb-3">
                <h4 className={`font-medium flex items-center gap-2 ${interaction.color}`}>
                  {interaction.icon}
                  {interaction.label}
                  <span className="text-white/60 text-sm font-normal">
                    ({interaction.species.length} species)
                  </span>
                </h4>
              </div>

              <ul className="space-y-1.5">
                {displayList.map((speciesName, idx) => (
                  <li
                    key={idx}
                    className="text-sm text-white/85 italic pl-4 before:content-['•'] before:mr-2 before:text-white/40"
                  >
                    {speciesName}
                  </li>
                ))}
              </ul>

              {interaction.remaining > 0 && (
                <button
                  onClick={() => toggleCategory(interaction.key)}
                  className="mt-3 text-sm text-emerald-400 hover:text-emerald-300 transition-colors"
                >
                  {isExpanded
                    ? 'Show less'
                    : `Show ${interaction.remaining} more species`}
                </button>
              )}
            </div>
          );
        })}
      </div>

      <p className="text-xs text-white/40 mt-4">
        Source:{' '}
        <a
          href="https://www.globalbioticinteractions.org/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-emerald-400 hover:text-emerald-300 underline"
        >
          Global Biotic Interactions Database (GloBI)
        </a>
      </p>
    </div>
  );
}
