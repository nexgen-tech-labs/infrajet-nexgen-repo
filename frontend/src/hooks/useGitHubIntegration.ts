import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
    githubApi,
    GitHubInstallation,
    CreateRepoRequest,
    PushFilesRequest,
    LinkProjectToGitHubRequest
} from '@/services/infrajetApi';
import { supabase } from '@/integrations/supabase/client';
import { useToast } from '@/hooks/use-toast';

// Query Keys
export const githubKeys = {
    all: ['github'] as const,
    installations: () => [...githubKeys.all, 'installations'] as const,
    repositories: () => [...githubKeys.all, 'repositories'] as const,
    projects: () => [...githubKeys.all, 'projects'] as const,
    projectLink: (projectId: string) => [...githubKeys.projects(), projectId, 'link'] as const,
};

// Hooks
export const useGitHubInstallations = (githubToken: string) => {
    return useQuery({
        queryKey: githubKeys.installations(),
        queryFn: async () => {
            // For now, return empty array since installations are handled differently
            return [];
        },
        enabled: !!githubToken,
        staleTime: 10 * 60 * 1000, // 10 minutes
    });
};

export const useCreateRepository = () => {
    const queryClient = useQueryClient();
    const { toast } = useToast();

    return useMutation({
        mutationFn: (data: CreateRepoRequest) => githubApi.createRepository(data),
        onSuccess: (data) => {
            // Invalidate repositories cache
            queryClient.invalidateQueries({ queryKey: githubKeys.repositories() });

            toast({
                title: "Repository created successfully",
                description: `Repository "${data.data?.name || data.name}" has been created.`,
            });
        },
        onError: (error: Error) => {
            toast({
                title: "Failed to create repository",
                description: error.message,
                variant: "destructive",
            });
        },
    });
};

export const usePushFiles = () => {
    const { toast } = useToast();

    return useMutation({
        mutationFn: async (data: PushFilesRequest) => {
            const { data: result, error } = await supabase.functions.invoke('github-push', {
                body: {
                    repoFullName: `${data.repo_owner}/${data.repo_name}`,
                    files: data.files,
                    commitMessage: 'Files synced from InfraJet'
                }
            });

            if (error) {
                throw new Error(`Failed to push files: ${error.message}`);
            }

            return result;
        },
        onSuccess: (data) => {
            toast({
                title: "Files pushed successfully",
                description: `Files have been pushed to the repository.`,
            });
        },
        onError: (error: Error) => {
            toast({
                title: "Failed to push files",
                description: error.message,
                variant: "destructive",
            });
        },
    });
};

export const useSyncRepository = () => {
    const { toast } = useToast();

    return useMutation({
        mutationFn: async ({
            installationId,
            repoOwner,
            repoName
        }: {
            installationId: number;
            repoOwner: string;
            repoName: string;
        }) => {
            // For now, this is a placeholder - sync functionality might be handled differently
            return { success: true };
        },
        onSuccess: () => {
            toast({
                title: "Repository synced successfully",
                description: "Repository has been synchronized.",
            });
        },
        onError: (error: Error) => {
            toast({
                title: "Failed to sync repository",
                description: error.message,
                variant: "destructive",
            });
        },
    });
};

export const useLinkProjectToGitHub = (projectId: string) => {
    const queryClient = useQueryClient();
    const { toast } = useToast();

    return useMutation({
        mutationFn: (data: LinkProjectToGitHubRequest) => githubApi.linkProjectToGitHub(projectId, data),
        onSuccess: (data) => {
            // Invalidate project data to refresh GitHub link status
            queryClient.invalidateQueries({
                queryKey: ['projects', 'detail', projectId]
            });

            toast({
                title: "Project linked to GitHub successfully",
                description: "Project has been linked to GitHub.",
            });
        },
        onError: (error: Error) => {
            toast({
                title: "Failed to link project to GitHub",
                description: error.message,
                variant: "destructive",
            });
        },
    });
};

export const usePushProjectToGitHub = (projectId: string) => {
    const queryClient = useQueryClient();
    const { toast } = useToast();

    return useMutation({
        mutationFn: (data: { generation_id?: string; commit_message: string }) => githubApi.pushProjectToGitHub(projectId, data),
        onSuccess: (data) => {
            // Invalidate project data to refresh sync status
            queryClient.invalidateQueries({
                queryKey: ['projects', 'detail', projectId]
            });

            toast({
                title: "Project files pushed to GitHub successfully",
                description: "Project files have been pushed to the linked repository.",
            });
        },
        onError: (error: Error) => {
            toast({
                title: "Failed to push project files to GitHub",
                description: error.message,
                variant: "destructive",
            });
        },
    });
};

export const useAutoSyncGeneration = () => {
    const { toast } = useToast();

    return useMutation({
        mutationFn: (generationId: string) => githubApi.autoSyncGeneration(generationId),
        onSuccess: (data) => {
            toast({
                title: "Generation auto-synced successfully",
                description: "Generation has been automatically synced to GitHub.",
            });
        },
        onError: (error: Error) => {
            toast({
                title: "Failed to auto-sync generation",
                description: error.message,
                variant: "destructive",
            });
        },
    });
};

export const useProjectGitHubStatus = (projectId: string) => {
    return useQuery({
        queryKey: ['github', 'project-status', projectId],
        queryFn: () => githubApi.getProjectGitHubStatus(projectId),
        enabled: !!projectId,
        staleTime: 30 * 1000, // 30 seconds
        refetchInterval: 60 * 1000, // Refetch every minute
    });
};

// Custom hook for managing GitHub integration flow
export const useGitHubIntegrationFlow = (projectId: string, githubToken?: string) => {
    const { data: installations, isLoading: loadingInstallations } = useGitHubInstallations(
        githubToken || ''
    );
    const linkMutation = useLinkProjectToGitHub(projectId);
    const pushProjectMutation = usePushProjectToGitHub(projectId);
    const createRepoMutation = useCreateRepository();
    const pushFilesMutation = usePushFiles();

    const linkToGitHub = async (data: LinkProjectToGitHubRequest) => {
        return linkMutation.mutateAsync(data);
    };

    const pushToGitHub = async (data: { generation_id?: string; commit_message: string }) => {
        return pushProjectMutation.mutateAsync(data);
    };

    const createRepository = async (data: CreateRepoRequest) => {
        return createRepoMutation.mutateAsync(data);
    };

    const pushFiles = async (data: PushFilesRequest) => {
        return pushFilesMutation.mutateAsync(data);
    };

    return {
        installations: installations || [],
        loadingInstallations,
        linkToGitHub,
        pushToGitHub,
        createRepository,
        pushFiles,
        isLinking: linkMutation.isPending,
        isPushingProject: pushProjectMutation.isPending,
        isCreatingRepo: createRepoMutation.isPending,
        isPushing: pushFilesMutation.isPending,
        linkError: linkMutation.error,
        pushProjectError: pushProjectMutation.error,
        createError: createRepoMutation.error,
        pushError: pushFilesMutation.error,
    };
};