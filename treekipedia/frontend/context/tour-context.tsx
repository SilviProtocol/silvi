'use client';

import React, { createContext, useContext, useCallback, useRef, useEffect, useMemo } from 'react';
import { driver, type Driver } from 'driver.js';
import 'driver.js/dist/driver.css';
import { getTourSteps } from '@/lib/tours';
import { tourStyles } from '@/lib/tours/styles';

const STORAGE_PREFIX = 'treekipedia_tour_seen_';

interface TourContextValue {
  startTour: (pageId: string) => void;
  stopTour: () => void;
  hasSeenTour: (pageId: string) => boolean;
  markTourAsSeen: (pageId: string) => void;
  resetTour: (pageId: string) => void;
  autoStartTour: (pageId: string) => void;
}

const TourContext = createContext<TourContextValue | undefined>(undefined);

export function TourProvider({ children }: { children: React.ReactNode }) {
  const driverRef = useRef<Driver | null>(null);
  const currentPageRef = useRef<string | null>(null);
  const autoStartedRef = useRef<Set<string>>(new Set());
  const safetyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Inject custom styles once on mount
  useEffect(() => {
    const style = document.createElement('style');
    style.textContent = tourStyles;
    document.head.appendChild(style);
    return () => {
      style.remove();
    };
  }, []);

  const hasSeenTour = useCallback((pageId: string): boolean => {
    if (typeof window === 'undefined') return true;
    return localStorage.getItem(`${STORAGE_PREFIX}${pageId}`) === 'true';
  }, []);

  const markTourAsSeen = useCallback((pageId: string) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(`${STORAGE_PREFIX}${pageId}`, 'true');
    }
  }, []);

  const stopTour = useCallback(() => {
    document.documentElement.classList.remove('driver-active');
    if (safetyTimerRef.current) {
      clearTimeout(safetyTimerRef.current);
      safetyTimerRef.current = null;
    }
    if (driverRef.current) {
      try { driverRef.current.destroy(); } catch (_) {}
      driverRef.current = null;
    }
    currentPageRef.current = null;
  }, []);

  const startTour = useCallback((pageId: string) => {
    // Prevent starting if already running
    if (driverRef.current) {
      try { driverRef.current.destroy(); } catch (_) {}
      driverRef.current = null;
    }
    if (safetyTimerRef.current) {
      clearTimeout(safetyTimerRef.current);
      safetyTimerRef.current = null;
    }

    const tourSteps = getTourSteps(pageId);
    if (tourSteps.length === 0) return;

    // Filter steps whose targets don't exist in the DOM
    const validSteps = tourSteps.filter((step) => {
      if (typeof step.element === 'string') {
        return document.querySelector(step.element) !== null;
      }
      return true;
    });

    if (validSteps.length === 0) return;

    currentPageRef.current = pageId;

    // Lock page scroll to prevent driver.js scrollIntoView from crashing the browser
    document.documentElement.classList.add('driver-active');

    try {
      const driverObj = driver({
        animate: false,
        overlayColor: 'rgb(0, 0, 0)',
        overlayOpacity: 0.75,
        stagePadding: 12,
        stageRadius: 12,
        allowClose: true,
        smoothScroll: false,
        allowKeyboardControl: true,
        showProgress: true,
        progressText: '{{current}} of {{total}}',
        showButtons: ['next', 'previous', 'close'],
        nextBtnText: 'Next →',
        prevBtnText: '← Back',
        doneBtnText: 'Done ✓',
        popoverClass: 'treekipedia-tour',
        popoverOffset: 14,
        steps: validSteps,
        onDestroyed: () => {
          document.documentElement.classList.remove('driver-active');
          if (safetyTimerRef.current) {
            clearTimeout(safetyTimerRef.current);
            safetyTimerRef.current = null;
          }
          if (currentPageRef.current) {
            markTourAsSeen(currentPageRef.current);
          }
          driverRef.current = null;
          currentPageRef.current = null;
        },
      });

      driverRef.current = driverObj;

      // Safety timeout: auto-destroy tour after 2 minutes to prevent memory leaks
      safetyTimerRef.current = setTimeout(() => {
        document.documentElement.classList.remove('driver-active');
        if (driverRef.current) {
          try { driverRef.current.destroy(); } catch (_) {}
          driverRef.current = null;
          currentPageRef.current = null;
        }
      }, 120000);

      driverObj.drive();
    } catch (err) {
      console.error('Tour failed to start:', err);
      document.documentElement.classList.remove('driver-active');
      driverRef.current = null;
      currentPageRef.current = null;
    }
  }, [markTourAsSeen]);

  // Safe auto-start that only fires once per page per session
  const autoStartTour = useCallback((pageId: string) => {
    if (autoStartedRef.current.has(pageId)) return;
    if (typeof window === 'undefined') return;
    if (localStorage.getItem(`${STORAGE_PREFIX}${pageId}`) === 'true') return;

    autoStartedRef.current.add(pageId);

    // Delay to let the page fully render before starting
    setTimeout(() => {
      startTour(pageId);
    }, 1500);
  }, [startTour]);

  const resetTour = useCallback((pageId: string) => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem(`${STORAGE_PREFIX}${pageId}`);
      autoStartedRef.current.delete(pageId);
    }
  }, []);

  const contextValue = useMemo<TourContextValue>(() => ({
    startTour,
    stopTour,
    hasSeenTour,
    markTourAsSeen,
    resetTour,
    autoStartTour,
  }), [startTour, stopTour, hasSeenTour, markTourAsSeen, resetTour, autoStartTour]);

  return (
    <TourContext.Provider value={contextValue}>
      {children}
    </TourContext.Provider>
  );
}

export function useTour() {
  const context = useContext(TourContext);
  if (context === undefined) {
    throw new Error('useTour must be used within a TourProvider');
  }
  return context;
}
