
import { loadRuntimeConfig } from '@/config';

let API_BASE_URL: string;

loadRuntimeConfig().then((config) => {
  API_BASE_URL = config.INFRAJET_API_URL;
}).catch((error) => {
  console.warn('Failed to load runtime config for API URL, using fallback:', error);
  API_BASE_URL = 'http://localhost:8000';
});

export const API_CONFIG = {
  BASE_URL:  API_BASE_URL|| 'http://localhost:8000/api/v1',
  WS_URL: import.meta.env.VITE_WS_URL || 'ws://localhost:8000/api/v1/websocket/ws',
  
  ENDPOINTS: {
    ENHANCED_CHAT: '/enhanced-chatbot/chat',
    CLARIFICATIONS: '/enhanced-chatbot/clarifications',
    CONVERSATION_STATUS: '/enhanced-chatbot/conversations',
    AZURE_FILES: '/enhanced-chatbot/azure/files'
  },
  
  WS_ENDPOINTS: {
    ENHANCED_CHAT: '/ws/enhanced-chat'
  }
};

export const getWebSocketUrl = (endpoint: string, token: string) => {
  return `${API_CONFIG.WS_URL}${endpoint}?token=${token}`;
};

export const getApiUrl = (endpoint: string) => {
  return `${API_CONFIG.BASE_URL}${endpoint}`;
};