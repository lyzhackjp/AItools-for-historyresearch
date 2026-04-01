export const validateEmail = (email: string): boolean => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
};

export const validateApiKey = (key: string): boolean => {
  return key.length >= 10;
};

export const validateFileType = (filename: string, allowedTypes: string[]): boolean => {
  const extension = '.' + filename.split('.').pop()?.toLowerCase();
  return allowedTypes.some((type) => type.toLowerCase() === extension);
};

export const validateFileSize = (size: number, maxSizeMB: number): boolean => {
  const maxSizeBytes = maxSizeMB * 1024 * 1024;
  return size <= maxSizeBytes;
};

export const sanitizeFilename = (filename: string): string => {
  return filename.replace(/[^a-zA-Z0-9\u4e00-\u9fa5._-]/g, '_');
};

export const validateJson = (str: string): boolean => {
  try {
    JSON.parse(str);
    return true;
  } catch (error) {
    return false;
  }
};
