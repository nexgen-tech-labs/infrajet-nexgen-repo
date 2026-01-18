import { useState, useCallback } from 'react';

export interface ConversationMessage {
    id: string;
    type: 'user' | 'assistant' | 'system' | 'event';
    content: string;
    timestamp: string;
}

export interface ConversationThread {
    thread_id: string;
    title: string;
    message_count: number;
    last_message_at: string;
}

export interface ClarificationDialog {
    request_id: string;
    questions: Array<{
        id: string;
        question: string;
        type: 'text' | 'select' | 'boolean';
        options?: string[];
    }>;
    context_summary: string;
}

export interface GenerationProgress {
    status: string;
    progress_percentage: number;
    current_step: string;
}

export const useInfraJetAutonomousChat = () => {
    const [isConnected, setIsConnected] = useState(false);
    const [isGenerating, setIsGenerating] = useState(false);
    const [currentThreadId, setCurrentThreadId] = useState<string | null>(null);
    const [messages, setMessages] = useState<ConversationMessage[]>([]);
    const [clarificationDialog, setClarificationDialog] = useState<ClarificationDialog | null>(null);
    const [generationProgress, setGenerationProgress] = useState<GenerationProgress | null>(null);

    const initChat = useCallback(() => {
        // Initialize chat connection
        setIsConnected(true);
    }, []);

    const sendMessage = useCallback(async (content: string) => {
        const newMessage: ConversationMessage = {
            id: Date.now().toString(),
            type: 'user',
            content,
            timestamp: new Date().toISOString(),
        };

        setMessages(prev => [...prev, newMessage]);

        // Simulate AI response
        setTimeout(() => {
            const aiResponse: ConversationMessage = {
                id: (Date.now() + 1).toString(),
                type: 'assistant',
                content: 'This is a placeholder response. The actual InfraJet AI integration will be implemented here.',
                timestamp: new Date().toISOString(),
            };
            setMessages(prev => [...prev, aiResponse]);
        }, 1000);

        return { success: true };
    }, []);

    const respondToClarification = useCallback(async (requestId: string, responses: { [key: string]: string }) => {
        setClarificationDialog(null);
        return { success: true };
    }, []);

    const getConversationThreads = useCallback(async (): Promise<ConversationThread[]> => {
        return [];
    }, []);

    const switchToThread = useCallback((threadId: string) => {
        setCurrentThreadId(threadId);
        setMessages([]);
    }, []);

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
        getConversationThreads,
        switchToThread,
    };
};