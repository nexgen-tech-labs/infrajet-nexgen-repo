import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
    Plus,
    Search,
    Filter,
    MoreHorizontal,
    Grid3X3,
    List,
    Calendar,
    Github,
    FileText,
    Settings,
    Trash2,
    ExternalLink,
    RefreshCw,
    Eye,
    Edit,
    FolderOpen,
    Activity,
    Link,
    Database,
    MessageSquare,
    ArrowLeft
} from 'lucide-react';
import { useProjects, useDeleteProject } from '@/hooks/useProjects';
import { usePushProjectToGitHub } from '@/hooks/useGitHubIntegration';
import { CreateProjectDialog } from '@/components/projects/CreateProjectDialog';
import { ProjectDashboard } from '@/components/projects/ProjectDashboard';
import { GitHubConnectButton } from '@/components/github/GitHubConnectButton';
import { Project } from '@/services/infrajetApi';
import { useAuth } from '@/contexts/AuthContext';
import { formatDistanceToNow } from 'date-fns';
import { useToast } from '@/hooks/use-toast';
import BackendStatus from '@/components/system/BackendStatus';

type ViewMode = 'grid' | 'list';
type SortBy = 'name' | 'created_at' | 'updated_at' | 'status';
type FilterBy = 'all' | 'active' | 'inactive' | 'github_linked' | 'github_unlinked';

const ProjectManagement: React.FC = () => {
    const { projectId } = useParams<{ projectId: string }>();
    const navigate = useNavigate();
    const [selectedProject, setSelectedProject] = useState<Project | null>(null);
    const [showCreateDialog, setShowCreateDialog] = useState(false);
    const [viewMode, setViewMode] = useState<ViewMode>('grid');
    const [searchQuery, setSearchQuery] = useState('');
    const [sortBy, setSortBy] = useState<SortBy>('updated_at');
    const [filterBy, setFilterBy] = useState<FilterBy>('all');

    const { user } = useAuth();
    const { toast } = useToast();

    // Get GitHub token from user metadata
    const githubToken = user?.user_metadata?.github_token;

    // Fetch projects with backend integration
    const {
        data: projectsData,
        isLoading,
        error,
        refetch
    } = useProjects({
        include_files: true,
        include_github_info: true,
        status_filter: filterBy === 'all' ? undefined : filterBy.replace('github_', ''),
    });

    const deleteProjectMutation = useDeleteProject();

    // Auto-select project from URL parameter
    useEffect(() => {
        if (projectId && projectsData?.projects) {
            const project = projectsData.projects.find(p => p.id === projectId);
            if (project) {
                setSelectedProject(project);
            }
        }
    }, [projectId, projectsData?.projects]);

    // Filter and sort projects based on user input
    const filteredAndSortedProjects = React.useMemo(() => {
        if (!projectsData?.projects) return [];

        let filtered = projectsData.projects || [];

        // Apply search filter
        if (searchQuery) {
            filtered = filtered.filter(project =>
                project.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                project.description.toLowerCase().includes(searchQuery.toLowerCase())
            );
        }

        // Apply status filter
        if (filterBy !== 'all') {
            if (filterBy === 'github_linked') {
                filtered = filtered.filter(project => project.github_linked);
            } else if (filterBy === 'github_unlinked') {
                filtered = filtered.filter(project => !project.github_linked);
            } else {
                filtered = filtered.filter(project => project.status === filterBy);
            }
        }

        // Apply sorting
        filtered.sort((a, b) => {
            switch (sortBy) {
                case 'name':
                    return a.name.localeCompare(b.name);
                case 'created_at':
                    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
                case 'updated_at':
                    return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
                case 'status':
                    return a.status.localeCompare(b.status);
                default:
                    return 0;
            }
        });

        return filtered;
    }, [projectsData?.projects, searchQuery, filterBy, sortBy]);

    const handleSelectProject = (project: Project) => {
        setSelectedProject(project);
    };

    const handleBackToList = () => {
        setSelectedProject(null);
        // Navigate back to projects list without project ID
        navigate('/projects');
    };

    const handleDeleteProject = async (projectId: string, projectName: string) => {
        if (window.confirm(`Are you sure you want to delete "${projectName}"? This action cannot be undone.`)) {
            try {
                await deleteProjectMutation.mutateAsync({ projectId });
                if (selectedProject?.id === projectId) {
                    setSelectedProject(null);
                }
            } catch (error) {
                // Error handled by mutation
            }
        }
    };

    const handleRefresh = () => {
        refetch();
        toast({
            title: "Projects refreshed",
            description: "Project list has been updated from the server.",
        });
    };

    const handleGoToApp = () => {
        navigate('/app');
    };

    // Show project dashboard if a project is selected
    if (selectedProject) {
        return (
            <div className="min-h-screen bg-background">
                <ProjectDashboard
                    projectId={selectedProject.id}
                    onBack={handleBackToList}
                    githubToken={githubToken}
                />
            </div>
        );
    }

    // Show loading state
    if (isLoading) {
        return (
            <div className="min-h-screen bg-background">
                <div className="container mx-auto py-8 px-4">
                    <div className="space-y-6">
                        <div className="flex items-center justify-between">
                            <div className="space-y-2">
                                <div className="h-8 w-48 bg-muted animate-pulse rounded" />
                                <div className="h-4 w-32 bg-muted animate-pulse rounded" />
                            </div>
                            <div className="h-10 w-32 bg-muted animate-pulse rounded" />
                        </div>
                        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                            {Array.from({ length: 6 }).map((_, i) => (
                                <div key={i} className="h-48 bg-muted animate-pulse rounded-lg" />
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    // Show error state
    if (error) {
        return (
            <div className="min-h-screen bg-background">
                <div className="container mx-auto py-8 px-4">
                    <div className="space-y-6">
                        <Card>
                            <CardContent className="pt-6">
                                <div className="text-center space-y-4">
                                    <div className="text-red-600">
                                        Failed to load projects: {error.message}
                                    </div>
                                    <Button onClick={handleRefresh} variant="outline">
                                        <RefreshCw className="h-4 w-4 mr-2" />
                                        Try Again
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>

                        {/* Show backend status when there are connection issues */}
                        <BackendStatus />
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-background">
            <div className="container mx-auto py-8 px-4">
                <div className="space-y-6">
                    {/* Header */}
                    <div className="relative overflow-hidden rounded-xl bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20 p-6 mb-6">
                        <div className="flex items-center justify-between">
                            <div className="space-y-2">
                                <div className="flex items-center gap-3">
                                    <div className="p-2 bg-blue-100 dark:bg-blue-900/50 rounded-lg">
                                        <FolderOpen className="h-6 w-6 text-blue-600 dark:text-blue-400" />
                                    </div>
                                    <div>
                                        <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
                                            Project Management
                                        </h1>
                                        <p className="text-muted-foreground">
                                            Manage your infrastructure projects and collaborate with your team
                                        </p>
                                    </div>
                                </div>
                            </div>
                            <div className="flex items-center gap-3">
                                <Button onClick={handleGoToApp} variant="outline" size="sm" className="hover:bg-white/50 transition-colors">
                                    <ArrowLeft className="h-4 w-4 mr-2" />
                                    Home
                                </Button>
                                <Button onClick={handleRefresh} variant="outline" size="sm" className="hover:bg-white/50 transition-colors">
                                    <RefreshCw className="h-4 w-4 mr-2" />
                                    Refresh
                                </Button>
                                <GitHubConnectButton />
                                <Button onClick={() => setShowCreateDialog(true)} className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 shadow-lg hover:shadow-xl transition-all duration-200">
                                    <Plus className="h-4 w-4 mr-2" />
                                    New Project
                                </Button>
                            </div>
                        </div>
                    </div>

                    {/* Stats Cards */}
                    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
                        <Card className="relative overflow-hidden bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-950/20 dark:to-blue-900/20 border-blue-200 dark:border-blue-800 hover:shadow-lg transition-all duration-300">
                            <div className="absolute top-0 right-0 w-16 h-16 bg-blue-500/10 rounded-bl-3xl"></div>
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium flex items-center gap-2">
                                    <Database className="h-4 w-4 text-blue-600" />
                                    Total Projects
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="text-3xl font-bold text-blue-700 dark:text-blue-300">{projectsData?.total_count || 0}</div>
                            </CardContent>
                        </Card>
                        <Card className="relative overflow-hidden bg-gradient-to-br from-green-50 to-green-100 dark:from-green-950/20 dark:to-green-900/20 border-green-200 dark:border-green-800 hover:shadow-lg transition-all duration-300">
                            <div className="absolute top-0 right-0 w-16 h-16 bg-green-500/10 rounded-bl-3xl"></div>
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium flex items-center gap-2">
                                    <Activity className="h-4 w-4 text-green-600" />
                                    Active Projects
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="text-3xl font-bold text-green-700 dark:text-green-300">
                                    {filteredAndSortedProjects.filter(p => p.status === 'active').length}
                                </div>
                            </CardContent>
                        </Card>
                        <Card className="relative overflow-hidden bg-gradient-to-br from-purple-50 to-purple-100 dark:from-purple-950/20 dark:to-purple-900/20 border-purple-200 dark:border-purple-800 hover:shadow-lg transition-all duration-300">
                            <div className="absolute top-0 right-0 w-16 h-16 bg-purple-500/10 rounded-bl-3xl"></div>
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium flex items-center gap-2">
                                    <Link className="h-4 w-4 text-purple-600" />
                                    GitHub Linked
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="text-3xl font-bold text-purple-700 dark:text-purple-300">
                                    {filteredAndSortedProjects.filter(p => p.github_linked).length}
                                </div>
                            </CardContent>
                        </Card>
                        <Card className="relative overflow-hidden bg-gradient-to-br from-orange-50 to-orange-100 dark:from-orange-950/20 dark:to-orange-900/20 border-orange-200 dark:border-orange-800 hover:shadow-lg transition-all duration-300">
                            <div className="absolute top-0 right-0 w-16 h-16 bg-orange-500/10 rounded-bl-3xl"></div>
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium flex items-center gap-2">
                                    <FileText className="h-4 w-4 text-orange-600" />
                                    Total Files
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="text-3xl font-bold text-orange-700 dark:text-orange-300">
                                    {filteredAndSortedProjects.reduce((sum, p) => sum + (p.file_count || 0), 0)}
                                </div>
                            </CardContent>
                        </Card>
                    </div>

                    {/* Filters and Controls */}
                    <Card className="shadow-sm border-0 bg-white/50 dark:bg-gray-900/50 backdrop-blur-sm">
                        <CardContent className="pt-6">
                            <div className="flex flex-col lg:flex-row gap-6 items-start lg:items-center justify-between">
                                <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center flex-1">
                                    {/* Search */}
                                    <div className="relative flex-1 max-w-md">
                                        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search projects..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-10 h-11 border-2 focus:border-blue-500 transition-colors"
                                        />
                                    </div>

                                    {/* Filter */}
                                    <Select value={filterBy} onValueChange={(value: FilterBy) => setFilterBy(value)}>
                                        <SelectTrigger className="w-52 h-11 border-2 hover:border-blue-500 transition-colors">
                                            <Filter className="h-4 w-4 mr-2 text-blue-600" />
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="all">All Projects</SelectItem>
                                            <SelectItem value="active">Active</SelectItem>
                                            <SelectItem value="inactive">Inactive</SelectItem>
                                            <SelectItem value="github_linked">GitHub Linked</SelectItem>
                                            <SelectItem value="github_unlinked">Not Linked</SelectItem>
                                        </SelectContent>
                                    </Select>

                                    {/* Sort */}
                                    <Select value={sortBy} onValueChange={(value: SortBy) => setSortBy(value)}>
                                        <SelectTrigger className="w-52 h-11 border-2 hover:border-blue-500 transition-colors">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="updated_at">Last Updated</SelectItem>
                                            <SelectItem value="created_at">Date Created</SelectItem>
                                            <SelectItem value="name">Name</SelectItem>
                                            <SelectItem value="status">Status</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>

                                {/* View Mode */}
                                <div className="flex items-center gap-1 bg-gray-100 dark:bg-gray-800 rounded-lg p-1 border">
                                    <Button
                                        variant={viewMode === 'grid' ? 'default' : 'ghost'}
                                        size="sm"
                                        onClick={() => setViewMode('grid')}
                                        className="h-9 px-3 hover:bg-blue-100 dark:hover:bg-blue-900 transition-colors"
                                    >
                                        <Grid3X3 className="h-4 w-4" />
                                    </Button>
                                    <Button
                                        variant={viewMode === 'list' ? 'default' : 'ghost'}
                                        size="sm"
                                        onClick={() => setViewMode('list')}
                                        className="h-9 px-3 hover:bg-blue-100 dark:hover:bg-blue-900 transition-colors"
                                    >
                                        <List className="h-4 w-4" />
                                    </Button>
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Projects Display */}
                    {filteredAndSortedProjects.length === 0 ? (
                        <Card className="border-2 border-dashed border-gray-300 dark:border-gray-700 bg-gradient-to-br from-gray-50 to-gray-100/50 dark:from-gray-900 dark:to-gray-800/50">
                            <CardContent className="pt-12 pb-12">
                                <div className="text-center space-y-6">
                                    <div className="mx-auto w-16 h-16 bg-gray-200 dark:bg-gray-700 rounded-full flex items-center justify-center">
                                        <FolderOpen className="h-8 w-8 text-gray-500 dark:text-gray-400" />
                                    </div>
                                    <div className="space-y-2">
                                        <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                                            {searchQuery || filterBy !== 'all'
                                                ? 'No matching projects'
                                                : 'No projects yet'
                                            }
                                        </h3>
                                        <p className="text-muted-foreground max-w-md mx-auto">
                                            {searchQuery || filterBy !== 'all'
                                                ? 'Try adjusting your search or filter criteria to find what you\'re looking for.'
                                                : 'Get started by creating your first infrastructure project. It\'s quick and easy!'
                                            }
                                        </p>
                                    </div>
                                    {(!searchQuery && filterBy === 'all') && (
                                        <Button onClick={() => setShowCreateDialog(true)} size="lg" className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 shadow-lg hover:shadow-xl transition-all duration-200">
                                            <Plus className="h-5 w-5 mr-2" />
                                            Create Your First Project
                                        </Button>
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    ) : (
                        <div className="animate-in fade-in-50 duration-300">
                            <ProjectsDisplay
                                projects={filteredAndSortedProjects}
                                viewMode={viewMode}
                                onSelectProject={handleSelectProject}
                                onDeleteProject={handleDeleteProject}
                                githubToken={githubToken}
                            />
                        </div>
                    )}
                </div>

                {/* Create Project Dialog */}
                <CreateProjectDialog
                    open={showCreateDialog}
                    onOpenChange={setShowCreateDialog}
                    githubToken={githubToken}
                />
            </div>
        </div>
    );
};

// Projects Display Component
interface ProjectsDisplayProps {
    projects: Project[];
    viewMode: ViewMode;
    onSelectProject: (project: Project) => void;
    onDeleteProject: (projectId: string, projectName: string) => void;
    githubToken?: string;
}

const ProjectsDisplay: React.FC<ProjectsDisplayProps> = ({
    projects,
    viewMode,
    onSelectProject,
    onDeleteProject,
    githubToken,
}) => {
    if (viewMode === 'grid') {
        return (
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                {projects.map((project) => (
                    <ProjectCard
                        key={project.id}
                        project={project}
                        onSelect={onSelectProject}
                        onDelete={onDeleteProject}
                        githubToken={githubToken}
                    />
                ))}
            </div>
        );
    }

    return (
        <Card>
            <CardContent className="p-0">
                <div className="divide-y">
                    {projects.map((project) => (
                        <ProjectListItem
                            key={project.id}
                            project={project}
                            onSelect={onSelectProject}
                            onDelete={onDeleteProject}
                            githubToken={githubToken}
                        />
                    ))}
                </div>
            </CardContent>
        </Card>
    );
};

// Project Card Component
interface ProjectItemProps {
    project: Project;
    onSelect: (project: Project) => void;
    onDelete: (projectId: string, projectName: string) => void;
    githubToken?: string;
}

const ProjectCard: React.FC<ProjectItemProps> = ({
    project,
    onSelect,
    onDelete,
    githubToken
}) => {
    const syncMutation = usePushProjectToGitHub(project.id);

    const handleSync = async (e: React.MouseEvent) => {
        e.stopPropagation();
        syncMutation.mutate({ commit_message: 'Manual sync from InfraJet' });
    };

    const formatFileSize = (bytes: number) => {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };

    return (
        <Card className="hover:shadow-xl hover:shadow-blue-500/10 transition-all duration-300 cursor-pointer group border-2 hover:border-blue-200 dark:hover:border-blue-800 bg-gradient-to-br from-white to-gray-50/50 dark:from-gray-900 dark:to-gray-800/50">
            <CardHeader className="pb-3 relative">
                <div className="absolute top-0 right-0 w-20 h-20 bg-gradient-to-bl from-blue-500/5 to-transparent rounded-bl-3xl"></div>
                <div className="flex items-start justify-between">
                    <div className="flex-1" onClick={() => onSelect(project)}>
                        <CardTitle className="text-lg font-semibold group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors line-clamp-1">
                            {project.name}
                        </CardTitle>
                        <CardDescription className="mt-1 line-clamp-2 text-gray-600 dark:text-gray-400">
                            {project.description}
                        </CardDescription>
                    </div>
                    <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="sm" className="opacity-0 group-hover:opacity-100 transition-all duration-200 hover:bg-blue-50 dark:hover:bg-blue-900/50">
                                <MoreHorizontal className="h-4 w-4" />
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="shadow-lg border-0 bg-white/95 dark:bg-gray-900/95 backdrop-blur-sm">
                            <DropdownMenuItem onClick={() => onSelect(project)} className="hover:bg-blue-50 dark:hover:bg-blue-900/50">
                                <Eye className="h-4 w-4 mr-2" />
                                View Project
                            </DropdownMenuItem>
                            {project.github_linked && (
                                <DropdownMenuItem onClick={handleSync} disabled={syncMutation.isPending} className="hover:bg-green-50 dark:hover:bg-green-900/50">
                                    <RefreshCw className={`h-4 w-4 mr-2 ${syncMutation.isPending ? 'animate-spin' : ''}`} />
                                    Sync with GitHub
                                </DropdownMenuItem>
                            )}
                            {project.github_repo_name && (
                                <DropdownMenuItem asChild>
                                    <a
                                        href={`https://github.com/${project.github_repo_name}`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="hover:bg-purple-50 dark:hover:bg-purple-900/50"
                                    >
                                        <ExternalLink className="h-4 w-4 mr-2" />
                                        Open in GitHub
                                    </a>
                                </DropdownMenuItem>
                            )}
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                                onClick={() => onDelete(project.id, project.name)}
                                className="text-red-600 hover:bg-red-50 dark:hover:bg-red-900/50"
                            >
                                <Trash2 className="h-4 w-4 mr-2" />
                                Delete Project
                            </DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>
                </div>
            </CardHeader>
            <CardContent onClick={() => onSelect(project)} className="pt-0">
                <div className="space-y-4">
                    {/* Status and GitHub */}
                    <div className="flex items-center justify-between">
                        <Badge variant={project.status === 'active' ? 'default' : 'secondary'} className="font-medium">
                            {project.status}
                        </Badge>
                        {project.github_linked && (
                            <div className="flex items-center text-sm text-muted-foreground bg-green-50 dark:bg-green-900/20 px-2 py-1 rounded-full">
                                <Github className="h-4 w-4 mr-1 text-green-600" />
                                <span className="truncate max-w-32 font-medium">
                                    {project.github_repo_name?.split('/')[1] || 'Linked'}
                                </span>
                            </div>
                        )}
                    </div>

                    {/* File info */}
                    {(project.file_count !== undefined || project.total_size !== undefined) && (
                        <div className="flex items-center justify-between text-sm text-muted-foreground bg-gray-50 dark:bg-gray-800/50 px-3 py-2 rounded-lg">
                            {project.file_count !== undefined && (
                                <div className="flex items-center">
                                    <FileText className="h-4 w-4 mr-1 text-blue-500" />
                                    <span className="font-medium">{project.file_count} files</span>
                                </div>
                            )}
                            {project.total_size !== undefined && (
                                <div className="flex items-center">
                                    <span className="font-medium">{formatFileSize(project.total_size)}</span>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Timestamps */}
                    <div className="text-xs text-muted-foreground flex items-center justify-between">
                        <div className="flex items-center">
                            <Calendar className="h-3 w-3 mr-1" />
                            Updated {formatDistanceToNow(new Date(project.updated_at), { addSuffix: true })}
                        </div>
                        <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};

// Project List Item Component
const ProjectListItem: React.FC<ProjectItemProps> = ({
    project,
    onSelect,
    onDelete,
    githubToken
}) => {
    const syncMutation = usePushProjectToGitHub(project.id);

    const handleSync = async (e: React.MouseEvent) => {
        e.stopPropagation();
        syncMutation.mutate({ commit_message: 'Manual sync from InfraJet' });
    };

    const formatFileSize = (bytes: number) => {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };

    return (
        <div
            className="p-6 hover:bg-gradient-to-r hover:from-blue-50/50 hover:to-indigo-50/50 dark:hover:from-blue-950/20 dark:hover:to-indigo-950/20 cursor-pointer transition-all duration-300 group border-b border-gray-100 dark:border-gray-800 last:border-b-0"
            onClick={() => onSelect(project)}
        >
            <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-4">
                        <div className="flex-1 min-w-0">
                            <h3 className="font-semibold text-lg group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors truncate">
                                {project.name}
                            </h3>
                            <p className="text-sm text-muted-foreground truncate mt-1">
                                {project.description}
                            </p>
                        </div>
                        <div className="hidden md:flex items-center gap-6 text-sm text-muted-foreground">
                            <Badge variant={project.status === 'active' ? 'default' : 'secondary'} className="font-medium">
                                {project.status}
                            </Badge>
                            {project.github_linked && (
                                <div className="flex items-center bg-green-50 dark:bg-green-900/20 px-3 py-1 rounded-full">
                                    <Github className="h-4 w-4 mr-1 text-green-600" />
                                    <span className="truncate max-w-32 font-medium">
                                        {project.github_repo_name?.split('/')[1] || 'Linked'}
                                    </span>
                                </div>
                            )}
                            {project.file_count !== undefined && (
                                <div className="flex items-center bg-blue-50 dark:bg-blue-900/20 px-3 py-1 rounded-full">
                                    <FileText className="h-4 w-4 mr-1 text-blue-500" />
                                    <span className="font-medium">{project.file_count}</span>
                                </div>
                            )}
                            {project.total_size !== undefined && (
                                <div className="bg-orange-50 dark:bg-orange-900/20 px-3 py-1 rounded-full">
                                    <span className="font-medium">{formatFileSize(project.total_size)}</span>
                                </div>
                            )}
                            <span className="text-gray-500 dark:text-gray-400">
                                {formatDistanceToNow(new Date(project.updated_at), { addSuffix: true })}
                            </span>
                        </div>
                        <div className="md:hidden flex items-center gap-2">
                            <Badge variant={project.status === 'active' ? 'default' : 'secondary'} className="text-xs">
                                {project.status}
                            </Badge>
                            {project.github_linked && <Github className="h-4 w-4 text-green-600" />}
                        </div>
                    </div>
                </div>
                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="sm" className="opacity-0 group-hover:opacity-100 transition-all duration-200 hover:bg-blue-50 dark:hover:bg-blue-900/50 ml-4">
                            <MoreHorizontal className="h-4 w-4" />
                        </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="shadow-lg border-0 bg-white/95 dark:bg-gray-900/95 backdrop-blur-sm">
                        <DropdownMenuItem onClick={() => onSelect(project)} className="hover:bg-blue-50 dark:hover:bg-blue-900/50">
                            <Eye className="h-4 w-4 mr-2" />
                            View Project
                        </DropdownMenuItem>
                        {project.github_linked && (
                            <DropdownMenuItem onClick={handleSync} disabled={syncMutation.isPending} className="hover:bg-green-50 dark:hover:bg-green-900/50">
                                <RefreshCw className={`h-4 w-4 mr-2 ${syncMutation.isPending ? 'animate-spin' : ''}`} />
                                Sync with GitHub
                            </DropdownMenuItem>
                        )}
                        {project.github_repo_name && (
                            <DropdownMenuItem asChild>
                                <a
                                    href={`https://github.com/${project.github_repo_name}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="hover:bg-purple-50 dark:hover:bg-purple-900/50"
                                >
                                    <ExternalLink className="h-4 w-4 mr-2" />
                                    Open in GitHub
                                </a>
                            </DropdownMenuItem>
                        )}
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                            onClick={() => onDelete(project.id, project.name)}
                            className="text-red-600 hover:bg-red-50 dark:hover:bg-red-900/50"
                        >
                            <Trash2 className="h-4 w-4 mr-2" />
                            Delete Project
                        </DropdownMenuItem>
                    </DropdownMenuContent>
                </DropdownMenu>
            </div>
        </div>
    );
};

export default ProjectManagement;