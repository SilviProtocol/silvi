import type { TourStep } from './types';

export const aboutTourSteps: TourStep[] = [
  {
    element: '[data-tour="about-header"]',
    popover: {
      title: 'About Treekipedia 🌳',
      description: "This page tells the story of the Tree Intelligence Commons — why it exists, how it works, and where it's headed. Let's take a quick look at the highlights.",
      side: 'bottom',
      align: 'center',
    },
  },
  {
    element: '[data-tour="about-overview"]',
    popover: {
      title: 'The Mission',
      description: "Treekipedia is an open-source project by Silvi to consolidate fragmented tree knowledge into one unified, AI-enhanced database — accessible to researchers, tree stewards, and citizen scientists worldwide.",
      side: 'top',
      align: 'center',
    },
  },
  {
    element: '[data-tour="about-how-it-works"]',
    popover: {
      title: 'How It Works ⚙️',
      description: "Five simple steps: Search for species, discover knowledge gaps, request AI research, get deep multi-language analysis from global databases, and earn Tree Points for your contributions.",
      side: 'top',
      align: 'center',
    },
  },
  {
    element: '[data-tour="about-tech"]',
    popover: {
      title: 'Technical Infrastructure',
      description: "Built on PostgreSQL + PostGIS with Claude AI powering deep research across GBIF, IUCN, POWO, and grey literature in multiple languages. All data has full provenance tracking.",
      side: 'top',
      align: 'center',
    },
  },
  {
    element: '[data-tour="about-data"]',
    popover: {
      title: 'The Data Foundation',
      description: "25M+ raw records from 10+ global databases, distilled into 50,000+ unique species with 50+ attributes each. This is the backbone of the Tree Intelligence Commons.",
      side: 'top',
      align: 'center',
    },
  },
];
