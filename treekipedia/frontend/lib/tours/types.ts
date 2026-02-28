export type TourPageId =
  | 'search'
  | 'species'
  | 'analysis'
  | 'guide'
  | 'guide_detail'
  | 'about';

export interface TourStep {
  element?: string;
  popover?: {
    title: string;
    description: string;
    side?: string;
    align?: string;
  };
}
