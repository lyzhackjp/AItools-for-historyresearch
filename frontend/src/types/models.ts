export interface ApiKeyConfig {
  key: string;
  createdAt: number;
  lastUsed?: number;
}

export interface UserPreferences {
  fontSize: 'normal' | 'large' | 'extra-large';
  highContrast: boolean;
  language: 'zh-CN' | 'en-US' | 'ja-JP';
}

export interface TaskStatus {
  id: string;
  type: 'polish' | 'ocr' | 'ner' | 'note' | 'research';
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  createdAt: number;
  updatedAt: number;
  result?: any;
  error?: string;
}

export interface FileInfo {
  name: string;
  size: number;
  type: string;
  path?: string;
}

export interface PolishResult {
  originalText: string;
  polishedText: string;
  changes: Array<{
    type: 'grammar' | 'style' | 'clarity';
    original: string;
    suggested: string;
    explanation: string;
  }>;
  statistics: {
    totalChanges: number;
    grammarFixes: number;
    styleImprovements: number;
    clarityEnhancements: number;
  };
}

export interface OCRResult {
  pages: Array<{
    pageNumber: number;
    text: string;
    confidence: number;
    processingTime: number;
  }>;
  metadata: {
    totalPages: number;
    totalCharacters: number;
    averageConfidence: number;
    processingTime: number;
    engine: string;
  };
}

export interface Entity {
  id: string;
  text: string;
  type: 'person' | 'location' | 'event' | 'organization' | 'concept';
  confidence: number;
  context: string;
  position: {
    start: number;
    end: number;
  };
}

export interface NERResult {
  entities: Entity[];
  statistics: {
    totalEntities: number;
    byType: Record<string, number>;
    averageConfidence: number;
  };
}

export interface Note {
  id: string;
  title: string;
  content: string;
  tags: string[];
  entities: Entity[];
  source: string;
  createdAt: number;
  updatedAt: number;
}

export interface ResearchMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  metadata?: {
    model?: string;
    tokens?: number;
  };
}

export interface PromptTemplate {
  id: string;
  name: string;
  description: string;
  content: string;
  variables: string[];
  category: string;
  createdAt: number;
  updatedAt: number;
}
