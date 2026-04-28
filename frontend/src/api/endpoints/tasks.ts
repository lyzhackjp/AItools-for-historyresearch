import apiClient from '../client';
import type {
  ApiResponse,
  JobSnapshot,
  TaskCapabilitiesResponse,
  TaskExecuteRequest,
  TaskExecutionPackage,
} from '../../types';

export const taskApi = {
  getCapabilities: async () => {
    return apiClient.get<unknown, ApiResponse<TaskCapabilitiesResponse>>('/api/tasks/capabilities');
  },

  getCapability: async (taskType: string) => {
    return apiClient.get<unknown, ApiResponse<unknown>>(`/api/tasks/capabilities/${taskType}`);
  },

  executeTask: async (payload: TaskExecuteRequest) => {
    return apiClient.post<unknown, TaskExecutionPackage>('/api/tasks/execute', payload);
  },

  getSystemStatus: async () => {
    return apiClient.get<unknown, ApiResponse<unknown>>('/api/system/status');
  },

  getJob: async (jobId: string) => {
    return apiClient.get<unknown, ApiResponse<JobSnapshot>>(`/api/jobs/${jobId}`);
  },
};
