import type { TourPageId, TourStep } from './types';
import { searchTourSteps } from './search-tour';
import { speciesTourSteps } from './species-tour';
import { analysisTourSteps } from './analysis-tour';
import { guideTourSteps } from './guide-tour';
import { guideDetailTourSteps } from './guide-detail-tour';
import { aboutTourSteps } from './about-tour';

const tourRegistry: Record<TourPageId, TourStep[]> = {
  search: searchTourSteps,
  species: speciesTourSteps,
  analysis: analysisTourSteps,
  guide: guideTourSteps,
  guide_detail: guideDetailTourSteps,
  about: aboutTourSteps,
};

export function getTourSteps(pageId: string): TourStep[] {
  return tourRegistry[pageId as TourPageId] || [];
}

export function getPageIdFromPathname(pathname: string): TourPageId | null {
  if (pathname === '/' || pathname === '/search') return 'search';
  if (pathname.startsWith('/species/')) return 'species';
  if (pathname === '/analysis') return 'analysis';
  if (pathname === '/guide') return 'guide';
  if (pathname.startsWith('/guide/')) return 'guide_detail';
  if (pathname === '/about') return 'about';
  return null;
}
