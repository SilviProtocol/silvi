'use client';

import { useState, useRef } from 'react';
import { analyzePlot } from '@/lib/api';
import { PlotAnalysisResponse, GeoJSONPolygon } from '@/lib/types';

interface FileUploadProps {
  onAnalysisComplete: (results: PlotAnalysisResponse) => void;
  onAnalysisError: (error: string) => void;
  onLoadingChange: (loading: boolean) => void;
}

// Simple KML to GeoJSON converter
function parseKMLToGeoJSON(kmlContent: string): GeoJSONPolygon[] {
  console.log('Starting KML parsing...');
  const parser = new DOMParser();
  const xmlDoc = parser.parseFromString(kmlContent, 'text/xml');

  // Check for parsing errors
  const parseError = xmlDoc.querySelector('parsererror');
  if (parseError) {
    console.error('KML parsing error:', parseError.textContent);
    throw new Error('Invalid KML file format');
  }

  const polygons: GeoJSONPolygon[] = [];

  // Find all Polygon elements (handles both direct Polygon and MultiGeometry > Polygon)
  const polygonElements = xmlDoc.getElementsByTagName('Polygon');
  console.log(`Found ${polygonElements.length} Polygon elements`);

  for (let i = 0; i < polygonElements.length; i++) {
    const polygon = polygonElements[i];

    // Find coordinates - try multiple paths for different KML structures
    // Structure: Polygon > outerBoundaryIs > LinearRing > coordinates
    let coordinatesElement = polygon.querySelector('outerBoundaryIs LinearRing coordinates');

    // Fallback: direct coordinates child
    if (!coordinatesElement) {
      coordinatesElement = polygon.querySelector('outerBoundaryIs coordinates');
    }
    if (!coordinatesElement) {
      coordinatesElement = polygon.querySelector('coordinates');
    }

    if (coordinatesElement) {
      const coordinatesText = coordinatesElement.textContent?.trim();
      if (coordinatesText) {
        try {
          // Parse coordinates - KML format is "lon,lat,alt lon,lat,alt ..." or newline-separated
          const coordPairs = coordinatesText.split(/[\s\n]+/).filter(pair => pair.trim());
          const coordinates: number[][] = [];

          for (const pair of coordPairs) {
            const parts = pair.split(',');
            if (parts.length >= 2) {
              const lon = parseFloat(parts[0]);
              const lat = parseFloat(parts[1]);
              if (!isNaN(lon) && !isNaN(lat)) {
                coordinates.push([lon, lat]);
              }
            }
          }

          // Ensure the polygon is closed
          if (coordinates.length > 0) {
            const first = coordinates[0];
            const last = coordinates[coordinates.length - 1];
            if (first[0] !== last[0] || first[1] !== last[1]) {
              coordinates.push([...first]);
            }
          }

          if (coordinates.length >= 4) { // Minimum for a valid polygon
            polygons.push({
              type: 'Polygon',
              coordinates: [coordinates]
            });
          }
        } catch (error) {
          console.warn('Failed to parse coordinates for polygon:', error);
        }
      }
    } else {
      console.warn(`Polygon ${i} has no coordinates element`);
    }
  }

  console.log(`Successfully parsed ${polygons.length} polygons`);

  if (polygons.length === 0) {
    throw new Error('No valid polygons found in KML file');
  }

  return polygons;
}

export default function FileUpload({ onAnalysisComplete, onAnalysisError, onLoadingChange }: FileUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelection = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.kml')) {
      onAnalysisError('Please select a KML file');
      return;
    }

    try {
      onLoadingChange(true);
      setUploadedFile(file.name);

      // Read file content
      const content = await file.text();
      
      // Parse KML to GeoJSON
      const polygons = parseKMLToGeoJSON(content);
      
      if (polygons.length === 0) {
        throw new Error('No polygons found in KML file');
      }

      // For now, use the first polygon found
      const geometry = polygons[0];
      
      // Analyze the plot
      const results = await analyzePlot(geometry);
      onAnalysisComplete(results);
      
    } catch (error) {
      console.error('KML processing error:', error);
      onAnalysisError(error instanceof Error ? error.message : 'Failed to process KML file');
      setUploadedFile(null);
    } finally {
      onLoadingChange(false);
    }
  };

  const handleFileInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      handleFileSelection(file);
    }
  };

  const handleDrop = (event: React.DragEvent) => {
    event.preventDefault();
    setIsDragging(false);
    
    const file = event.dataTransfer.files[0];
    if (file) {
      handleFileSelection(file);
    }
  };

  const handleDragOver = (event: React.DragEvent) => {
    event.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (event: React.DragEvent) => {
    event.preventDefault();
    setIsDragging(false);
  };

  const openFileSelector = () => {
    fileInputRef.current?.click();
  };

  const clearFile = () => {
    setUploadedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="space-y-4">
      {/* File drop zone */}
      <div
        className={`
          border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors backdrop-blur-md
          ${isDragging 
            ? 'border-emerald-400 bg-emerald-600/20' 
            : 'border-white/30 hover:border-emerald-400/40 bg-black/20'
          }
        `}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={openFileSelector}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".kml"
          onChange={handleFileInputChange}
          className="hidden"
        />
        
        {uploadedFile ? (
          <div className="space-y-2">
            <div className="text-emerald-400">
              <svg className="w-8 h-8 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <p className="text-sm font-medium text-white">{uploadedFile}</p>
            <button
              onClick={(e) => {
                e.stopPropagation();
                clearFile();
              }}
              className="text-xs text-white/70 hover:text-white"
            >
              Clear file
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            <div className="text-white/60">
              <svg className="w-8 h-8 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
            </div>
            <p className="text-white/80">
              <span className="font-medium">Click to upload</span> or drag and drop
            </p>
            <p className="text-xs text-white/60">KML files only</p>
          </div>
        )}
      </div>

      {/* File info */}
      <div className="text-xs text-white/60 space-y-1">
        <p>• KML files should contain polygon boundaries</p>
        <p>• Multiple polygons supported (first will be analyzed)</p>
        <p>• File size limit: 10MB</p>
      </div>
    </div>
  );
}