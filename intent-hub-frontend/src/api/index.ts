import axios from 'axios';

// 根据环境变量设置 API 基础地址
// 开发环境使用 /api（通过 vite 代理）
// 生产环境直接使用完整 URL
const getBaseURL = () => {
  return '/api'
};

const api = axios.create({
  baseURL: getBaseURL(),
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器：添加 API Key
api.interceptors.request.use((config) => {
  // 登录接口不需要携带 token
  if (config.url === '/auth/login') {
    return config;
  }
  
  // 预测接口鉴权处理
  if (config.url === '/predict') {
    const predictKey = localStorage.getItem('predict_auth_key');
    if (predictKey) {
      config.headers['Authorization'] = predictKey;
      return config;
    }
  }
  
  // 其他接口使用 API Key 认证
  const token = localStorage.getItem('api_key');
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`;
    config.headers['X-API-Key'] = token;
  }
  return config;
});

// 响应拦截器：处理 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // 如果是 401 且不是登录接口，则跳转到登录页
    if (error.response?.status === 401 && !error.config?.url?.includes('/auth/login')) {
      localStorage.removeItem('api_key');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export interface RouteConfig {
  id: number;
  name: string;
  description: string;
  utterances: string[];
  score_threshold: number;
}

export interface GenerateUtterancesRequest {
  id: number;
  name: string;
  description?: string;
  count?: number;
  utterances?: string[];
}

export interface PredictResult {
  id: number;
  name: string;
  score?: number;
}

export const getRoutes = () => api.get<RouteConfig[]>('/routes');
export const searchRoutes = (query: string = '') => api.get<RouteConfig[]>('/routes/search', { params: { q: query } });
export const createRoute = (data: RouteConfig) => api.post<RouteConfig>('/routes', data);
export const updateRoute = (id: number, data: Partial<RouteConfig>) => api.put<RouteConfig>(`/routes/${id}`, data);
export const deleteRoute = (id: number) => api.delete<{ message: string }>(`/routes/${id}`);
export const generateUtterances = (data: GenerateUtterancesRequest) => api.post<RouteConfig>('/routes/generate-utterances', data);

export interface ReindexResponse {
  message: string;
  mode: string;
  routes_count: number;
  total_points: number;
}

export const reindex = (forceFull: boolean = false) => api.post<ReindexResponse>('/reindex', { force_full: forceFull });

export const predict = (text: string) => api.post<PredictResult[]>('/predict', { text });

export interface Settings {
  // Qdrant配置
  QDRANT_URL: string;
  QDRANT_COLLECTION: string;
  QDRANT_API_KEY?: string | null;
  
  // Embedding模型配置
  HUGGINGFACE_ACCESS_TOKEN?: string | null;
  HUGGINGFACE_PROVIDER?: string | null;
  EMBEDDING_MODEL_NAME: string;
  EMBEDDING_DEVICE: 'cpu' | 'cuda' | 'mps';
  
  // LLM配置（通用）
  LLM_PROVIDER: 'deepseek' | 'openrouter' | 'doubao' | 'qwen' | 'gemini';
  LLM_API_KEY?: string | null;
  LLM_BASE_URL?: string | null;
  LLM_MODEL?: string | null;
  LLM_TEMPERATURE: number;
  
  // DeepSeek配置（向后兼容）
  DEEPSEEK_API_KEY?: string | null;
  DEEPSEEK_BASE_URL?: string;
  DEEPSEEK_MODEL?: string;
  
  // 提示词配置
  UTTERANCE_GENERATION_PROMPT: string;
  
  // 认证配置
  PREDICT_AUTH_KEY?: string | null;
  
  // 其他配置
  BATCH_SIZE?: number;
  DEFAULT_ROUTE_ID?: number;
  DEFAULT_ROUTE_NAME?: string;
}

export const getSettings = () => api.get<Settings>('/settings');
export const updateSettings = (data: Partial<Settings>) => api.post<{ message: string; settings: Settings }>('/settings', data);

export default api;

