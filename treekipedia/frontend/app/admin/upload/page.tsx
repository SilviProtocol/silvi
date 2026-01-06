'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, Download, FileText, CheckCircle, AlertCircle } from 'lucide-react';
import FileDropzone from '../components/FileDropzone';

interface FieldDetection {
  [key: string]: string;
}

interface UploadResult {
  success: boolean;
  ontology_path?: string;
  field_detection?: FieldDetection;
  quality_score?: number;
  error?: string;
}

export default function UploadPage() {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);

  const handleFilesSelected = (files: File[]) => {
    setSelectedFiles(files);
    setResult(null); // Clear previous result
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0) {
      alert('Please select at least one CSV file');
      return;
    }

    setUploading(true);
    setResult(null);

    try {
      const formData = new FormData();
      selectedFiles.forEach((file) => {
        formData.append('files', file);
      });

      const response = await fetch('http://localhost:5001/api/admin/ontology/generate', {
        method: 'POST',
        body: formData,
      });

      const data: UploadResult = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Upload failed');
      }

      setResult(data);
    } catch (error) {
      console.error('Upload failed:', error);
      setResult({
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 via-emerald-950 to-gray-900">
      <div className="container mx-auto px-4 py-8 max-w-6xl">
        {/* Header */}
        <div className="mb-8">
          <Link
            href="/admin"
            className="flex items-center gap-2 text-emerald-400 hover:text-emerald-300 mb-4"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Admin
          </Link>
          <h1 className="text-4xl font-bold text-emerald-300 mb-2">
            CSV Ontology Generation
          </h1>
          <p className="text-gray-400">
            Upload CSV files to automatically generate OWL ontologies with field detection
          </p>
        </div>

        {/* Upload Section */}
        <div className="bg-black/30 backdrop-blur-md border border-white/20 rounded-xl p-6 mb-6">
          <h2 className="text-xl font-semibold text-emerald-300 mb-4">
            Upload CSV Files
          </h2>

          <FileDropzone
            onFilesSelected={handleFilesSelected}
            accept=".csv"
            maxFiles={10}
            maxSize={32}
            className="mb-6"
          />

          {selectedFiles.length > 0 && (
            <button
              onClick={handleUpload}
              disabled={uploading}
              className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <FileText className="w-5 h-5" />
              {uploading ? 'Generating Ontology...' : 'Generate Ontology'}
            </button>
          )}
        </div>

        {/* Results */}
        {result && (
          <div className="space-y-6">
            {/* Success/Error Message */}
            {result.success ? (
              <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-6">
                <div className="flex items-start gap-3 mb-4">
                  <CheckCircle className="w-6 h-6 text-emerald-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <h3 className="text-emerald-300 font-semibold mb-1">
                      Ontology Generated Successfully!
                    </h3>
                    <p className="text-sm text-gray-300">
                      Your OWL ontology has been generated from the CSV files.
                    </p>
                  </div>
                </div>

                {result.quality_score !== undefined && (
                  <div className="mt-4 p-4 bg-black/30 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-gray-300">Quality Score</span>
                      <span className="text-2xl font-bold text-emerald-300">
                        {result.quality_score.toFixed(1)}/100
                      </span>
                    </div>
                    <div className="w-full h-2 bg-black/40 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-emerald-500"
                        style={{ width: `${result.quality_score}%` }}
                      />
                    </div>
                  </div>
                )}

                {result.ontology_path && (
                  <button
                    onClick={() => window.open(result.ontology_path, '_blank')}
                    className="mt-4 flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition-colors"
                  >
                    <Download className="w-4 h-4" />
                    Download OWL File
                  </button>
                )}
              </div>
            ) : (
              <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6">
                <div className="flex items-start gap-3">
                  <AlertCircle className="w-6 h-6 text-red-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <h3 className="text-red-300 font-semibold mb-1">
                      Generation Failed
                    </h3>
                    <p className="text-sm text-gray-300">{result.error}</p>
                  </div>
                </div>
              </div>
            )}

            {/* Field Detection */}
            {result.field_detection && Object.keys(result.field_detection).length > 0 && (
              <div className="bg-black/30 backdrop-blur-md border border-white/20 rounded-xl p-6">
                <h2 className="text-xl font-semibold text-emerald-300 mb-4">
                  Detected Fields
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {Object.entries(result.field_detection).map(([field, type]) => (
                    <div
                      key={field}
                      className="flex items-center justify-between p-3 bg-black/40 border border-white/10 rounded-lg"
                    >
                      <span className="text-gray-300">{field}</span>
                      <span className="text-sm text-emerald-400 font-mono">{type}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Info Card */}
        <div className="mt-6 bg-blue-500/10 border border-blue-500/30 rounded-xl p-6">
          <h3 className="text-blue-300 font-semibold mb-2">
            How CSV Ontology Generation Works
          </h3>
          <ul className="text-sm text-gray-300 space-y-2">
            <li>• Automatically detects 120+ biodiversity field patterns (taxon_id, scientific_name, etc.)</li>
            <li>• Supports multiple CSV formats: direct schema, transposed, and MVP format</li>
            <li>• Generates OWL classes, properties, and instances</li>
            <li>• Creates relationships between fields based on detected patterns</li>
            <li>• Quality score based on field coverage and relationship accuracy</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
