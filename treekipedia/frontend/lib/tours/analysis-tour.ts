import type { TourStep } from './types';

export const analysisTourSteps: TourStep[] = [
  {
    popover: {
      title: 'Welcome to GIS Analysis! 🗺️',
      description: "This is your spatial analysis toolkit. Draw areas on the map, upload boundary files, switch map layers, and discover which tree species thrive in any region on Earth.",
      side: 'over',
      align: 'center',
    },
  },
  {
    element: '[data-tour="analysis-header"]',
    popover: {
      title: 'Drawing Tools 🖊️',
      description: "On the left side of the map you'll find drawing tools. Use the pentagon to draw a custom polygon, the square for a rectangle, or the pencil/trash to edit and delete shapes. Once drawn, species analysis runs automatically!",
      side: 'bottom',
      align: 'start',
    },
  },
  {
    element: '[data-tour="upload-kml"]',
    popover: {
      title: 'Upload KML Files',
      description: "Already have boundary data from Google Earth or QGIS? Click here to upload a KML file and analyze species within those boundaries automatically.",
      side: 'left',
      align: 'start',
    },
  },
  {
    element: '[data-tour="map-layers"]',
    popover: {
      title: 'Map Layers Panel',
      description: "Switch between 6 base map styles (Dark Mode, Satellite, Topographic, and more) and overlay data like Ecoregion boundaries, Intact Forests, and live Occurrence Heatmaps.",
      side: 'left',
      align: 'start',
    },
  },
  {
    popover: {
      title: "You're All Set! 🎉",
      description: "Click anywhere on the map for instant AI species predictions, draw a polygon for area analysis, or upload a KML file. Results appear in floating panels on the left. The help button (bottom-left) has a quick reference too. Happy mapping!",
      side: 'over',
      align: 'center',
    },
  },
];
