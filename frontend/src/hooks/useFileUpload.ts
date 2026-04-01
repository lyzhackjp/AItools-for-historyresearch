import { useState, useCallback } from 'react';
import { message } from 'antd';
import { validateFileType, validateFileSize } from '../utils/validation';

export const useFileUpload = (
  accept: string[],
  maxSize: number,
  multiple: boolean = false
) => {
  const [files, setFiles] = useState<File[]>([]);
  const [error, setError] = useState<string>('');

  const validate = useCallback(
    (fileList: File[]): File[] => {
      const validFiles: File[] = [];

      for (const file of fileList) {
        if (!validateFileType(file.name, accept)) {
          setError(`不支持的文件格式: ${file.name}`);
          continue;
        }

        if (!validateFileSize(file.size, maxSize)) {
          setError(`文件大小超过限制: ${file.name} (最大 ${maxSize}MB)`);
          continue;
        }

        validFiles.push(file);
      }

      return validFiles;
    },
    [accept, maxSize]
  );

  const handleUpload = useCallback(
    (fileList: File[]) => {
      const validFiles = validate(fileList);
      if (validFiles.length > 0) {
        setFiles(multiple ? [...files, ...validFiles] : validFiles);
        setError('');
      }
    },
    [files, multiple, validate]
  );

  const clearFiles = useCallback(() => {
    setFiles([]);
    setError('');
  }, []);

  return {
    files,
    error,
    handleUpload,
    clearFiles,
    hasFiles: files.length > 0,
  };
};
