import axios from 'axios';

// Create a configured axios instance
export const api = axios.create({
  baseURL: 'http://localhost:8000/api', // default FastAPI port
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface ConfigData {
  llm_provider: string;
  api_key_configured: boolean;
  api_key?: string;
  model_name: string;
  embedding_model: string;
}

export interface ConfigUpdateData {
  llm_provider?: string;
  api_key?: string;
  model_name?: string;
  embedding_model?: string;
}

export const getConfig = async (): Promise<ConfigData> => {
  const response = await api.get('/config');
  return response.data;
};

export const saveConfig = async (data: ConfigUpdateData): Promise<ConfigData> => {
  const response = await api.post('/config', data);
  return response.data;
};

export const testConfig = async (data?: ConfigUpdateData): Promise<{success: boolean, message: string, response: string}> => {
  const response = await api.post('/config/test', data || {});
  return response.data;
};
