'use client';

import { Upload, File, X } from 'lucide-react';
import { useState, useCallback } from 'react';

interface FileDropzoneProps {
  onFilesSelected: (files: File[]) => void;
  accept?: string;
  maxFiles?: number;
  maxSize?: number; // in MB
  className?: string;
}

export default function FileDropzone({
  onFilesSelected,
  accept = '.csv',
  maxFiles = 10,
  maxSize = 32,
  className = '',
}: FileDropzoneProps) {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const validateFiles = (files: FileList): File[] | null => {
    const fileArray = Array.from(files);

    // Check file count
    if (fileArray.length > maxFiles) {
      setError(`Maximum ${maxFiles} files allowed`);
      return null;
    }

    // Check file size
    const oversizedFiles = fileArray.filter(
      (file) => file.size > maxSize * 1024 * 1024
    );
    if (oversizedFiles.length > 0) {
      setError(`Files must be smaller than ${maxSize}MB`);
      return null;
    }

    // Check file type
    const acceptedTypes = accept.split(',').map((t) => t.trim());
    const invalidFiles = fileArray.filter((file) => {
      const ext = '.' + file.name.split('.').pop()?.toLowerCase();
      return !acceptedTypes.includes(ext) && !acceptedTypes.includes(file.type);
    });
    if (invalidFiles.length > 0) {
      setError(`Only ${accept} files are allowed`);
      return null;
    }

    setError(null);
    return fileArray;
  };

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragActive(false);

      const files = validateFiles(e.dataTransfer.files);
      if (files) {
        setSelectedFiles(files);
        onFilesSelected(files);
      }
    },
    [onFilesSelected, maxFiles, maxSize, accept]
  );

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (e.target.files) {
      const files = validateFiles(e.target.files);
      if (files) {
        setSelectedFiles(files);
        onFilesSelected(files);
      }
    }
  };

  const removeFile = (index: number) => {
    const newFiles = selectedFiles.filter((_, i) => i !== index);
    setSelectedFiles(newFiles);
    onFilesSelected(newFiles);
  };

  return (
    <div className={className}>
      <div
        className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-colors ${
          dragActive
            ? 'border-emerald-500 bg-emerald-500/10'
            : 'border-white/20 bg-black/30 backdrop-blur-md hover:border-emerald-500/50'
        }`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <input
          type="file"
          id="file-upload"
          className="hidden"
          onChange={handleChange}
          accept={accept}
          multiple={maxFiles > 1}
        />
        <label
          htmlFor="file-upload"
          className="cursor-pointer flex flex-col items-center gap-4"
        >
          <Upload className="w-12 h-12 text-emerald-400" />
          <div>
            <p className="text-lg font-medium text-emerald-300 mb-2">
              Drop files here or click to browse
            </p>
            <p className="text-sm text-gray-400">
              {accept} files, max {maxFiles} files, {maxSize}MB each
            </p>
          </div>
        </label>
      </div>

      {error && (
        <div className="mt-4 p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      {selectedFiles.length > 0 && (
        <div className="mt-4 space-y-2">
          <h4 className="text-sm font-medium text-emerald-300 mb-2">
            Selected Files ({selectedFiles.length})
          </h4>
          {selectedFiles.map((file, index) => (
            <div
              key={index}
              className="flex items-center justify-between p-3 bg-black/30 backdrop-blur-md border border-white/20 rounded-lg"
            >
              <div className="flex items-center gap-3">
                <File className="w-5 h-5 text-emerald-400" />
                <div>
                  <p className="text-sm text-white font-medium">{file.name}</p>
                  <p className="text-xs text-gray-400">
                    {(file.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
              </div>
              <button
                onClick={() => removeFile(index)}
                className="p-1 hover:bg-red-500/20 rounded transition-colors"
              >
                <X className="w-5 h-5 text-red-400" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
