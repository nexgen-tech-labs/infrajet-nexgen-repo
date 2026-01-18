import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
    MoreHorizontal,
    Github,
    Calendar,
    FileText,
    HardDrive,
    Trash2,
    ExternalLink,
    RefreshCw,
    Plus
} from 'lucide-react';
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useProjects, useDeleteProject } from '@/hooks/useProjects';
import { usePushProjectToGitHub, useProjectGitHubStatus } from '@/hooks/useGitHubIntegration';
import { Project } from '@/services/infrajetApi';
import { formatDistanceToNow } from 'date-fns';

interface ProjectListProps {
    onSelectProject?: (project: Project) => void;
    onCreateProject?: () => void;
}

const ProjectCard: React.FC<{
    project: Project;
    onSelect?: (project: Project) => void;
}> = ({ project, onSelect }) => {
    const deleteMutation = useDeleteProject();
    const syncMutation = usePushProjectToGitHub(project.id);
    const { data: githubStatus, isLoading: githubLoading } = useProjectGitHubStatus(project.id);

    const handleDelete = async () => {
        if (window.confirm('Are you sure you want to delete this project?')) {
            deleteMutation.mutate({ projectId: project.id });
        }
    };

    const handleSync = async () => {
        syncMutation.mutate({ commit_message: 'Manual sync from InfraJet' });
    };

    // Determine GitHub status for UI
    const isGitHubLinked = githubStatus?.data?.github_linked || project.github_linked;
    const githubRepoName = githubStatus?.data?.github_repo_name || project.github_repo_name;
    const lastSync = githubStatus?.data?.last_github_sync || project.last_github_sync;

    const formatFileSize = (bytes: number) => {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };

    return (
        <Card className="hover:shadow-md transition-shadow cursor-pointer">
            <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                    <div className="flex-1" onClick={() => onSelect?.(project)}>
                        <CardTitle className="text-lg font-semibold">{project.name}</CardTitle>
                        <CardDescription className="mt-1 line-clamp-2">
                            {project.description}
                        </CardDescription>
                    </div>
                    <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="sm">
                                <MoreHorizontal className="h-4 w-4" />
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => onSelect?.(project)}>
                                <ExternalLink className="h-4 w-4 mr-2" />
                                Open Project
                            </DropdownMenuItem>
                            {isGitHubLinked && (
                                <DropdownMenuItem
                                    onClick={handleSync}
                                    disabled={syncMutation.isPending}
                                >
                                    <RefreshCw className={`h-4 w-4 mr-2 ${syncMutation.isPending ? 'animate-spin' : ''}`} />
                                    Sync with GitHub
                                </DropdownMenuItem>
                            )}
                            <DropdownMenuItem
                                onClick={handleDelete}
                                disabled={deleteMutation.isPending}
                                className="text-red-600"
                            >
                                <Trash2 className="h-4 w-4 mr-2" />
                                Delete Project
                            </DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>
                </div>
            </CardHeader>
            <CardContent>
                <div className="space-y-3">
                    {/* Status and GitHub */}
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <Badge variant={project.status === 'active' ? 'default' : 'secondary'}>
                                {project.status}
                            </Badge>
                            {githubLoading ? (
                                <div className="flex items-center text-sm text-muted-foreground">
                                    <RefreshCw className="h-3 w-3 mr-1 animate-spin" />
                                    Checking GitHub...
                                </div>
                            ) : isGitHubLinked ? (
                                <div className="flex items-center text-sm text-green-600">
                                    <Github className="h-4 w-4 mr-1" />
                                    <span className="font-medium">Linked</span>
                                </div>
                            ) : (
                                <div className="flex items-center text-sm text-orange-600">
                                    <Github className="h-4 w-4 mr-1" />
                                    <span className="font-medium">Not Linked</span>
                                </div>
                            )}
                        </div>
                        {isGitHubLinked && githubRepoName && (
                            <div className="flex items-center text-sm text-muted-foreground">
                                <span>{githubRepoName}</span>
                            </div>
                        )}
                    </div>

                    {/* File info */}
                    {(project.file_count !== undefined || project.total_size !== undefined) && (
                        <div className="flex items-center justify-between text-sm text-muted-foreground">
                            {project.file_count !== undefined && (
                                <div className="flex items-center">
                                    <FileText className="h-4 w-4 mr-1" />
                                    {project.file_count} files
                                </div>
                            )}
                            {project.total_size !== undefined && (
                                <div className="flex items-center">
                                    <HardDrive className="h-4 w-4 mr-1" />
                                    {formatFileSize(project.total_size)}
                                </div>
                            )}
                        </div>
                    )}

                    {/* Timestamps */}
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                        <div className="flex items-center">
                            <Calendar className="h-3 w-3 mr-1" />
                            Created {formatDistanceToNow(new Date(project.created_at), { addSuffix: true })}
                        </div>
                        {lastSync && (
                            <div>
                                Last sync {formatDistanceToNow(new Date(lastSync), { addSuffix: true })}
                            </div>
                        )}
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};

const ProjectListSkeleton: React.FC = () => (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i}>
                <CardHeader>
                    <Skeleton className="h-6 w-3/4" />
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-2/3" />
                </CardHeader>
                <CardContent>
                    <div className="space-y-3">
                        <div className="flex justify-between">
                            <Skeleton className="h-5 w-16" />
                            <Skeleton className="h-4 w-20" />
                        </div>
                        <div className="flex justify-between">
                            <Skeleton className="h-4 w-12" />
                            <Skeleton className="h-4 w-16" />
                        </div>
                        <Skeleton className="h-3 w-full" />
                    </div>
                </CardContent>
            </Card>
        ))}
    </div>
);

export const ProjectList: React.FC<ProjectListProps> = ({
    onSelectProject,
    onCreateProject
}) => {
    const { data, isLoading, error, refetch } = useProjects({
        include_files: true,
        include_github_info: true,
    });

    if (isLoading) {
        return <ProjectListSkeleton />;
    }

    if (error) {
        return (
            <Card>
                <CardContent className="pt-6">
                    <div className="text-center space-y-4">
                        <div className="text-red-600">
                            Failed to load projects: {error.message}
                        </div>
                        <Button onClick={() => refetch()} variant="outline">
                            <RefreshCw className="h-4 w-4 mr-2" />
                            Try Again
                        </Button>
                    </div>
                </CardContent>
            </Card>
        );
    }

    const projects = data?.projects || [];

    if (projects.length === 0) {
        return (
            <Card>
                <CardContent className="pt-6">
                    <div className="text-center space-y-4">
                        <div className="text-muted-foreground">
                            No projects found. Create your first project to get started.
                        </div>
                        {onCreateProject && (
                            <Button onClick={onCreateProject}>
                                <Plus className="h-4 w-4 mr-2" />
                                Create Project
                            </Button>
                        )}
                    </div>
                </CardContent>
            </Card>
        );
    }

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold">Projects</h2>
                    <p className="text-muted-foreground">
                        {data?.total_count} project{data?.total_count !== 1 ? 's' : ''} total
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <Button onClick={() => refetch()} variant="outline" size="sm">
                        <RefreshCw className="h-4 w-4 mr-2" />
                        Refresh
                    </Button>
                    {onCreateProject && (
                        <Button onClick={onCreateProject}>
                            <Plus className="h-4 w-4 mr-2" />
                            Create Project
                        </Button>
                    )}
                </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {projects.map((project) => (
                    <ProjectCard
                        key={project.id}
                        project={project}
                        onSelect={onSelectProject}
                    />
                ))}
            </div>
        </div>
    );
};