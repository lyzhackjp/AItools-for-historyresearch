export interface FileUploaderProps {
  accept: string[];
  maxSize: number;
  multiple?: boolean;
  onUpload: (files: File[]) => void;
  onError: (error: string) => void;
  disabled?: boolean;
  className?: string;
}

export interface ResultViewerProps {
  result: any;
  type: 'polish' | 'ocr' | 'ner' | 'note';
  onExport?: (format: string) => void;
  onDownload?: () => void;
}

export interface ApiKeyManagerProps {
  onKeyAdded?: (provider: string) => void;
  onKeyRemoved?: (provider: string) => void;
  onProviderSwitched?: (provider: string) => void;
}

export interface PromptEditorProps {
  moduleId: string;
  promptId: string;
  onSave?: (content: string) => void;
  readOnly?: boolean;
}

export interface StepIndicatorProps {
  current: number;
  total: number;
  labels?: string[];
}

export interface OCREngineSelectorProps {
  value: string;
  onChange: (value: string) => void;
  options: Array<{
    value: string;
    label: string;
    desc: string;
    recommended?: boolean;
  }>;
}
