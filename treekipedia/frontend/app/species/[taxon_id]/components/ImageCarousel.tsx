import React, { useState, useCallback, useEffect } from "react";
import { ChevronLeft, ChevronRight, ExternalLink, Info, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SpeciesImage } from "@/lib/types";
import { useSpeciesImages } from "../hooks/useSpeciesImages";

interface ImageCarouselProps {
  taxonId: string;
}

export function ImageCarousel({ taxonId }: ImageCarouselProps) {
  const { images, imageCount, isLoading, isError, hasImages } = useSpeciesImages(taxonId);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [showAttribution, setShowAttribution] = useState(false);
  const [imageLoading, setImageLoading] = useState(true);

  const currentImage = images[currentIndex];

  // Close attribution overlay when image changes
  useEffect(() => {
    setShowAttribution(false);
  }, [currentIndex]);

  const nextImage = useCallback(() => {
    if (images.length > 0) {
      setCurrentIndex((prev) => (prev + 1) % images.length);
      setImageLoading(true);
    }
  }, [images.length]);

  const prevImage = useCallback(() => {
    if (images.length > 0) {
      setCurrentIndex((prev) => (prev - 1 + images.length) % images.length);
      setImageLoading(true);
    }
  }, [images.length]);

  const goToImage = useCallback((index: number) => {
    setCurrentIndex(index);
    setImageLoading(true);
  }, []);

  const handleImageLoad = () => {
    setImageLoading(false);
  };

  const handleImageError = () => {
    setImageLoading(false);
  };

  // Don't render anything if loading or no images
  if (isLoading) {
    return (
      <div className="rounded-xl bg-black/40 backdrop-blur-md border border-white/15 p-4 h-64 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-emerald-300" />
      </div>
    );
  }

  if (isError || !hasImages) {
    // Return nothing if no images - graceful fallback
    return null;
  }

  return (
    <div className="rounded-xl bg-black/40 backdrop-blur-md border border-white/15 overflow-hidden">
        {/* Main Image Display */}
        <div className="relative h-64 md:h-80 lg:h-96 bg-black/50">
          {/* Loading overlay */}
          {imageLoading && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/50 z-10">
              <Loader2 className="w-8 h-8 animate-spin text-emerald-300" />
            </div>
          )}

          {/* Main Image */}
          {currentImage && (
            <img
              src={currentImage.image_url}
              alt={`Species image ${currentIndex + 1} of ${imageCount}`}
              className="w-full h-full object-cover"
              onLoad={handleImageLoad}
              onError={handleImageError}
            />
          )}

          {/* Navigation Controls */}
          {images.length > 1 && (
            <>
              <Button
                onClick={prevImage}
                variant="outline"
                size="sm"
                className="absolute left-2 top-1/2 transform -translate-y-1/2 bg-black/60 backdrop-blur-md border-white/15 text-white hover:bg-black/80 p-2"
              >
                <ChevronLeft className="w-4 h-4" />
              </Button>
              <Button
                onClick={nextImage}
                variant="outline"
                size="sm"
                className="absolute right-2 top-1/2 transform -translate-y-1/2 bg-black/60 backdrop-blur-md border-white/15 text-white hover:bg-black/80 p-2"
              >
                <ChevronRight className="w-4 h-4" />
              </Button>
            </>
          )}

          {/* Image Counter */}
          <div className="absolute top-2 right-2 bg-black/50 backdrop-blur-md rounded-lg px-3 py-1 text-white text-sm">
            {currentIndex + 1} / {imageCount}
          </div>

          {/* Attribution Toggle */}
          <Button
            onClick={() => setShowAttribution(!showAttribution)}
            variant="outline"
            size="sm"
            className="absolute bottom-2 right-2 bg-black/60 backdrop-blur-md border-white/15 text-white hover:bg-black/80 p-2"
          >
            <Info className="w-4 h-4" />
          </Button>

          {/* Attribution Overlay */}
          {showAttribution && currentImage && (
            <div className="absolute bottom-0 left-0 right-0 bg-black/80 backdrop-blur-md text-white p-4">
              <div className="text-sm space-y-1">
                {currentImage.photographer && (
                  <div>
                    <span className="text-white/70">Photo by:</span>{" "}
                    <span
                      dangerouslySetInnerHTML={{ __html: currentImage.photographer }}
                      className="text-white"
                    />
                  </div>
                )}
                {currentImage.license && (
                  <div>
                    <span className="text-white/70">License:</span>{" "}
                    <span className="text-white">{currentImage.license}</span>
                  </div>
                )}
                <div>
                  <span className="text-white/70">Source:</span>{" "}
                  <span className="text-white">{currentImage.source}</span>
                  {currentImage.page_url && (
                    <a
                      href={currentImage.page_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="ml-2 inline-flex items-center text-emerald-300 hover:text-emerald-200 transition-colors"
                    >
                      <ExternalLink className="w-3 h-3 ml-1" />
                    </a>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Thumbnail Navigation */}
        {images.length > 1 && (
          <div className="p-3 bg-black/20">
            <div className="flex gap-2 overflow-x-auto">
              {images.map((image, index) => (
                <button
                  key={image.id}
                  onClick={() => goToImage(index)}
                  className={`flex-shrink-0 w-16 h-16 rounded border-2 overflow-hidden transition-all ${
                    index === currentIndex
                      ? "border-emerald-400 opacity-100"
                      : "border-white/15 opacity-70 hover:opacity-100"
                  }`}
                >
                  <img
                    src={image.image_url}
                    alt={`Thumbnail ${index + 1}`}
                    className="w-full h-full object-cover"
                  />
                  {image.is_primary && (
                    <div className="absolute top-0 right-0 bg-emerald-500 text-white text-xs px-1 rounded-bl">
                      ★
                    </div>
                  )}
                </button>
              ))}
            </div>
          </div>
        )}
    </div>
  );
}