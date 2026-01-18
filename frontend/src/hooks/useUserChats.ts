import { useState, useEffect, useCallback, useRef } from 'react';
import { getAuthToken } from '@/services/infrajetApi';
import { ConversationThread, ThreadMessagesResponse, ConversationsResponse, Message, ChatMessage } from '@/types/chat';

const API_BASE_URL = window.__RUNTIME_CONFIG__?.INFRAJET_API_URL;

interface ClarificationQuestion {
  id: string;
  question: string;
  type: 'text' | 'select' | 'boolean';
  options?: string[];
}

export const useUserChats = (projectId: string, userId: string) => {
  const [threads, setThreads] = useState<ConversationThread[]>([]);
  const [selectedThread, setSelectedThread] = useState<ConversationThread | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [messagesKey, setMessagesKey] = useState(0); // Force re-render key
  const [loading, setLoading] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [offset, setOffset] = useState(0);
  const [isConnected, setIsConnected] = useState(false);
  const [sendingMessage, setSendingMessage] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationProgress, setGenerationProgress] = useState<{
    status: string;
    progress_percentage: number;
    current_step: string;
    estimated_completion?: string;
  } | null>(null);
  const [clarificationDialog, setClarificationDialog] = useState<{
    isOpen: boolean;
    questions: ClarificationQuestion[];
    context_summary?: string;
  }>({
    isOpen: false,
    questions: [],
    context_summary: ''
  });
  const socketRef = useRef<any>(null);

  // Fetch user's conversation threads
  const fetchThreads = useCallback(async (loadMore = false) => {
    try {
      setLoading(true);
      const token = await getAuthToken();

      const response = await fetch(`${API_BASE_URL}/api/v1/autonomous/conversations?project_id=${projectId}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        // Fallback to mock data if API doesn't exist
        console.warn('Threads API not available, using mock data');
        const mockThreads: ConversationThread[] = [
          {
            thread_id: 'thread-1',
            project_id: projectId,
            title: 'VPC Infrastructure Setup',
            created_at: new Date().toISOString(),
            last_message_at: new Date().toISOString(),
            message_count: 5,
            user_id: userId,
            status: 'active',
            cloud_provider: 'AWS'
          },
          {
            thread_id: 'thread-2',
            project_id: projectId,
            title: 'EC2 Instance Configuration',
            created_at: new Date(Date.now() - 86400000).toISOString(),
            last_message_at: new Date(Date.now() - 3600000).toISOString(),
            message_count: 8,
            user_id: userId,
            status: 'completed',
            cloud_provider: 'AWS'
          }
        ];
        // setThreads(mockThreads);
        setHasMore(false);
        return;
      }

      const data: ConversationThread[] = await response.json();
      setThreads(data || []);
      setHasMore(false); // API doesn't provide pagination info
    } catch (error) {
      console.error('Error fetching threads:', error);
      // Fallback to mock data
      const mockThreads: ConversationThread[] = [
        {
          thread_id: 'thread-1',
          project_id: projectId,
          title: 'VPC Infrastructure Setup',
          created_at: new Date().toISOString(),
          last_message_at: new Date().toISOString(),
          message_count: 5,
          user_id: userId,
          status: 'active',
          cloud_provider: 'AWS'
        }
      ];
      setThreads(mockThreads);
      setHasMore(false);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  // Fetch messages for a specific thread
  const fetchThreadMessages = useCallback(async (threadId: string, loadMore = false) => {
    try {
      setLoadingMessages(true);
      const token = await getAuthToken();

      const response = await fetch(`${API_BASE_URL}/api/v1/projects/${projectId}/terraform-chat/threads/${threadId}/messages`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch thread messages: ${response.status}`);
      }

      const data: ThreadMessagesResponse = await response.json();

      // Convert ChatMessage[] to Message[]
      const convertedMessages: Message[] = data.messages.map(chatMsg => ({
        id: chatMsg.id,
        type: chatMsg.message_type === 'user' ? 'user' :
          chatMsg.message_type === 'ai' ? 'bot' :
            chatMsg.message_type === 'system' ? 'system' : 'system',
        content: chatMsg.message_content,
        timestamp: new Date(chatMsg.timestamp),
        status: 'completed',
        generation_id: chatMsg.generation_id
      }));

      if (loadMore) {
        setMessages(prev => [...prev, ...convertedMessages]);
      } else {
        setMessages(convertedMessages);
      }

      setHasMore(false); // API doesn't provide has_more, assume no pagination for now
    } catch (error) {
      console.error('Error fetching thread messages:', error);
      setMessages([]);
    } finally {
      setLoadingMessages(false);
    }
  }, [projectId]);

  // Select a thread and load its messages
  const selectThread = useCallback(async (thread: ConversationThread) => {
    console.log('🎯 Selecting thread:', thread.thread_id);
    setSelectedThread(thread);
    setMessages([]);
    await fetchThreadMessages(thread.thread_id);

    // Subscribe to thread-specific events
    if (socketRef.current && thread.thread_id) {
      console.log('📡 Subscribing to conversation:', thread.thread_id);
      socketRef.current.emit('subscribe_conversation', { thread_id: thread.thread_id });
    }
  }, [fetchThreadMessages]);

  // Create a new temporary chat (no thread_id yet)
  const createNewThread = useCallback(() => {
    // Create a temporary thread object without thread_id
    const tempThread: ConversationThread = {
      thread_id: '', // Empty thread_id for temporary chat
      project_id: projectId,
      title: 'New Chat',
      created_at: new Date().toISOString(),
      last_message_at: new Date().toISOString(),
      message_count: 0
    };
    setSelectedThread(tempThread);
    setMessages([]);
  }, [projectId]);

  // Load more messages for current thread
  const loadMoreMessages = useCallback(async () => {
    if (selectedThread && hasMore && !loadingMessages) {
      await fetchThreadMessages(selectedThread.thread_id, true);
    }
  }, [selectedThread, hasMore, loadingMessages, fetchThreadMessages]);

  // Load more threads
  const loadMoreThreads = useCallback(async () => {
    if (hasMore && !loading) {
      await fetchThreads(true);
    }
  }, [hasMore, loading, fetchThreads]);

  // Send message to continue thread or create new thread
  const sendMessage = useCallback(async (message: string, cloudProvider = 'AWS') => {
    try {
      setSendingMessage(true);

      const token = await getAuthToken();

      // Add user message to local state immediately for better UX
      const tempUserMessage: Message = {
        id: `temp-${Date.now()}`, // Temporary ID
        type: 'user',
        content: message,
        timestamp: new Date(),
        status: 'completed'
      };
      setMessages(prev => [...prev, tempUserMessage]);

      const requestBody: any = {
        message,
        cloud_provider: cloudProvider
      };

      // If we have a selected thread with a real thread_id, continue it
      if (selectedThread && selectedThread.thread_id) {
        requestBody.thread_id = selectedThread.thread_id;
      }
      // If thread_id is empty, this is a new chat and backend will create thread_id

      const response = await fetch(`${API_BASE_URL}/api/v1/projects/${projectId}/terraform-chat/messages`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestBody)
      });

      if (!response.ok) {
        // Remove the temporary message if request failed
        setMessages(prev => prev.filter(msg => msg.id !== tempUserMessage.id));
        throw new Error(`Failed to send message: ${response.status}`);
      }

      const result = await response.json();

      // If this was a new thread creation (selectedThread has empty thread_id), update it with real thread_id
      if (selectedThread && !selectedThread.thread_id && result.thread_id) {
        // Update the temporary thread with the real thread_id
        const updatedThread: ConversationThread = {
          ...selectedThread,
          thread_id: result.thread_id,
          title: `Chat ${result.thread_id.substring(0, 8)}`,
          last_message_at: new Date().toISOString(),
          message_count: 1
        };

        // Add to threads list and update selected thread
        setThreads(prev => [updatedThread, ...prev]);
        setSelectedThread(updatedThread);
        setMessages([tempUserMessage]); // Keep the user message for the new thread
      }

      // The actual message will come through WebSocket and replace the temp one, or we keep the temp one if WebSocket fails

    } catch (error) {
      console.error('Error sending message:', error);
      throw error;
    } finally {
      setSendingMessage(false);
    }
  }, [projectId, selectedThread]);

  // Initialize WebSocket connection
  const initWebSocket = useCallback(async () => {
    if (socketRef.current?.connected) {
      console.log('WebSocket already connected');
      return; // Already connected
    }

    try {
      console.log('🔌 Initializing WebSocket connection...');
      const token = await getAuthToken();
      console.log('🔑 Got auth token for WebSocket');

      const io = (await import('socket.io-client')).default;

      const socket = io(API_BASE_URL, {
        auth: { token },
        transports: ['websocket', 'polling'],
        timeout: 5000
      });

      socket.on('connect', () => {
        console.log('✅ Chat WebSocket connected successfully');
        setIsConnected(true);
        socket.emit('subscribe_project', { project_id: projectId });
        console.log('📡 Subscribed to project:', projectId);

        // Also try subscribing with different formats in case the backend expects different structure
        socket.emit('subscribe', { project_id: projectId });
        socket.emit('join_project', { project_id: projectId });
        console.log('📡 Also tried alternative subscription methods');

        // Subscribe to current thread if one is selected
        if (selectedThread && selectedThread.thread_id) {
          console.log('📡 Re-subscribing to conversation:', selectedThread.thread_id);
          socket.emit('subscribe_conversation', { thread_id: selectedThread.thread_id });
        }
      });

      socket.on('connect_error', (error) => {
        console.error('❌ WebSocket connection error:', error);
        setIsConnected(false);
      });

      socket.on('disconnect', (reason) => {
        console.log('❌ Chat WebSocket disconnected:', reason);
        setIsConnected(false);
      });

      // Handle WebSocket events - match backend event structure
      socket.on('message', (data) => {
        console.log('🔥 RECEIVED WebSocket message:', JSON.stringify(data, null, 2));

        if (data.type) {
          // Direct event format from backend
          handleWebSocketEvent(data.type, data);
        } else if (data.event_type) {
          // Wrapped event format
          handleWebSocketEvent(data.event_type, data.data || data);
        } else {
          console.log('⚠️ Unknown event format:', data);
        }
      });

      // All events are now handled by the main 'message' listener above

      // Event handler function
      const handleWebSocketEvent = (eventType: string, eventData: any) => {
        console.log(`🎯 Processing ${eventType} event:`, eventData);

        switch (eventType) {
          case 'new_message':
            // Add new message to current thread if it's the selected one
            if (selectedThread && (eventData.thread_id === selectedThread.thread_id || eventData.project_id)) {
              const newMessage: Message = {
                id: eventData.id,
                type: eventData.message_type === 'user' ? 'user' :
                  eventData.message_type === 'ai' ? 'bot' :
                    eventData.message_type === 'system' ? 'system' : 'system',
                content: eventData.message_content || eventData.content,
                timestamp: new Date(eventData.timestamp),
                status: 'completed',
                generation_id: eventData.generation_id
              };
              console.log('✅ Adding new message from WebSocket:', newMessage);
              setMessages(prev => {
                // Remove any temporary message with the same content
                const filtered = prev.filter(msg => msg.content !== newMessage.content || !msg.id.startsWith('temp-'));
                const updated = [...filtered, newMessage];
                console.log('📝 Updated messages array:', updated.length, 'messages');
                return updated;
              });
              setMessagesKey(prev => prev + 1); // Force re-render
            }
            break;

          case 'terraform_generation_progress':
            console.log('⚡ Processing terraform generation progress:', eventData);
            setIsGenerating(true);
            setGenerationProgress({
              status: 'generating',
              progress_percentage: eventData.progress_percentage || 0,
              current_step: eventData.current_step || 'Processing...',
              estimated_completion: eventData.estimated_completion
            });
            break;

          case 'terraform_clarification_needed':
            console.log('❓ Processing terraform clarification needed:', eventData);
            if (selectedThread && eventData.thread_id === selectedThread.thread_id) {
              const clarificationMessage: Message = {
                id: `clarification-${Date.now()}`,
                type: 'bot',
                content: eventData.message || 'I need some additional information to generate the best infrastructure code for you.',
                timestamp: new Date(eventData.timestamp || Date.now()),
                status: 'clarifying',
                is_clarification_request: true,
                clarification_questions: (eventData.questions || []).map((q: any, index: number) => ({
                  id: `q-${index}`,
                  question: typeof q === 'string' ? q : q.question || q.text || `Question ${index + 1}`,
                  type: q.type || 'text',
                  options: q.options || undefined
                }))
              };
              setMessages(prev => [...prev, clarificationMessage]);
              setMessagesKey(prev => prev + 1);
            }
            break;

          case 'terraform_generation_completed':
            console.log('✅ Processing terraform generation completed:', eventData);
            setIsGenerating(false);
            setGenerationProgress(null);

            // Add final completion message to chat with generation_id
            if (selectedThread && eventData.thread_id === selectedThread.thread_id) {
              const completionMessage: Message = {
                id: `completed-${Date.now()}`,
                type: 'system',
                content: `✅ Generated ${eventData.generated_files?.length || 0} files successfully`,
                timestamp: new Date(eventData.timestamp || Date.now()),
                status: 'completed',
                generation_id: eventData.job_id
              };
              setMessages(prev => [...prev, completionMessage]);
              setMessagesKey(prev => prev + 1);
            }
            break;

          case 'terraform_generation_failed':
            console.log('❌ Processing terraform generation failed:', eventData);
            setIsGenerating(false);
            setGenerationProgress(null);
            break;

          // Fallback cases for older event formats
          case 'generation_progress':
          case 'clarification_request':
          case 'generation_completed':
          case 'generation_failed':
            console.log(`📋 Handling legacy event: ${eventType}`);
            // Handle legacy events with the old logic if needed
            break;

          default:
            console.log('❓ Unknown event type:', eventType, eventData);
        }
      };


      // All terraform events are now handled by the main 'message' listener

      socketRef.current = socket;
    } catch (error) {
      console.error('Failed to initialize WebSocket:', error);
    }
  }, [projectId, selectedThread]);

  // Cleanup WebSocket on unmount
  const cleanupWebSocket = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.disconnect();
      socketRef.current = null;
      setIsConnected(false);
    }
  }, []);

  // Initial load and WebSocket connection
  useEffect(() => {
    if (projectId && userId) {
      fetchThreads();
      // Initialize WebSocket connection
      initWebSocket();
    }

    return () => {
      cleanupWebSocket();
    };
  }, [projectId, userId, fetchThreads, initWebSocket, cleanupWebSocket]);

  // Respond to clarification
  const respondToClarification = useCallback(async (responses: { [key: string]: string }) => {
    try {
      setSendingMessage(true);
      const token = await getAuthToken();

      const response = await fetch(`${API_BASE_URL}/api/v1/projects/${projectId}/terraform-chat/clarifications/${selectedThread?.thread_id}/respond`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          responses
        })
      });

      if (!response.ok) {
        throw new Error(`Failed to respond to clarification: ${response.status}`);
      }

      // Close the clarification dialog
      setClarificationDialog({
        isOpen: false,
        questions: [],
        context_summary: ''
      });

    } catch (error) {
      console.error('Error responding to clarification:', error);
      throw error;
    } finally {
      setSendingMessage(false);
    }
  }, [projectId, selectedThread]);

  // Manual WebSocket reconnection
  const reconnectWebSocket = useCallback(async () => {
    console.log('🔄 Manual WebSocket reconnection requested');
    if (socketRef.current) {
      socketRef.current.disconnect();
      socketRef.current = null;
      setIsConnected(false);
    }
    await initWebSocket();
  }, []);

  return {
    threads,
    selectedThread,
    messages,
    messagesKey, // Force re-render key
    loading,
    loadingMessages,
    hasMore,
    isConnected,
    sendingMessage,
    isGenerating,
    generationProgress,
    clarificationDialog,
    selectThread,
    createNewThread,
    loadMoreMessages,
    loadMoreThreads,
    sendMessage,
    respondToClarification,
    reconnectWebSocket,
    refreshThreads: () => fetchThreads()
  };
};