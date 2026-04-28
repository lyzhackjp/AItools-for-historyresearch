import { useState } from 'react';

export function useFileUpload() {
  const [files, setFiles] = useState<File[]>([]);

  return {
    files,
    clearFiles: () => setFiles([]),
    setFiles,
  };
}
