import { useState, useEffect, useRef, useCallback } from 'react';
import { InfraJetChat, ChatMessage, Generation, GenerationFile } from '@/services/infrajetApi';
import { getAuthToken } from '@/services/infrajetApi';
import { useToast } from '@/hooks/use-toast';

interface UseInfraJetChatOptions {
    onGenerationStarted?: (data: any) => void;
    onGenerationProgress?: (data: any) => void;
    onGenerationCompleted?: (data: any) => void;
    autoConnect?: boolean;
}

export const useInfraJetChat = (projectId: string, options: UseInfraJetChatOptions = {}) => {
    const {
        onGenerationStarted,
        onGenerationProgress,
        onGenerationCompleted,
        autoConnect = true
    } = options;

    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [generations, setGenerations] = useState<Generation[]>([]);
    const [isConnected, setIsConnected] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [isSending, setIsSending] = useState(false);
    const [generationStatus, setGenerationStatus] = useState<{
        isGenerating: boolean;
        message?: string;
        progress?: number;
        currentStep?: string;
        status?: string;
    }>({ isGenerating: false });

    const chatRef = useRef<InfraJetChat | null>(null);
    const { toast } = useToast();

    // Initialize chat
    const initializeChat = useCallback(async () => {
        if (chatRef.current) return;

        try {
            const token = await getAuthToken();
            chatRef.current = new InfraJetChat(projectId, token);

            // Set up WebSocket handlers
            chatRef.current.onGenerationStarted((data) => {
                setGenerationStatus({
                    isGenerating: true,
                    message: data.message || '🤖 Starting code generation...'
                });
                onGenerationStarted?.(data);
            });

            chatRef.current.onGenerationProgress((data) => {
                setGenerationStatus({
                    isGenerating: data.data.status !== 'completed' && data.data.status !== 'failed',
                    message: data.data.current_step || 'Generating code...',
                    progress: data.data.progress_percentage,
                    currentStep: data.data.current_step,
                    status: data.data.status
                });
                onGenerationProgress?.(data);
            });

            chatRef.current.onGenerationCompleted((data) => {
                setGenerationStatus({
                    isGenerating: false,
                    message: '✅ Generated files successfully!'
                });
                // Clear status after delay
                setTimeout(() => setGenerationStatus({ isGenerating: false }), 3000);
                // Refresh data
                loadChatHistory();
                loadGenerations();
                onGenerationCompleted?.(data);
            });

            // Initialize WebSocket
            await chatRef.current.initWebSocket();
            setIsConnected(true);

            // Load initial data
            await loadChatHistory();
            await loadGenerations();
        } catch (error) {
            console.error('Failed to initialize chat:', error);
            toast({
                title: "Connection Error",
                description: "Failed to connect to chat service",
                variant: "destructive",
            });
        }
    }, [projectId, onGenerationStarted, onGenerationProgress, onGenerationCompleted]);

    // Load chat history
    const loadChatHistory = useCallback(async () => {
        if (!chatRef.current) return;

        setIsLoading(true);
        try {
            const response = await chatRef.current.getChatHistory();
            setMessages(response.messages || []);
        } catch (error) {
            console.error('Failed to load chat history:', error);
            toast({
                title: "Failed to load messages",
                description: "Please refresh the page",
                variant: "destructive",
            });
            setMessages([]);
        } finally {
            setIsLoading(false);
        }
    }, []);

    // Load generations
    const loadGenerations = useCallback(async () => {
        if (!chatRef.current) return;

        try {
            const response = await chatRef.current.getGenerations();
            setGenerations(response.generations || []);
        } catch (error) {
            console.error('Failed to load generations:', error);
            setGenerations([]);
        }
    }, []);

    // Send message
    const sendMessage = useCallback(async (content: string, type: 'user' | 'system' | 'ai' = 'user') => {
        if (!chatRef.current || !content.trim()) return;

        setIsSending(true);
        try {
            await chatRef.current.sendMessage(content, type);
            await loadChatHistory(); // Refresh to show new message
        } catch (error) {
            console.error('Failed to send message:', error);
            toast({
                title: "Failed to send message",
                description: "Please try again",
                variant: "destructive",
            });
        } finally {
            setIsSending(false);
        }
    }, [loadChatHistory]);

    // Get generation files
    const getGenerationFiles = useCallback(async (generationId: string, includeContent = false): Promise<GenerationFile[]> => {
        if (!chatRef.current) return [];

        try {
            const response = await chatRef.current.getGenerationFiles(generationId, includeContent);
            return response.files;
        } catch (error) {
            console.error('Failed to load generation files:', error);
            toast({
                title: "Failed to load files",
                description: "Please try again",
                variant: "destructive",
            });
            return [];
        }
    }, []);

    // Get specific file
    const getGenerationFile = useCallback(async (generationId: string, filePath: string): Promise<string> => {
        if (!chatRef.current) return '';

        try {
            const response = await chatRef.current.getGenerationFile(generationId, filePath);
            return response.content;
        } catch (error) {
            console.error('Failed to load file:', error);
            toast({
                title: "Failed to load file",
                description: "Please try again",
                variant: "destructive",
            });
            return '';
        }
    }, []);

    // Disconnect
    const disconnect = useCallback(() => {
        if (chatRef.current) {
            chatRef.current.disconnect();
            chatRef.current = null;
        }
        setIsConnected(false);
    }, []);

    // Auto-initialize on mount
    useEffect(() => {
        if (autoConnect) {
            initializeChat();
        }

        return () => {
            disconnect();
        };
    }, [autoConnect, initializeChat, disconnect]);

    return {
        // State
        messages,
        generations,
        isConnected,
        isLoading,
        isSending,
        generationStatus,

        // Actions
        sendMessage,
        loadChatHistory,
        loadGenerations,
        getGenerationFiles,
        getGenerationFile,
        initializeChat,
        disconnect,

        // Chat instance (for advanced usage)
        chat: chatRef.current,
    };
};

// Utility hook for file downloads
export const useFileDownload = () => {
    const { toast } = useToast();

    const downloadFile = useCallback((filename: string, content: string) => {
        try {
            const blob = new Blob([content], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            a.click();
            URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Failed to download file:', error);
            toast({
                title: "Download failed",
                description: "Please try again",
                variant: "destructive",
            });
        }
    }, [toast]);

    const downloadAsZip = useCallback(async (files: GenerationFile[], filename: string) => {
        try {
            // Dynamic import to avoid bundling JSZip if not used
            const JSZip = (await import('jszip')).default;
            const zip = new JSZip();

            files.forEach(file => {
                zip.file(file.name, file.content || '');
            });

            const content = await zip.generateAsync({ type: 'blob' });
            const url = URL.createObjectURL(content);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            a.click();
            URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Failed to download zip:', error);
            toast({
                title: "Download failed",
                description: "Please try again",
                variant: "destructive",
            });
        }
    }, [toast]);

    return {
        downloadFile,
        downloadAsZip,
    };
};