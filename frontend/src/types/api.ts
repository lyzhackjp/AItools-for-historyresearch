import type { ArtifactSummary, QualityFlag, ReviewItem, TaskCapability } from './models';

export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

export interface TaskExecuteRequest {
  task_type: string;
  preset?: string;
  mode?: string;
  provider?: string;
  backend?: string;
  model?: string;
  input?: Record<string, unknown>;
  timeout?: number;
  max_retries?: number;
  fallback_backends?: string[];
  preferred_providers?: string[];
  extra_params?: Record<string, unknown>;
}

export interface TaskExecutionPackage {
  type?: string;
  schema_version?: string;
  success: boolean;
  task_type?: string;
  requested_task_type?: string;
  package_type?: string;
  preset?: string;
  mode?: string;
  backend?: string;
  provider?: string;
  model?: string;
  confidence?: number;
  needs_review?: boolean;
  quality_flags?: Array<string | QualityFlag>;
  execution_time?: number;
  data?: unknown;
  result?: unknown;
  task_options?: unknown;
  artifacts?: ArtifactSummary[];
  created_at?: string;
  metadata?: {
    provider?: string;
    backend?: string;
    confidence?: number;
    needs_review?: boolean;
    quality_flags?: QualityFlag[];
    artifacts?: ArtifactSummary[];
    review_items?: ReviewItem[];
  };
  error?: string;
}

export interface TaskCapabilitiesResponse {
  tasks: Record<string, TaskCapability> | TaskCapability[];
  providers: Record<string, unknown> | unknown[];
  default_mode: string;
  default_provider: string;
}

export interface JobSnapshot {
  job_id: string;
  state: string;
  progress: number;
  stage: string;
  logs: string[];
  artifacts: ArtifactSummary[];
}

export interface OCRRequest {
  file: File;
  engine: string;
  language?: string;
  dpi?: number;
}

export interface NERRequest {
  text: string;
  entityTypes: string[];
  language: 'zh' | 'ja' | 'en';
}
