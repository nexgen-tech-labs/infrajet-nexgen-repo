import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  ArrowLeft,
  Settings,
  Code,
  MessageSquare,
  Github,
  Calendar,
  FileText,
  HardDrive,
  ExternalLink,
  History,
  Cloud,
  Database,
  Activity,
  ChevronRight
} from 'lucide-react';
import { useProject } from '@/hooks/useProjects';
import { useAuth } from '@/contexts/AuthContext';
import { SimpleChatInterface } from '@/components/chat/SimpleChatInterface';
import { TerraformChatInterface } from '@/components/chat/TerraformChatInterface';
import { UserChats } from '@/components/chat/UserChats';
import { CodeGenerator } from '@/components/code-generation/CodeGenerator';
import { GitHubIntegration } from '@/components/github/GitHubIntegration';
import ProjectFileManager from '@/components/projects/ProjectFileManager';
import ProjectSettings from '@/components/projects/ProjectSettings';
import { Project } from '@/services/infrajetApi';
import { formatDistanceToNow } from 'date-fns';

interface ProjectDashboardProps {
    projectId: string;
    onBack?: () => void;
    githubToken?: string;
}

const ProjectHeader: React.FC<{
    project: Project;
    onBack?: () => void;
}> = ({ project, onBack }) => {
    const formatFileSize = (bytes: number) => {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };

    return (
        <div className="space-y-4">
            {/* Navigation */}
            {onBack && (
                <Button variant="ghost" onClick={onBack} className="flex items-center gap-2">
                    <ArrowLeft className="h-4 w-4" />
                    Back to Projects
                </Button>
            )}

            {/* Project Info */}
            <Card>
                <CardHeader>
                    <div className="flex items-start justify-between">
                        <div className="space-y-2">
                            <div className="flex items-center gap-3">
                                <CardTitle className="text-2xl">{project.name}</CardTitle>
                                <Badge variant={project.status === 'active' ? 'default' : 'secondary'}>
                                    {project.status}
                                </Badge>
                                {project.github_linked && (
                                    <Badge variant="outline" className="flex items-center gap-1">
                                        <Github className="h-3 w-3" />
                                        GitHub
                                    </Badge>
                                )}
                            </div>
                            <CardDescription className="text-base">
                                {project.description}
                            </CardDescription>
                        </div>
                        <Button variant="outline" size="sm">
                            <Settings className="h-4 w-4 mr-2" />
                            Settings
                        </Button>
                    </div>
                </CardHeader>
                <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div className="flex items-center gap-2 text-sm">
                            <Calendar className="h-4 w-4 text-muted-foreground" />
                            <div>
                                <p className="font-medium">Created</p>
                                <p className="text-muted-foreground">
                                    {(() => {
                                        try {
                                            if (project.created_at && typeof project.created_at === 'string') {
                                                return formatDistanceToNow(new Date(project.created_at), { addSuffix: true });
                                            }
                                            return 'Unknown';
                                        } catch (error) {
                                            return 'Invalid date';
                                        }
                                    })()}
                                </p>
                            </div>
                        </div>

                        {project.file_count !== undefined && (
                            <div className="flex items-center gap-2 text-sm">
                                <FileText className="h-4 w-4 text-muted-foreground" />
                                <div>
                                    <p className="font-medium">Files</p>
                                    <p className="text-muted-foreground">{project.file_count}</p>
                                </div>
                            </div>
                        )}

                        {project.total_size !== undefined && (
                            <div className="flex items-center gap-2 text-sm">
                                <HardDrive className="h-4 w-4 text-muted-foreground" />
                                <div>
                                    <p className="font-medium">Size</p>
                                    <p className="text-muted-foreground">{formatFileSize(project.total_size)}</p>
                                </div>
                            </div>
                        )}

                        {project.github_repo_name && (
                            <div className="flex items-center gap-2 text-sm">
                                <Github className="h-4 w-4 text-muted-foreground" />
                                <div>
                                    <p className="font-medium">Repository</p>
                                    <a
                                        href={`https://github.com/${project.github_repo_name}`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-blue-600 hover:underline flex items-center gap-1"
                                    >
                                        {project.github_repo_name.split('/')[1]}
                                        <ExternalLink className="h-3 w-3" />
                                    </a>
                                </div>
                            </div>
                        )}
                    </div>

                    {project.last_github_sync && (
                        <div className="mt-4 pt-4 border-t">
                            <p className="text-sm text-muted-foreground">
                                Last GitHub sync: {(() => {
                                    try {
                                        if (project.last_github_sync && typeof project.last_github_sync === 'string') {
                                            return formatDistanceToNow(new Date(project.last_github_sync), { addSuffix: true });
                                        }
                                        return 'Unknown';
                                    } catch (error) {
                                        return 'Invalid date';
                                    }
                                })()}
                            </p>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
};

const ProjectDashboardSkeleton: React.FC = () => (
    <div className="space-y-6">
        <div className="space-y-4">
            <Skeleton className="h-10 w-32" />
            <Card>
                <CardHeader>
                    <div className="flex items-start justify-between">
                        <div className="space-y-2">
                            <Skeleton className="h-8 w-64" />
                            <Skeleton className="h-4 w-96" />
                        </div>
                        <Skeleton className="h-9 w-24" />
                    </div>
                </CardHeader>
                <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        {Array.from({ length: 4 }).map((_, i) => (
                            <div key={i} className="space-y-2">
                                <Skeleton className="h-4 w-16" />
                                <Skeleton className="h-4 w-20" />
                            </div>
                        ))}
                    </div>
                </CardContent>
            </Card>
        </div>
        <Skeleton className="h-96 w-full" />
    </div>
);

export const ProjectDashboard: React.FC<ProjectDashboardProps> = ({
  projectId,
  onBack,
  githubToken,
}) => {
  const [activeSection, setActiveSection] = useState('terraform-chat');
  const { user } = useAuth();
  const { data: project, isLoading, error } = useProject(projectId);

  const navigationItems = [
    { id: 'overview', label: 'Overview', icon: Activity, color: 'text-blue-600' },
    { id: 'terraform-chat', label: 'Terraform Chat', icon: MessageSquare, color: 'text-blue-600' },
    { id: 'chat-history', label: 'Chat History', icon: History, color: 'text-purple-600' },
    // { id: 'code-generation', label: 'Code Generation', icon: Code, color: 'text-green-600' },
    { id: 'files', label: 'Files', icon: FileText, color: 'text-orange-600' },
    { id: 'github', label: 'GitHub', icon: Github, color: 'text-gray-600' },
    { id: 'settings', label: 'Settings', icon: Settings, color: 'text-red-600' },
  ];

    if (isLoading) {
        return <ProjectDashboardSkeleton />;
    }

    if (error || !project) {
        return (
            <Card>
                <CardContent className="pt-6">
                    <div className="text-center text-red-600">
                        {error ? `Failed to load project: ${error.message}` : 'Project not found'}
                    </div>
                    {onBack && (
                        <div className="mt-4">
                            <Button variant="outline" onClick={onBack}>
                                Back to Projects
                            </Button>
                        </div>
                    )}
                </CardContent>
            </Card>
        );
    }

    const renderContent = () => {
        switch (activeSection) {
            case 'overview':
                return (
                    <div className="space-y-6">
                        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                            <Card className="hover:shadow-lg transition-shadow">
                                <CardHeader className="pb-3">
                                    <CardTitle className="flex items-center gap-2 text-lg">
                                        <MessageSquare className="h-5 w-5 text-blue-600" />
                                        Terraform Chat
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <p className="text-sm text-muted-foreground mb-4">
                                        Chat with AI to generate Terraform infrastructure code
                                    </p>
                                    <Button
                                        onClick={() => setActiveSection('terraform-chat')}
                                        className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700"
                                    >
                                        Start Chatting
                                    </Button>
                                </CardContent>
                            </Card>

                            <Card className="hover:shadow-lg transition-shadow">
                                <CardHeader className="pb-3">
                                    <CardTitle className="flex items-center gap-2 text-lg">
                                        <FileText className="h-5 w-5 text-orange-600" />
                                        Project Files
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <p className="text-sm text-muted-foreground mb-4">
                                        Manage your project files and generated code
                                    </p>
                                    <Button
                                        onClick={() => setActiveSection('files')}
                                        variant="outline"
                                        className="w-full"
                                    >
                                        View Files
                                    </Button>
                                </CardContent>
                            </Card>

                            <Card className="hover:shadow-lg transition-shadow">
                                <CardHeader className="pb-3">
                                    <CardTitle className="flex items-center gap-2 text-lg">
                                        <Github className="h-5 w-5 text-gray-600" />
                                        GitHub Integration
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <p className="text-sm text-muted-foreground mb-4">
                                        Connect and sync with your GitHub repository
                                    </p>
                                    <Button
                                        onClick={() => setActiveSection('github')}
                                        variant="outline"
                                        className="w-full"
                                    >
                                        Manage GitHub
                                    </Button>
                                </CardContent>
                            </Card>
                        </div>

                        <div className="grid gap-6 md:grid-cols-2">
                            <Card className="hover:shadow-lg transition-shadow">
                                <CardHeader className="pb-3">
                                    <CardTitle className="flex items-center gap-2 text-lg">
                                        <History className="h-5 w-5 text-purple-600" />
                                        Recent Activity
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="space-y-3">
                                        <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg">
                                            <MessageSquare className="h-4 w-4 text-blue-600" />
                                            <div className="flex-1">
                                                <p className="text-sm font-medium">Terraform chat started</p>
                                                <p className="text-xs text-muted-foreground">2 hours ago</p>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg">
                                            <FileText className="h-4 w-4 text-green-600" />
                                            <div className="flex-1">
                                                <p className="text-sm font-medium">Code generated</p>
                                                <p className="text-xs text-muted-foreground">5 hours ago</p>
                                            </div>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>

                            <Card className="hover:shadow-lg transition-shadow">
                                <CardHeader className="pb-3">
                                    <CardTitle className="flex items-center gap-2 text-lg">
                                        <Settings className="h-5 w-5 text-red-600" />
                                        Quick Settings
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="space-y-3">
                                        <Button
                                            onClick={() => setActiveSection('settings')}
                                            variant="outline"
                                            className="w-full justify-start"
                                        >
                                            <Settings className="h-4 w-4 mr-2" />
                                            Project Settings
                                        </Button>
                                        <Button
                                            onClick={() => setActiveSection('terraform-chat')}
                                            variant="outline"
                                            className="w-full justify-start"
                                        >
                                            <Code className="h-4 w-4 mr-2" />
                                            Code Generation
                                        </Button>
                                    </div>
                                </CardContent>
                            </Card>
                        </div>
                    </div>
                );
            case 'terraform-chat':
                return <TerraformChatInterface projectId={projectId} />;
            case 'chat-history':
                return <UserChats projectId={projectId} userId={user?.id || 'user-id'} />;
            case 'code-generation':
                return <CodeGenerator projectId={projectId} />;
            case 'files':
                return <ProjectFileManager projectId={projectId} />;
            case 'github':
                return (
                    <GitHubIntegration
                        projectId={projectId}
                        githubToken={githubToken}
                    />
                );
            case 'settings':
                return (
                    <ProjectSettings
                        projectId={projectId}
                        onProjectDeleted={onBack}
                    />
                );
            default:
                return <div>Select a section from the sidebar</div>;
        }
    };

    return (
        <div className="min-h-screen bg-background">
            <div className="flex">
                {/* Sidebar */}
                <div className="w-64 bg-card border-r border-border">
                    <div className="p-6 border-b border-border">
                        <Button
                            variant="ghost"
                            onClick={onBack}
                            className="flex items-center gap-2 w-full justify-start"
                        >
                            <ArrowLeft className="h-4 w-4" />
                            Back to Projects
                        </Button>
                    </div>

                    <ScrollArea className="flex-1">
                        <div className="p-4">
                            <nav className="space-y-2">
                                {navigationItems.map((item) => {
                                    const Icon = item.icon;
                                    const isActive = activeSection === item.id;

                                    return (
                                        <Button
                                            key={item.id}
                                            variant={isActive ? "secondary" : "ghost"}
                                            onClick={() => setActiveSection(item.id)}
                                            className={`w-full justify-start gap-3 h-12 ${
                                                isActive
                                                    ? 'bg-primary/10 text-primary border-l-2 border-primary'
                                                    : 'hover:bg-muted'
                                            }`}
                                        >
                                            <Icon className={`h-5 w-5 ${item.color}`} />
                                            <span className="font-medium">{item.label}</span>
                                            {isActive && <ChevronRight className="h-4 w-4 ml-auto" />}
                                        </Button>
                                    );
                                })}
                            </nav>
                        </div>
                    </ScrollArea>
                </div>

                {/* Main Content */}
                <div className="flex-1">
                    <div className="p-8">
                        {/* Project Header - Only show in overview */}
                        {activeSection === 'overview' && (
                            <>
                                <ProjectHeader project={project} onBack={onBack} />
                                <div className="mt-8">
                                    {renderContent()}
                                </div>
                            </>
                        )}
                        {/* Other sections without project header */}
                        {activeSection !== 'overview' && (
                            <div>
                                {renderContent()}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};