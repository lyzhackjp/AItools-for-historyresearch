export type WorkspaceMode = 'manual' | 'agent';

export type TaskKind =
  | 'ocr'
  | 'ner'
  | 'citation'
  | 'note'
  | 'analysis'
  | 'knowledge'
  | 'writing'
  | 'polish'
  | 'workflow'
  | 'agent'
  | 'system';

export type ModuleFamily =
  | 'workflow'
  | 'ocr'
  | 'analysis'
  | 'citation'
  | 'knowledge'
  | 'writing'
  | 'agent'
  | 'system';

export type ExecutionTarget = 'task_manager' | 'workflow_stage' | 'package_module' | 'agent_skill';

export type ModulePrivacy = 'local_first' | 'mixed' | 'external_optional' | 'managed_root';

export interface WorkspaceModule {
  id: string;
  title: string;
  family: ModuleFamily;
  modulePath: string;
  description: string;
  executionTarget: ExecutionTarget;
  taskType: string;
  inputs: string[];
  outputs: string[];
  backends: string[];
  packageTypes: string[];
  privacy: ModulePrivacy;
  reviewRequired: boolean;
  stage?: string;
  presets?: string[];
}

export interface WorkflowNodeConfig {
  id: string;
  moduleId: string;
  label: string;
  inputBinding: string;
  outputBinding: string;
  backend: string;
  provider: string;
  preset?: string;
  reviewGate: boolean;
  enabled: boolean;
  notes?: string;
}

export interface WorkflowEdgeConfig {
  id: string;
  from: string;
  to: string;
  outputKey: string;
  inputKey: string;
}

export interface WorkflowBlueprint {
  id: string;
  name: string;
  description: string;
  nodes: WorkflowNodeConfig[];
  edges: WorkflowEdgeConfig[];
  createdAt: number;
  updatedAt: number;
}

export interface AgentSkillConfig {
  id: string;
  name: string;
  description: string;
  selectedModuleIds: string[];
  allowedBackends: string[];
  permissions: {
    readWorkspace: boolean;
    writeArtifacts: boolean;
    externalSearch: boolean;
    downloadSources: boolean;
    usePaidApi: boolean;
    writeVault: boolean;
  };
  systemPrompt: string;
  acceptanceChecklist: string[];
  generatedSkillMarkdown: string;
  updatedAt: number;
}

export type TaskState = 'queued' | 'running' | 'waiting_review' | 'completed' | 'failed' | 'cancelled';

export interface ArtifactSummary {
  id: string;
  name: string;
  type: string;
  path?: string;
  createdAt: number;
}

export interface QualityFlag {
  id: string;
  level: 'info' | 'warning' | 'error';
  message: string;
  source?: string;
}

export interface ReviewItem {
  id: string;
  title: string;
  status: 'open' | 'resolved' | 'deferred';
  priority: 'low' | 'medium' | 'high';
  summary: string;
}

export interface TaskLogEntry {
  id: string;
  timestamp: number;
  level: 'info' | 'success' | 'warning' | 'error';
  message: string;
}

export interface WorkspaceTask {
  id: string;
  title: string;
  kind: TaskKind;
  mode: WorkspaceMode;
  state: TaskState;
  progress: number;
  stage: string;
  createdAt: number;
  updatedAt: number;
  startedAt?: number;
  finishedAt?: number;
  provider?: string;
  backend?: string;
  logs: TaskLogEntry[];
  artifacts: ArtifactSummary[];
  qualityFlags: QualityFlag[];
  reviewItems: ReviewItem[];
  result?: unknown;
  error?: string;
}

export interface TaskCapability {
  taskType: string;
  title: string;
  description: string;
  presets: string[];
  backends: string[];
  providers: string[];
  privacyLevel: 'local' | 'mixed' | 'external';
}

export interface AgentCapability {
  id: string;
  name: string;
  description: string;
  risk: 'low' | 'medium' | 'high';
}

export interface AgentGoal {
  topic: string;
  materialScope: string;
  expectedOutput: string;
  timeBudget: string;
  allowedBackends: string[];
}

export interface AgentPlanStep {
  id: string;
  title: string;
  owner: 'agent' | 'user';
  status: 'planned' | 'approved' | 'running' | 'done';
  description: string;
}

export interface AgentPlan {
  id: string;
  connectorId: string;
  goal: AgentGoal;
  steps: AgentPlanStep[];
  createdAt: number;
}

export interface UserPreferences {
  fontSize: 'normal' | 'large' | 'extra-large';
  highContrast: boolean;
  language: 'zh-CN' | 'en-US' | 'ja-JP';
  compactDensity: boolean;
}

export interface ApiKeyConfig {
  provider: string;
  displayName: string;
  configured: boolean;
  updatedAt?: number;
}
