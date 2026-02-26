import type { TourStep } from './types';

export const speciesTourSteps: TourStep[] = [
  {
    element: '[data-tour="species-header"]',
    popover: {
      title: 'Species Profile 🌿',
      description: "You're looking at a full tree species profile — scientific name, common names, taxonomy, and all the ecological data we've gathered from global databases. Let's explore what's here.",
      side: 'bottom',
      align: 'start',
    },
  },
  {
    element: '[data-tour="tab-navigation"]',
    popover: {
      title: 'Six Data Categories',
      description: "Everything is organized into tabs: Overview (quick facts & taxonomy), Geographic (native regions & climate), Ecological (habitat & biome), Physical (height, growth form), Stewardship (planting tips), and Research Data (raw AI output).",
      side: 'bottom',
      align: 'center',
    },
  },
  {
    element: '[data-tour="research-button"]',
    popover: {
      title: 'AI-Powered Research ✨',
      description: "This is the magic button! Click it to queue this species for deep AI research. Our system scans GBIF, IUCN, POWO and grey literature in multiple languages, then synthesizes comprehensive ecological data with full provenance tracking.",
      side: 'bottom',
      align: 'start',
    },
  },
  {
    element: '[data-tour="back-to-search"]',
    popover: {
      title: 'Navigate Back',
      description: "Jump back to search anytime to explore more species. You can also use the nav bar above. Happy exploring!",
      side: 'bottom',
      align: 'start',
    },
  },
];
