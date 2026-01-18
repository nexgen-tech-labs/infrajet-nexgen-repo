import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { chatApi, SaveMessageRequest, ChatMessage } from '@/services/infrajetApi';
import { useToast } from '@/hooks/use-toast';

// Query Keys
export const chatKeys = {
    all: ['chat'] as const,
    projects: () => [...chatKeys.all, 'project'] as const,
    project: (projectId: string) => [...chatKeys.projects(), projectId] as const,
    messages: (projectId: string, params?: Record<string, any>) =>
        [...chatKeys.project(projectId), 'messages', params] as const,
};

// Hooks
export const useChatMessages = (projectId: string, params?: {
    limit?: number;
    offset?: number;
}) => {
    return useQuery({
        queryKey: chatKeys.messages(projectId, params),
        queryFn: () => chatApi.getMessages(projectId, params),
        enabled: !!projectId,
        staleTime: 1 * 60 * 1000, // 1 minute
    });
};

export const useSaveMessage = (projectId: string) => {
    const queryClient = useQueryClient();
    const { toast } = useToast();

    return useMutation({
        mutationFn: (data: SaveMessageRequest) => chatApi.saveMessage(projectId, data),
        onSuccess: (data) => {
            // Add the new message to the cache
            queryClient.setQueryData(
                chatKeys.messages(projectId),
                (oldData: any) => {
                    if (!oldData) return { messages: [data.message], total_count: 1 };

                    return {
                        ...oldData,
                        messages: [...oldData.messages, data.message],
                        total_count: oldData.total_count + 1,
                    };
                }
            );
        },
        onError: (error: Error) => {
            toast({
                title: "Failed to save message",
                description: error.message,
                variant: "destructive",
            });
        },
    });
};

// Custom hook for managing chat state
export const useChatState = (projectId: string) => {
    const { data: messagesData, isLoading, error } = useChatMessages(projectId);
    const saveMessageMutation = useSaveMessage(projectId);

    const sendMessage = async (content: string, type: 'user' | 'system' | 'ai' = 'user') => {
        return saveMessageMutation.mutateAsync({
            message_content: content,
            message_type: type,
        });
    };

    return {
        messages: messagesData?.messages || [],
        totalCount: messagesData?.total_count || 0,
        isLoading,
        error,
        sendMessage,
        isSending: saveMessageMutation.isPending,
        sendError: saveMessageMutation.error,
    };
};