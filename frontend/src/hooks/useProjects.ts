import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { projectApi, CreateProjectRequest, Project } from '@/services/infrajetApi';
import { useToast } from '@/hooks/use-toast';

// Query Keys
export const projectKeys = {
    all: ['projects'] as const,
    lists: () => [...projectKeys.all, 'list'] as const,
    list: (filters: Record<string, any>) => [...projectKeys.lists(), filters] as const,
    details: () => [...projectKeys.all, 'detail'] as const,
    detail: (id: string) => [...projectKeys.details(), id] as const,
};

// Hooks
export const useProjects = (params?: {
    include_files?: boolean;
    include_github_info?: boolean;
    status_filter?: string;
}) => {
    return useQuery({
        queryKey: projectKeys.list(params || {}),
        queryFn: () => projectApi.list(params),
        select: (data) => ({
            ...data,
            projects: data?.projects || [],
        }),
        staleTime: 5 * 60 * 1000, // 5 minutes
    });
};

export const useProject = (projectId: string) => {
    return useQuery({
        queryKey: projectKeys.detail(projectId),
        queryFn: () => projectApi.getById(projectId),
        enabled: !!projectId,
        staleTime: 5 * 60 * 1000, // 5 minutes
    });
};

export const useCreateProject = () => {
    const queryClient = useQueryClient();
    const { toast } = useToast();

    return useMutation({
        mutationFn: (data: CreateProjectRequest) => projectApi.create(data),
        onSuccess: (data) => {
            // Invalidate and refetch projects list
            queryClient.invalidateQueries({ queryKey: projectKeys.lists() });

            // Add the new project to the cache
            queryClient.setQueryData(
                projectKeys.detail(data.project.id),
                data.project
            );

            toast({
                title: "Project created successfully",
                description: data.message,
            });
        },
        onError: (error: Error) => {
            toast({
                title: "Failed to create project",
                description: error.message,
                variant: "destructive",
            });
        },
    });
};

export const useUpdateProject = () => {
    const queryClient = useQueryClient();
    const { toast } = useToast();

    return useMutation({
        mutationFn: (data: CreateProjectRequest) => projectApi.create(data),
        onSuccess: (data) => {
            // Invalidate and refetch projects list
            queryClient.invalidateQueries({ queryKey: projectKeys.lists() });

            // Update the project in the cache
            queryClient.setQueryData(
                projectKeys.detail(data.project.id),
                data.project
            );

            toast({
                title: "Project updated successfully",
                description: data.message,
            });
        },
        onError: (error: Error) => {
            toast({
                title: "Failed to update project",
                description: error.message,
                variant: "destructive",
            });
        },
    });
};

export const useDeleteProject = () => {
    const queryClient = useQueryClient();
    const { toast } = useToast();

    return useMutation({
        mutationFn: ({
            projectId,
            options
        }: {
            projectId: string;
            options?: { delete_github_repo?: boolean; soft_delete?: boolean }
        }) => projectApi.delete(projectId, options),
        onSuccess: (_, variables) => {
            // Remove from cache
            queryClient.removeQueries({ queryKey: projectKeys.detail(variables.projectId) });

            // Invalidate projects list
            queryClient.invalidateQueries({ queryKey: projectKeys.lists() });

            toast({
                title: "Project deleted successfully",
                description: "The project has been removed.",
            });
        },
        onError: (error: Error) => {
            toast({
                title: "Failed to delete project",
                description: error.message,
                variant: "destructive",
            });
        },
    });
};