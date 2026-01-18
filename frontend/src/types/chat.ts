export interface Message {
  id: string;
  type: 'user' | 'bot' | 'system';
  content: string;
  timestamp: Date;
  confidence?: number;
  status?: 'analyzing' | 'clarifying' | 'generating' | 'completed' | 'error';
  generation_id?: string;
  is_clarification_request?: boolean;
  clarification_questions?: ClarificationQuestion[];
}

export interface ClarificationQuestion {
  id: string;
  question: string;
  required?: boolean;
  type?: 'text' | 'select' | 'boolean';
  options?: string[];
}

export interface Clarification {
  id: string;
  questions: ClarificationQuestion[];
  round: number;
  maxRounds: number;
  responses: Record<string, string>;
}

export interface GeneratedFile {
  filename: string;
  content: string;
  azure_path: string;
  size: number;
}

export interface WebSocketEvent {
  event_type: string;
  thread_id?: string;
  message?: string;
  timestamp?: string;
  clarification_id?: string;
  questions?: string[];
  round?: number;
  max_rounds?: number;
  progress?: number;
  estimated_time?: number;
  saved_files?: GeneratedFile[];
  error?: string;
}

export interface ChatRequest {
  message: string;
  cloud_provider?: 'AWS' | 'Azure' | 'GCP';
  enable_realtime?: boolean;
  save_to_azure?: boolean;
}

export interface ClarificationResponse {
  responses: Record<string, string>;
}

export interface ConversationThread {
  thread_id: string;
  project_id: string;
  title: string;
  created_at: string;
  last_message_at: string | null;
  message_count: number;
  user_id?: string;
  cloud_provider?: string;
  status?: 'active' | 'completed';
}

export interface ChatMessage {
  id: string;
  thread_id: string;
  message_content: string;
  message_type: 'user' | 'system' | 'ai' | 'clarification_request';
  timestamp: string;
  is_user_message: boolean;
  is_system_message: boolean;
  is_ai_message: boolean;
  is_clarification_request: boolean;
  generation_id?: string;
}

export interface ThreadMessagesResponse {
  project_id: string;
  thread_id: string;
  messages: ChatMessage[];
  total_count: number;
  message: string;
}

export interface ConversationsResponse {
  conversations: ConversationThread[];
  total_count: number;
  has_more: boolean;
}