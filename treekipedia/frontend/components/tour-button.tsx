'use client';

import { HelpCircle } from 'lucide-react';
import { usePathname } from 'next/navigation';
import { useTour } from '@/context/tour-context';
import { getPageIdFromPathname } from '@/lib/tours';

export function TourButton() {
  const pathname = usePathname();
  const { startTour, resetTour } = useTour();

  const pageId = getPageIdFromPathname(pathname);

  // Don't render on pages without tours
  if (!pageId) return null;

  const handleClick = () => {
    resetTour(pageId);
    setTimeout(() => {
      startTour(pageId);
    }, 150);
  };

  return (
    <button
      onClick={handleClick}
      className="fixed bottom-6 right-6 z-[9999] group flex items-center gap-2.5 pl-4 pr-5 py-3 rounded-full text-white font-semibold shadow-lg transition-all duration-300 hover:scale-105 hover:shadow-[0_0_30px_rgba(16,185,129,0.35)]"
      style={{
        background: 'linear-gradient(135deg, rgba(16,185,129,0.85) 0%, rgba(5,150,105,0.9) 100%)',
        border: '1px solid rgba(110,231,183,0.3)',
        backdropFilter: 'blur(12px)',
      }}
      aria-label="Take a tour of this page"
    >
      <HelpCircle className="w-[18px] h-[18px] transition-transform duration-300 group-hover:rotate-12" />
      <span className="text-sm font-semibold tracking-wide">Take a Tour</span>
    </button>
  );
}
