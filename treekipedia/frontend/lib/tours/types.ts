import type { DriveStep } from 'driver.js';

export type TourPageId =
  | 'search'
  | 'species'
  | 'analysis'
  | 'guide'
  | 'guide_detail'
  | 'about';

export type TourStep = DriveStep;
