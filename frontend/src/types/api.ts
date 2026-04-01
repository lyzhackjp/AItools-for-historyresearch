export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

export interface ApiError {
  code: string;
  message: string;
  details?: any;
}

export interface UploadResponse {
  fileId: string;
  filename: string;
  size: number;
  url?: string;
}

export interface PolishRequest {
  file: File;
  strategy: 'quick' | 'deep' | 'custom';
  language: 'zh' | 'ja' | 'en';
  preserveFormatting?: boolean;
}

export interface OCRRequest {
  file: File;
  engine: 'tesseract' | 'ndlocr-lite' | 'ndlkotenocr-lite' | 'qwen-vl-ocr';
  language?: string;
  options?: {
    dpi?: number;
    removeWatermark?: boolean;
    extractPageNumbers?: boolean;
  };
}

export interface NERRequest {
  text: string;
  entityTypes?: string[];
  language?: 'zh' | 'ja';
}

export interface NoteGenerationRequest {
  sourceText: string;
  template?: string;
  format?: 'markdown' | 'obsidian';
  extractEntities?: boolean;
}

export interface ResearchRequest {
  message: string;
  conversationId?: string;
  context?: string[];
}

export interface PromptUpdateRequest {
  moduleId: string;
  promptId: string;
  content: string;
}
