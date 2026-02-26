import type { TourStep } from './types';

export const searchTourSteps: TourStep[] = [
  {
    popover: {
      title: 'Welcome to Treekipedia! 🌳',
      description: "Hey there! Let us show you around the Tree Intelligence Commons — one of the world's largest open-source tree knowledge databases with 67,743+ species. This'll only take a minute.",
      side: 'over',
      align: 'center',
    },
  },
  {
    element: '[data-tour="search-form"]',
    popover: {
      title: 'Search for Any Tree 🔍',
      description: "Type any tree name — common or scientific — and smart suggestions pop up instantly. You'll see both common names and scientific names side by side. Click a result to see its full species profile.",
      side: 'bottom',
      align: 'center',
    },
  },
  {
    element: '[data-tour="nav-analysis"]',
    popover: {
      title: 'GIS Analysis Tool',
      description: "Head here to explore an interactive map where you can draw polygons, upload KML files, switch between satellite/terrain views, and discover which species thrive in any area on Earth.",
      side: 'bottom',
      align: 'start',
    },
  },
  {
    element: '[data-tour="nav-guide"]',
    popover: {
      title: 'Ecoregion Guides 🌍',
      description: "Explore reforestation guides for 847 ecoregions worldwide. Each guide has LEAF-ranked species recommendations and AI-synthesized planting strategies tailored to the local ecology.",
      side: 'bottom',
      align: 'start',
    },
  },
  {
    element: '[data-tour="wallet-button"]',
    popover: {
      title: 'Connect Your Wallet 💳',
      description: "Got a Web3 wallet? Connect it to unlock future features like contributing data, sponsoring research, and earning Tree Points on the Treederboard. Happy exploring!",
      side: 'bottom',
      align: 'end',
    },
  },
];
