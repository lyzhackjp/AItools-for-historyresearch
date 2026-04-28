import axios, { AxiosError, type AxiosInstance, type InternalAxiosRequestConfig } from 'axios';
import { message } from 'antd';

const sameOriginBaseURL = typeof window === 'undefined' ? 'http://localhost:5000' : window.location.origin;
const baseURL = import.meta.env.DEV
  ? import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000'
  : sameOriginBaseURL;

const apiClient: AxiosInstance = axios.create({
  baseURL,
  timeout: 90_000,
});

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  return config;
});

apiClient.interceptors.response.use(
  (response) => response.data,
  (error: AxiosError<{ error?: string; message?: string }>) => {
    const errorMessage = error.response?.data?.error ?? error.response?.data?.message ?? error.message;
    if (error.response?.status === 404) {
      message.error('请求的接口或资源不存在。');
    } else if (error.response?.status && error.response.status >= 500) {
      message.error('后端服务返回错误，请查看任务中心或服务日志。');
    } else if (!error.response) {
      message.warning('暂时无法连接后端，前端会保留本地任务状态。');
    } else {
      message.error(errorMessage);
    }
    return Promise.reject(error);
  },
);

export { baseURL };
export default apiClient;
