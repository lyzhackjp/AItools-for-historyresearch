import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
import { message } from 'antd';
import { useApiStore } from '../stores/useApiStore';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000';

const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const apiKey = useApiStore.getState().getActiveKey();
    if (apiKey && config.headers) {
      config.headers['X-API-Key'] = apiKey;
    }
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

apiClient.interceptors.response.use(
  (response) => response.data,
  (error: AxiosError<any>) => {
    if (error.response) {
      const status = error.response.status;
      const errorMessage = error.response.data?.error || error.message;

      switch (status) {
        case 401:
          message.error('API密钥无效，请检查配置');
          break;
        case 403:
          message.error('没有权限访问此资源');
          break;
        case 404:
          message.error('请求的资源不存在');
          break;
        case 500:
          message.error('服务器内部错误，请稍后重试');
          break;
        default:
          message.error(errorMessage);
      }
    } else if (error.request) {
      message.error('网络连接失败，请检查网络');
    } else {
      message.error(error.message);
    }

    return Promise.reject(error);
  }
);

export default apiClient;
