"use client";

import { useEffect } from "react";
import { SearchForm } from "@/components/search-form";
import { useTour } from "@/context/tour-context";

export default function SearchPage() {
  const { autoStartTour } = useTour();

  useEffect(() => {
    autoStartTour('search');
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <section className="relative w-full min-h-[calc(100vh-80px)] flex items-center justify-center">
      <div className="container relative z-10 px-4 md:px-6 mx-auto">
        <div className="flex flex-col items-center justify-center space-y-8 text-center">
          {/* Logo and Subtitle Group */}
          <div className="flex flex-col items-center" data-tour="search-hero">
            <img
              src="/treekipedialogo.svg"
              alt="Treekipedia"
              className="h-[90px] text-silvi-mint filter brightness-100 saturate-0 mb-2"
              style={{ filter: 'brightness(0) saturate(100%) invert(98%) sepia(5%) saturate(401%) hue-rotate(53deg) brightness(103%) contrast(94%)' }}
            />

            {/* Subtitle directly below logo with minimal spacing */}
            <div className="max-w-3xl">
              <h1 className="text-4xl font-bold tracking-tighter">
                <span className="bg-clip-text text-transparent bg-gradient-to-r from-emerald-300 via-green-200 to-teal-300 animate-gradient-x">
                  The Tree Intelligence Commons
                </span>
              </h1>
            </div>
          </div>

          {/* Search bar with more separation */}
          <div className="w-full max-w-2xl mt-6">
            <SearchForm />
          </div>
        </div>
      </div>
    </section>
  );
}
