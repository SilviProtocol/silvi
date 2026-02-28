'use client';

import React, { createContext, useContext, useCallback, useRef, useMemo, useState, useEffect } from 'react';
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
  currentStep: number;
  totalSteps: number;
  currentStepData: StepData | null;
  nextStep: () => void;
  prevStep: () => void;
  isRunning: boolean;
}

interface StepData {
  title: string;
  description: string;
  rect: DOMRect | null; // null = centered popover (no element)
}

const TourContext = createContext<TourContextValue | undefined>(undefined);

export function TourProvider({ children }: { children: React.ReactNode }) {
  const [isRunning, setIsRunning] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [totalSteps, setTotalSteps] = useState(0);
  const [currentStepData, setCurrentStepData] = useState<StepData | null>(null);
  const stepsRef = useRef<any[]>([]);
  const pageIdRef = useRef<string | null>(null);
  const autoStartedRef = useRef<Set<string>>(new Set());

  // Inject styles
  useEffect(() => {
    const style = document.createElement('style');
    style.textContent = tourStyles;
    document.head.appendChild(style);
    return () => { style.remove(); };
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

  const showStep = useCallback((index: number) => {
    const steps = stepsRef.current;
    if (index < 0 || index >= steps.length) return;

    const step = steps[index];
    let rect: DOMRect | null = null;

    if (typeof step.element === 'string') {
      const el = document.querySelector(step.element);
      if (el) {
        rect = el.getBoundingClientRect();
      }
    }

    setCurrentStep(index);
    setCurrentStepData({
      title: step.popover?.title || '',
      description: step.popover?.description || '',
      rect,
    });
  }, []);

  const stopTour = useCallback(() => {
    if (pageIdRef.current) {
      markTourAsSeen(pageIdRef.current);
    }
    setIsRunning(false);
    setCurrentStepData(null);
    setCurrentStep(0);
    setTotalSteps(0);
    stepsRef.current = [];
    pageIdRef.current = null;
  }, [markTourAsSeen]);

  const nextStep = useCallback(() => {
    const next = currentStep + 1;
    if (next >= stepsRef.current.length) {
      stopTour();
    } else {
      showStep(next);
    }
  }, [currentStep, showStep, stopTour]);

  const prevStep = useCallback(() => {
    if (currentStep > 0) {
      showStep(currentStep - 1);
    }
  }, [currentStep, showStep]);

  const startTour = useCallback((pageId: string) => {
    const tourSteps = getTourSteps(pageId);
    if (tourSteps.length === 0) return;

    // Filter to only steps with existing DOM elements
    const validSteps = tourSteps.filter((step) => {
      if (typeof step.element === 'string') {
        return document.querySelector(step.element) !== null;
      }
      return true; // steps with no element (centered popovers) are always valid
    });

    if (validSteps.length === 0) return;

    stepsRef.current = validSteps;
    pageIdRef.current = pageId;
    setTotalSteps(validSteps.length);
    setIsRunning(true);
    showStep(0);
  }, [showStep]);

  const autoStartTour = useCallback((pageId: string) => {
    if (autoStartedRef.current.has(pageId)) return;
    if (typeof window === 'undefined') return;
    if (localStorage.getItem(`${STORAGE_PREFIX}${pageId}`) === 'true') return;

    autoStartedRef.current.add(pageId);
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
    currentStep,
    totalSteps,
    currentStepData,
    nextStep,
    prevStep,
    isRunning,
  }), [startTour, stopTour, hasSeenTour, markTourAsSeen, resetTour, autoStartTour, currentStep, totalSteps, currentStepData, nextStep, prevStep, isRunning]);

  return (
    <TourContext.Provider value={contextValue}>
      {children}
      {isRunning && currentStepData && (
        <TourOverlay
          step={currentStepData}
          current={currentStep}
          total={totalSteps}
          onNext={nextStep}
          onPrev={prevStep}
          onClose={stopTour}
        />
      )}
    </TourContext.Provider>
  );
}

// ---- Overlay + Popover rendered as a portal-free React component ----

function TourOverlay({
  step,
  current,
  total,
  onNext,
  onPrev,
  onClose,
}: {
  step: StepData;
  current: number;
  total: number;
  onNext: () => void;
  onPrev: () => void;
  onClose: () => void;
}) {
  const isLast = current === total - 1;
  const isFirst = current === 0;
  const hasElement = step.rect !== null;

  // Spotlight cutout style
  const cutout = hasElement && step.rect ? {
    top: step.rect.top - 8,
    left: step.rect.left - 8,
    width: step.rect.width + 16,
    height: step.rect.height + 16,
  } : null;

  // Position popover near the highlighted element or center it
  const popoverStyle: React.CSSProperties = hasElement && step.rect
    ? {
        position: 'fixed',
        top: step.rect.bottom + 16,
        left: Math.max(16, Math.min(step.rect.left, window.innerWidth - 420)),
        zIndex: 10002,
      }
    : {
        position: 'fixed',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        zIndex: 10002,
      };

  // If popover would go below viewport, show it above the element
  if (hasElement && step.rect && step.rect.bottom + 250 > window.innerHeight) {
    popoverStyle.top = Math.max(16, step.rect.top - 16);
    (popoverStyle as any).transform = 'translateY(-100%)';
  }

  return (
    <>
      {/* Dark overlay with cutout */}
      <div
        style={{ position: 'fixed', inset: 0, zIndex: 10000, pointerEvents: 'none' }}
      >
        <svg width="100%" height="100%" style={{ position: 'absolute', inset: 0 }}>
          <defs>
            <mask id="tour-mask">
              <rect width="100%" height="100%" fill="white" />
              {cutout && (
                <rect
                  x={cutout.left}
                  y={cutout.top}
                  width={cutout.width}
                  height={cutout.height}
                  rx={12}
                  fill="black"
                />
              )}
            </mask>
          </defs>
          <rect
            width="100%"
            height="100%"
            fill="rgba(0,0,0,0.75)"
            mask="url(#tour-mask)"
          />
        </svg>
      </div>

      {/* Clickable backdrop to close */}
      <div
        onClick={onClose}
        style={{ position: 'fixed', inset: 0, zIndex: 10001, cursor: 'pointer' }}
      />

      {/* Popover */}
      <div
        className="treekipedia-tour-popover"
        style={popoverStyle}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="tour-close-btn"
        >
          ×
        </button>

        <div className="tour-title">{step.title}</div>
        <div className="tour-description">{step.description}</div>

        <div className="tour-footer">
          <span className="tour-progress">{current + 1} of {total}</span>
          <div className="tour-nav-btns">
            {!isFirst && (
              <button onClick={onPrev} className="tour-btn-back">
                ← Back
              </button>
            )}
            <button onClick={onNext} className="tour-btn-next">
              {isLast ? 'Done ✓' : 'Next →'}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

export function useTour() {
  const context = useContext(TourContext);
  if (context === undefined) {
    throw new Error('useTour must be used within a TourProvider');
  }
  return context;
}
