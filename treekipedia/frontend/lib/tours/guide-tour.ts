import type { TourStep } from './types';

export const guideTourSteps: TourStep[] = [
  {
    element: '[data-tour="guide-header"]',
    popover: {
      title: 'Ecoregion Guides 🌍',
      description: "Welcome to the reforestation guides! We've built planting guides for 847 One Earth ecoregions, each with species ranked by how well they fit the local ecology using LEAF scoring.",
      side: 'bottom',
      align: 'center',
    },
  },
  {
    element: '[data-tour="guide-search"]',
    popover: {
      title: 'Find Your Ecoregion',
      description: 'Type the name of any ecoregion — like "Appalachian", "Borneo", or "Sahel" — and matching results appear instantly with biome, realm, and area info. Click one to see its full guide.',
      side: 'bottom',
      align: 'center',
    },
  },
  {
    element: '[data-tour="guide-info-cards"]',
    popover: {
      title: 'How It Works',
      description: "LEAF scoring ranks species using GBIF occurrence data and WCVP native status. AI Research synthesizes planting strategies from global literature. All 847 ecoregions are covered with full species rankings.",
      side: 'top',
      align: 'center',
    },
  },
];
