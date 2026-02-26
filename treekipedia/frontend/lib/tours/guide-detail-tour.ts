import type { TourStep } from './types';

export const guideDetailTourSteps: TourStep[] = [
  {
    element: '[data-tour="ecoregion-header"]',
    popover: {
      title: 'Your Ecoregion Guide 🌱',
      description: "Here's the full reforestation guide for this ecoregion — biome, realm, area, countries, and the total number of LEAF-scored species all at a glance.",
      side: 'bottom',
      align: 'center',
    },
  },
  {
    element: '[data-tour="quick-jump"]',
    popover: {
      title: 'Quick Navigation',
      description: "Use these links to jump to any section — Overview, Top Species, All Species, Planting Strategy, Climate, Conservation, and Methodology. Everything you need for planning.",
      side: 'bottom',
      align: 'start',
    },
  },
  {
    element: '[data-tour="top-species"]',
    popover: {
      title: 'Top Recommended Species ⭐',
      description: "These are the highest-ranked species for this ecoregion. Each card shows the LEAF score, native status, height, and an AI-generated description. Click any species to see its full profile.",
      side: 'top',
      align: 'center',
    },
  },
  {
    element: '[data-tour="all-species"]',
    popover: {
      title: 'All Species by Tier',
      description: "Every scored species organized into tiers: BEST (score 90+), GOOD (70+), ACCEPTABLE (50+), and LOW. Pick the right trees for your reforestation project based on ecological suitability.",
      side: 'top',
      align: 'center',
    },
  },
];
