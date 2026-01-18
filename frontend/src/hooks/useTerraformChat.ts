import { useState, useRef, useCallback, useEffect } from 'react';
import { getAuthToken } from '@/services/infrajetApi';
import { useToast } from '@/hooks/use-toast';

// Types based on the Terraform Chat API documentation
export interface ClarificationQuestion {
  id: string;
  question: string;
  type: 'text' | 'select' | 'boolean';
  options?: string[];
}

export interface GeneratedFile {
  name: string;
  path: string;
  content: string;
  size: number;
  content_type: string;
}

export interface TerraformChatMessage {
  id: string;
  thread_id: string;
  message_content: string;
  message_type: 'user' | 'system' | 'ai' | 'clarification_request' | 'generation_result';
  timestamp: string;
  is_user_message: boolean;
  is_system_message: boolean;
  is_ai_message: boolean;
  is_clarification_request: boolean;
  clarification_questions?: ClarificationQuestion[];
  generated_files?: GeneratedFile[];
  generation_summary?: string;
}

export interface MessageHistoryResponse {
  project_id: string;
  thread_id: string;
  messages: TerraformChatMessage[];
  total_count: number;
  message: string;
}

export interface SendMessageRequest {
  message: string;
  thread_id?: string;
  cloud_provider?: string;
}

export interface SendMessageResponse {
  thread_id: string;
  status: 'clarification_needed' | 'generating';
  clarification_questions?: string[];
  generation_job_id?: string;
  message: string;
}

export interface ClarificationResponse {
  responses: { [key: string]: string };
}

export interface ClarificationResponseResult {
  thread_id: string;
  status: 'generating' | 'completed' | 'error';
  generation_job_id?: string;
  message: string;
}

// WebSocket event types
export interface TerraformChatProcessingEvent {
  type: 'terraform_chat_processing';
  thread_id: string;
  message: string;
  timestamp: string;
}

export interface TerraformClarificationNeededEvent {
  type: 'terraform_clarification_needed';
  thread_id: string;
  questions: string[];
  message: string;
  timestamp: string;
}

export interface TerraformGenerationStartingEvent {
  type: 'terraform_generation_starting';
  thread_id: string;
  message: string;
  timestamp: string;
}

export interface TerraformGenerationProgressEvent {
  type: 'terraform_generation_progress' | 'generation_progress';
  thread_id?: string;
  job_id?: string;
  generation_id?: string;
  progress_percentage: number;
  current_step: string;
  estimated_completion?: string;
  files_generated?: string[];
  project_id?: string;
  status?: string;
  user_id?: number;
  timestamp: string;
}

export interface TerraformGenerationCompletedEvent {
  type: 'terraform_generation_completed';
  thread_id: string;
  job_id: string;
  generated_files: string[];
  processing_time_ms: number;
  summary: string;
  timestamp: string;
}

export interface TerraformGenerationFailedEvent {
  type: 'terraform_generation_failed';
  thread_id: string;
  job_id: string;
  error: string;
  timestamp: string;
}

export interface TerraformGenerationTimeoutEvent {
  type: 'terraform_generation_timeout';
  thread_id: string;
  job_id: string;
  message: string;
  timestamp: string;
}

export interface TerraformChatErrorEvent {
  type: 'terraform_chat_error';
  thread_id: string;
  error: string;
  message: string;
  timestamp: string;
}

export type TerraformWebSocketEvent =
  | TerraformChatProcessingEvent
  | TerraformClarificationNeededEvent
  | TerraformGenerationStartingEvent
  | TerraformGenerationProgressEvent
  | TerraformGenerationCompletedEvent
  | TerraformGenerationFailedEvent
  | TerraformGenerationTimeoutEvent
  | TerraformChatErrorEvent;

export interface GenerationProgress {
  status: string;
  progress_percentage: number;
  current_step: string;
  estimated_completion?: string;
}

export interface ClarificationDialogState {
  isOpen: boolean;
  questions: string[];
  context_summary?: string;
  thread_id?: string;
}

// Terraform Chat Service Class
class TerraformChatService {
  private authToken: string;
  private baseUrl: string;
  private wsUrl: string;
  private projectId: string;
  private websocket: WebSocket | null = null;
  private eventHandlers = new Map<string, (data: TerraformWebSocketEvent) => void>();
  private reconnectAttempts = 5;
  private reconnectCount = 0;

  constructor(authToken: string, projectId: string) {
    this.authToken = authToken;
    this.projectId = projectId;
    this.baseUrl = window.__RUNTIME_CONFIG__?.INFRAJET_API_URL;
    this.wsUrl = this.baseUrl;
  }

  // Initialize WebSocket connection
  async initWebSocket(): Promise<void> {
    if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      // Using Socket.IO client for WebSocket connection
      const io = (await import('socket.io-client')).default;
      const socket = io(this.wsUrl, {
        auth: {
          token: this.authToken
        },
        transports: ['websocket', 'polling']
      });

      socket.on('connect', () => {
        console.log('Terraform Chat WebSocket connected');
        this.reconnectCount = 0;
        // Subscribe to project updates
        socket.emit('subscribe_project', { project_id: this.projectId });
      });

      socket.on('disconnect', () => {
        console.log('Terraform Chat WebSocket disconnected');
      });

      // Listen for all terraform events through the 'message' event
      socket.on('message', (data) => {
        if (data && data.event_type) {
          // Handle the new event structure where data is nested
          if (data.data) {
            this.handleEvent(data.event_type, { ...data.data, type: data.event_type });
          } else {
            this.handleEvent(data.event_type, { ...data, type: data.event_type });
          }
        } else if (data && data.type) {
          // Fallback for old structure
          this.handleEvent(data.type, data);
        }
      });

      this.websocket = socket as unknown as WebSocket; // Type compatibility
    } catch (error) {
      console.error('Failed to initialize WebSocket:', error);
    }
  }

  // Handle WebSocket events
  handleEvent(eventType: string, data: TerraformWebSocketEvent): void {
    const handler = this.eventHandlers.get(eventType);
    if (handler) {
      handler(data);
    }
  }

  // Register event handlers
  onEvent(eventType: string, callback: (data: TerraformWebSocketEvent) => void): void {
    this.eventHandlers.set(eventType, callback);
  }

  // Send Terraform chat message
  async sendMessage(projectId: string, request: SendMessageRequest): Promise<SendMessageResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/projects/${projectId}/terraform-chat/messages`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.authToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(request)
    });

    if (!response.ok) {
      const errorText = await response.text();
      // Don't expose internal error details to the user
      throw new Error('Failed to load generated files. Please try again.');
    }

    return await response.json();
  }

  // Respond to clarification questions
  async respondToClarification(projectId: string, threadId: string, responses: ClarificationResponse): Promise<ClarificationResponseResult> {
    const response = await fetch(`${this.baseUrl}/api/v1/projects/${projectId}/terraform-chat/clarifications/${threadId}/respond`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.authToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(responses)
    });

    if (!response.ok) {
      const errorText = await response.text();
      // Don't expose internal error details to the user
      throw new Error('Failed to load message history. Please try again.');
    }

    return await response.json();
  }

  // Get message history
  async getMessageHistory(projectId: string, threadId?: string, limit = 50): Promise<MessageHistoryResponse> {
    const params = new URLSearchParams();
    if (threadId) params.set('thread_id', threadId);
    params.set('limit', limit.toString());

    const response = await fetch(`${this.baseUrl}/api/v1/projects/${projectId}/terraform-chat/history?${params.toString()}`, {
      headers: {
        'Authorization': `Bearer ${this.authToken}`
      }
    });

    if (!response.ok) {
      const errorText = await response.text();
      // Don't expose internal error details to the user
      throw new Error('Failed to respond to clarification. Please try again.');
    }

    return await response.json();
  }

  // Get generation files
  async getGenerationFiles(projectId: string, generationId: string): Promise<GeneratedFile[]> {
    const response = await fetch(`${this.baseUrl}/api/v1/projects/${projectId}/generations/${generationId}/files?include_content=true`, {
      headers: {
        'Authorization': `Bearer ${this.authToken}`
      }
    });

    if (!response.ok) {
      const errorText = await response.text();
      // Don't expose internal error details to the user
      throw new Error('Failed to send message. Please try again.');
    }

    const data = await response.json();
    return data.files || [];
  }

  // Disconnect WebSocket
  disconnect(): void {
    if (this.websocket) {
      this.websocket.close();
      this.websocket = null;
    }
  }
}

// Hook for using Terraform chat
export const useTerraformChat = (projectId: string) => {
  const [chatService, setChatService] = useState<TerraformChatService | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [currentThreadId, setCurrentThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<TerraformChatMessage[]>([]);
  const [clarificationDialog, setClarificationDialog] = useState<ClarificationDialogState>({
    isOpen: false,
    questions: []
  });
  const [generationProgress, setGenerationProgress] = useState<GenerationProgress | null>(null);
  const { toast } = useToast();

  // Initialize chat service
  const initChat = useCallback(async () => {
    try {
      console.log('🔐 Getting auth token for Terraform chat...');
      const token = await getAuthToken();
      console.log('✅ Got auth token for Terraform chat, length:', token.length);
      const service = new TerraformChatService(token, projectId);

      // Set up event handlers
      service.onEvent('terraform_chat_processing', (data: TerraformChatProcessingEvent) => {
        setMessages(prev => [...prev, {
          id: `processing-${Date.now()}`,
          thread_id: data.thread_id,
          message_content: data.message,
          message_type: 'system',
          timestamp: data.timestamp,
          is_user_message: false,
          is_system_message: true,
          is_ai_message: false,
          is_clarification_request: false
        }]);
      });

      service.onEvent('terraform_clarification_needed', (data: TerraformClarificationNeededEvent) => {
        const clarificationQuestions: ClarificationQuestion[] = data.questions.map((question, index) => ({
          id: `question-${index}`,
          question,
          type: 'text' as const
        }));
        setClarificationDialog({
          isOpen: false, // No longer using dialog
          questions: data.questions,
          context_summary: data.message,
          thread_id: data.thread_id
        });
        setMessages(prev => [...prev, {
          id: `clarification-${Date.now()}`,
          thread_id: data.thread_id,
          message_content: `I need some additional information:`,
          message_type: 'clarification_request',
          timestamp: data.timestamp,
          is_user_message: false,
          is_system_message: false,
          is_ai_message: false,
          is_clarification_request: true,
          clarification_questions: clarificationQuestions
        }]);
      });

      service.onEvent('terraform_generation_starting', (data: TerraformGenerationStartingEvent) => {
        setIsGenerating(true);
        setMessages(prev => [...prev, {
          id: `starting-${Date.now()}`,
          thread_id: data.thread_id,
          message_content: data.message,
          message_type: 'system',
          timestamp: data.timestamp,
          is_user_message: false,
          is_system_message: true,
          is_ai_message: false,
          is_clarification_request: false
        }]);
      });

      service.onEvent('terraform_generation_progress', (data: TerraformGenerationProgressEvent) => {
        console.log('Handling generation progress:', data);
        setGenerationProgress({
          status: data.status || 'generating',
          progress_percentage: data.progress_percentage,
          current_step: data.current_step,
          estimated_completion: data.estimated_completion
        });
        setMessages(prev => [...prev, {
          id: `progress-${Date.now()}`,
          thread_id: data.thread_id || currentThreadId || '',
          message_content: `🔄 ${data.current_step} (${data.progress_percentage}%)`,
          message_type: 'system',
          timestamp: data.timestamp,
          is_user_message: false,
          is_system_message: true,
          is_ai_message: false,
          is_clarification_request: false
        }]);
      });

      // Also handle the new event type
      service.onEvent('generation_progress', (data: TerraformGenerationProgressEvent) => {
        setGenerationProgress({
          status: data.status || 'generating',
          progress_percentage: data.progress_percentage,
          current_step: data.current_step,
          estimated_completion: data.estimated_completion
        });
        setMessages(prev => [...prev, {
          id: `progress-${Date.now()}`,
          thread_id: currentThreadId || '',
          message_content: `🔄 ${data.current_step} (${data.progress_percentage}%)`,
          message_type: 'system',
          timestamp: data.timestamp,
          is_user_message: false,
          is_system_message: true,
          is_ai_message: false,
          is_clarification_request: false
        }]);
      });

      service.onEvent('terraform_generation_completed', async (data: TerraformGenerationCompletedEvent) => {
        setIsGenerating(false);
        setGenerationProgress(null);

        try {
          // Fetch the generated files
          const generatedFiles = await service.getGenerationFiles(projectId, data.job_id);

          setMessages(prev => [...prev, {
            id: `completed-${Date.now()}`,
            thread_id: data.thread_id,
            message_content: `✅ ${data.summary}`,
            message_type: 'generation_result',
            timestamp: data.timestamp,
            is_user_message: false,
            is_system_message: false,
            is_ai_message: true,
            is_clarification_request: false,
            generated_files: generatedFiles,
            generation_summary: data.summary
          }]);
        } catch (error) {
          console.error('Failed to fetch generated files:', error);
          // Fallback to simple message if file fetching fails
          setMessages(prev => [...prev, {
            id: `completed-${Date.now()}`,
            thread_id: data.thread_id,
            message_content: `✅ ${data.summary}`,
            message_type: 'system',
            timestamp: data.timestamp,
            is_user_message: false,
            is_system_message: true,
            is_ai_message: false,
            is_clarification_request: false
          }]);
        }

        toast({
          title: "Generation Complete",
          description: data.summary,
        });
      });

      service.onEvent('terraform_generation_failed', (data: TerraformGenerationFailedEvent) => {
        setIsGenerating(false);
        setGenerationProgress(null);
        setMessages(prev => [...prev, {
          id: `failed-${Date.now()}`,
          thread_id: data.thread_id,
          message_content: `❌ Generation failed: ${data.error}`,
          message_type: 'system',
          timestamp: data.timestamp,
          is_user_message: false,
          is_system_message: true,
          is_ai_message: false,
          is_clarification_request: false
        }]);
        toast({
          title: "Generation Failed",
          description: data.error,
          variant: "destructive",
        });
      });

      service.onEvent('terraform_generation_timeout', (data: TerraformGenerationTimeoutEvent) => {
        setIsGenerating(false);
        setGenerationProgress(null);
        setMessages(prev => [...prev, {
          id: `timeout-${Date.now()}`,
          thread_id: data.thread_id,
          message_content: `⏰ ${data.message}`,
          message_type: 'system',
          timestamp: data.timestamp,
          is_user_message: false,
          is_system_message: true,
          is_ai_message: false,
          is_clarification_request: false
        }]);
        toast({
          title: "Generation Timeout",
          description: data.message,
          variant: "destructive",
        });
      });

      service.onEvent('terraform_chat_error', (data: TerraformChatErrorEvent) => {
        setMessages(prev => [...prev, {
          id: `error-${Date.now()}`,
          thread_id: data.thread_id,
          message_content: `❌ ${data.message}`,
          message_type: 'system',
          timestamp: data.timestamp,
          is_user_message: false,
          is_system_message: true,
          is_ai_message: false,
          is_clarification_request: false
        }]);
        toast({
          title: "Chat Error",
          description: data.message,
          variant: "destructive",
        });
      });

      await service.initWebSocket();
      setChatService(service);
      setIsConnected(true);
    } catch (error) {
      console.error('Failed to initialize Terraform chat:', error);
      toast({
        title: "Connection Error",
        description: "Failed to connect to Terraform chat service",
        variant: "destructive",
      });
    }
  }, [toast]);

  // Send message
  const sendMessage = useCallback(async (messageContent: string, threadId?: string, cloudProvider?: string) => {
    if (!chatService) {
      throw new Error('Chat service not initialized');
    }

    // Add user message to conversation
    const userMessage: TerraformChatMessage = {
      id: `user-${Date.now()}`,
      thread_id: threadId || currentThreadId || '',
      message_content: messageContent,
      message_type: 'user',
      timestamp: new Date().toISOString(),
      is_user_message: true,
      is_system_message: false,
      is_ai_message: false,
      is_clarification_request: false
    };
    setMessages(prev => [...prev, userMessage]);

    try {
      const request: SendMessageRequest = {
        message: messageContent,
        thread_id: threadId || currentThreadId || undefined,
        cloud_provider: cloudProvider
      };

      const result = await chatService.sendMessage(projectId, request);

      // Update current thread ID
      setCurrentThreadId(result.thread_id);

      return result;
    } catch (error) {
      console.error('Failed to send Terraform chat message:', error);
      setMessages(prev => [...prev, {
        id: `error-${Date.now()}`,
        thread_id: currentThreadId || '',
        message_content: '❌ Failed to send message. Please try again.',
        message_type: 'system',
        timestamp: new Date().toISOString(),
        is_user_message: false,
        is_system_message: true,
        is_ai_message: false,
        is_clarification_request: false
      }]);
      toast({
        title: "Failed to send message",
        description: "Please try again",
        variant: "destructive",
      });
      throw error;
    }
  }, [chatService, currentThreadId, projectId, toast]);

  // Respond to clarification
  const respondToClarification = useCallback(async (responses: { [key: string]: string }, threadId?: string) => {
    if (!chatService) {
      throw new Error('Chat service not initialized');
    }
    const targetThreadId = threadId || clarificationDialog.thread_id;
    if (!targetThreadId) {
      throw new Error('No clarification pending');
    }

    try {
      const result = await chatService.respondToClarification(projectId, targetThreadId, { responses });
      // Clear the clarification state
      setClarificationDialog({ isOpen: false, questions: [] });
      return result;
    } catch (error) {
      console.error('Failed to respond to clarification:', error);
      toast({
        title: "Failed to process clarification",
        description: "Please try again",
        variant: "destructive",
      });
      throw error;
    }
  }, [chatService, clarificationDialog.thread_id, projectId, toast]);

  // Load message history
  const loadMessageHistory = useCallback(async (threadId?: string, limit = 50) => {
    if (!chatService) return;

    try {
      const history = await chatService.getMessageHistory(projectId, threadId, limit);
      setMessages(history.messages);
      if (threadId) {
        setCurrentThreadId(threadId);
      }
    } catch (error) {
      console.error('Failed to load message history:', error);
      toast({
        title: "Failed to load history",
        description: "Could not load conversation history",
        variant: "destructive",
      });
    }
  }, [chatService, projectId, toast]);

  // Cleanup
  useEffect(() => {
    return () => {
      if (chatService) {
        chatService.disconnect();
      }
    };
  }, [chatService]);

  return {
    isConnected,
    isGenerating,
    currentThreadId,
    messages,
    clarificationDialog,
    generationProgress,
    initChat,
    sendMessage,
    respondToClarification,
    loadMessageHistory,
  };
};