import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';
import {
    Form,
    FormControl,
    FormDescription,
    FormField,
    FormItem,
    FormLabel,
    FormMessage,
} from '@/components/ui/form';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
    AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import {
    Settings,
    Save,
    Trash2,
    AlertTriangle,
    Github,
    Unlink,
    RefreshCw,
    Key,
    Shield,
    Database,
    ExternalLink
} from 'lucide-react';
import { useProject, useUpdateProject, useDeleteProject } from '@/hooks/useProjects';
import { useLinkProjectToGitHub, usePushProjectToGitHub, useProjectGitHubStatus } from '@/hooks/useGitHubIntegration';
import { Project } from '@/services/infrajetApi';
import { useToast } from '@/hooks/use-toast';

const projectSettingsSchema = z.object({
    name: z.string().min(1, 'Project name is required').max(100, 'Name too long'),
    description: z.string().min(1, 'Description is required').max(500, 'Description too long'),
    status: z.enum(['active', 'inactive', 'archived']),
    auto_sync_github: z.boolean().default(false),
    enable_notifications: z.boolean().default(true),
    default_provider: z.string().default('aws'),
});

type ProjectSettingsFormData = z.infer<typeof projectSettingsSchema>;

interface ProjectSettingsProps {
    projectId: string;
    onProjectUpdated?: (project: Project) => void;
    onProjectDeleted?: () => void;
    className?: string;
}

const ProjectSettings: React.FC<ProjectSettingsProps> = ({
    projectId,
    onProjectUpdated,
    onProjectDeleted,
    className,
}) => {
    const [isDeleting, setIsDeleting] = useState(false);
    const { toast } = useToast();

    const { data: project, isLoading, error } = useProject(projectId);
    const updateProjectMutation = useUpdateProject();
    const deleteProjectMutation = useDeleteProject();
    const syncMutation = usePushProjectToGitHub(projectId);
    const { data: githubStatus, isLoading: githubLoading } = useProjectGitHubStatus(projectId);

    const form = useForm<ProjectSettingsFormData>({
        resolver: zodResolver(projectSettingsSchema),
        defaultValues: {
            name: project?.name || '',
            description: project?.description || '',
            status: (project?.status as any) || 'active',
            auto_sync_github: false, // This would come from project settings
            enable_notifications: true, // This would come from project settings
            default_provider: 'aws', // This would come from project settings
        },
    });

    // Update form when project data loads
    React.useEffect(() => {
        if (project) {
            form.reset({
                name: project.name,
                description: project.description,
                status: project.status as any,
                auto_sync_github: false, // TODO: Get from project settings
                enable_notifications: true, // TODO: Get from project settings
                default_provider: 'aws', // TODO: Get from project settings
            });
        }
    }, [project, form]);

    const onSubmit = async (data: ProjectSettingsFormData) => {
        try {
            const result = await updateProjectMutation.mutateAsync({
                project_id: projectId,
                name: data.name,
                description: data.description,
                // TODO: Add other settings to the API
            });

            onProjectUpdated?.(result.project);

            toast({
                title: "Settings updated",
                description: "Project settings have been saved successfully.",
            });
        } catch (error) {
            // Error handled by mutation
        }
    };

    const handleDeleteProject = async () => {
        setIsDeleting(true);
        try {
            await deleteProjectMutation.mutateAsync({
                projectId,
                options: { soft_delete: false }
            });

            onProjectDeleted?.();

            toast({
                title: "Project deleted",
                description: "The project has been permanently deleted.",
            });
        } catch (error) {
            // Error handled by mutation
        } finally {
            setIsDeleting(false);
        }
    };

    const handleSyncGitHub = async () => {
        syncMutation.mutate({ commit_message: 'Manual sync from InfraJet' });
    };

    if (isLoading) {
        return (
            <Card className={className}>
                <CardHeader>
                    <div className="animate-pulse space-y-2">
                        <div className="h-6 w-48 bg-muted rounded" />
                        <div className="h-4 w-64 bg-muted rounded" />
                    </div>
                </CardHeader>
                <CardContent>
                    <div className="animate-pulse space-y-4">
                        {Array.from({ length: 6 }).map((_, i) => (
                            <div key={i} className="space-y-2">
                                <div className="h-4 w-24 bg-muted rounded" />
                                <div className="h-10 w-full bg-muted rounded" />
                            </div>
                        ))}
                    </div>
                </CardContent>
            </Card>
        );
    }

    if (error || !project) {
        return (
            <Card className={className}>
                <CardContent className="pt-6">
                    <div className="text-center text-red-600">
                        {error ? `Failed to load project: ${error.message}` : 'Project not found'}
                    </div>
                </CardContent>
            </Card>
        );
    }

    return (
        <div className={`space-y-8 ${className}`}>
            {/* General Settings */}
            <Card className="shadow-lg border-2">
                <CardHeader className="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20">
                    <CardTitle className="flex items-center gap-2">
                        <Settings className="h-5 w-5 text-blue-600" />
                        General Settings
                    </CardTitle>
                    <CardDescription>
                        Update your project information and preferences
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <Form {...form}>
                        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
                            <div className="grid gap-4 md:grid-cols-2">
                                <FormField
                                    control={form.control}
                                    name="name"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>Project Name</FormLabel>
                                            <FormControl>
                                                <Input placeholder="My Terraform Project" {...field} />
                                            </FormControl>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />

                                <FormField
                                    control={form.control}
                                    name="status"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>Status</FormLabel>
                                            <Select onValueChange={field.onChange} defaultValue={field.value}>
                                                <FormControl>
                                                    <SelectTrigger>
                                                        <SelectValue />
                                                    </SelectTrigger>
                                                </FormControl>
                                                <SelectContent>
                                                    <SelectItem value="active">Active</SelectItem>
                                                    <SelectItem value="inactive">Inactive</SelectItem>
                                                    <SelectItem value="archived">Archived</SelectItem>
                                                </SelectContent>
                                            </Select>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />
                            </div>

                            <FormField
                                control={form.control}
                                name="description"
                                render={({ field }) => (
                                    <FormItem>
                                        <FormLabel>Description</FormLabel>
                                        <FormControl>
                                            <Textarea
                                                placeholder="Describe your infrastructure project..."
                                                className="resize-none"
                                                {...field}
                                            />
                                        </FormControl>
                                        <FormMessage />
                                    </FormItem>
                                )}
                            />

                            <FormField
                                control={form.control}
                                name="default_provider"
                                render={({ field }) => (
                                    <FormItem>
                                        <FormLabel>Default Provider</FormLabel>
                                        <Select onValueChange={field.onChange} defaultValue={field.value}>
                                            <FormControl>
                                                <SelectTrigger>
                                                    <SelectValue />
                                                </SelectTrigger>
                                            </FormControl>
                                            <SelectContent>
                                                <SelectItem value="aws">AWS</SelectItem>
                                                <SelectItem value="azure">Azure</SelectItem>
                                                <SelectItem value="gcp">Google Cloud</SelectItem>
                                                <SelectItem value="kubernetes">Kubernetes</SelectItem>
                                            </SelectContent>
                                        </Select>
                                        <FormDescription>
                                            Default cloud provider for code generation
                                        </FormDescription>
                                        <FormMessage />
                                    </FormItem>
                                )}
                            />

                            <Separator />

                            {/* Preferences */}
                            <div className="space-y-4">
                                <h4 className="font-semibold">Preferences</h4>

                                <FormField
                                    control={form.control}
                                    name="auto_sync_github"
                                    render={({ field }) => (
                                        <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                                            <div className="space-y-0.5">
                                                <FormLabel className="text-base">
                                                    Auto-sync with GitHub
                                                </FormLabel>
                                                <FormDescription>
                                                    Automatically sync changes with your GitHub repository
                                                </FormDescription>
                                            </div>
                                            <FormControl>
                                                <Switch
                                                    checked={field.value}
                                                    onCheckedChange={field.onChange}
                                                />
                                            </FormControl>
                                        </FormItem>
                                    )}
                                />

                                <FormField
                                    control={form.control}
                                    name="enable_notifications"
                                    render={({ field }) => (
                                        <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                                            <div className="space-y-0.5">
                                                <FormLabel className="text-base">
                                                    Enable Notifications
                                                </FormLabel>
                                                <FormDescription>
                                                    Receive notifications about project activities
                                                </FormDescription>
                                            </div>
                                            <FormControl>
                                                <Switch
                                                    checked={field.value}
                                                    onCheckedChange={field.onChange}
                                                />
                                            </FormControl>
                                        </FormItem>
                                    )}
                                />
                            </div>

                            <div className="flex justify-end">
                                <Button
                                    type="submit"
                                    disabled={updateProjectMutation.isPending}
                                    className="flex items-center gap-2"
                                >
                                    {updateProjectMutation.isPending ? (
                                        <RefreshCw className="h-4 w-4 animate-spin" />
                                    ) : (
                                        <Save className="h-4 w-4" />
                                    )}
                                    Save Changes
                                </Button>
                            </div>
                        </form>
                    </Form>
                </CardContent>
            </Card>

            {/* GitHub Integration */}
            <Card className="shadow-lg border-2">
                <CardHeader className="bg-gradient-to-r from-gray-50 to-slate-50 dark:from-gray-950/20 dark:to-slate-950/20">
                    <CardTitle className="flex items-center gap-2">
                        <Github className="h-5 w-5 text-gray-600" />
                        GitHub Integration
                    </CardTitle>
                    <CardDescription>
                        Manage your GitHub repository connection
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    {githubLoading ? (
                        <div className="flex items-center justify-center p-8">
                            <RefreshCw className="h-6 w-6 animate-spin mr-2" />
                            <span>Loading GitHub status...</span>
                        </div>
                    ) : githubStatus?.data?.github_linked ? (
                        <>
                            <div className="flex items-center justify-between p-4 border rounded-lg">
                                <div>
                                    <p className="font-medium">Repository</p>
                                    <p className="text-sm text-muted-foreground">
                                        {githubStatus.data.github_repo_name || 'Connected'}
                                    </p>
                                    {githubStatus.data.last_github_sync && (
                                        <p className="text-xs text-muted-foreground mt-1">
                                            Last sync: {new Date(githubStatus.data.last_github_sync).toLocaleString()}
                                        </p>
                                    )}
                                </div>
                                <Badge variant="default" className="bg-green-100 text-green-800">
                                    Connected
                                </Badge>
                            </div>

                            <div className="flex gap-2">
                                <Button
                                    onClick={handleSyncGitHub}
                                    disabled={syncMutation.isPending}
                                    variant="outline"
                                    className="flex items-center gap-2"
                                >
                                    {syncMutation.isPending ? (
                                        <RefreshCw className="h-4 w-4 animate-spin" />
                                    ) : (
                                        <RefreshCw className="h-4 w-4" />
                                    )}
                                    Sync Now
                                </Button>

                                {githubStatus.data.github_repo_name && (
                                    <Button variant="outline" asChild>
                                        <a
                                            href={`https://github.com/${githubStatus.data.github_repo_name}`}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                        >
                                            <ExternalLink className="h-4 w-4 mr-2" />
                                            View Repository
                                        </a>
                                    </Button>
                                )}
                            </div>
                        </>
                    ) : (
                        <div className="text-center p-8 border-2 border-dashed border-muted-foreground/25 rounded-lg">
                            <Github className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
                            <h3 className="text-lg font-semibold mb-2">No GitHub Repository Linked</h3>
                            <p className="text-sm text-muted-foreground mb-4">
                                Link this project to a GitHub repository to enable automatic syncing and version control.
                            </p>
                            <Button variant="outline">
                                <Github className="h-4 w-4 mr-2" />
                                Link to GitHub Repository
                            </Button>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Project Information */}
            <Card className="shadow-lg border-2">
                <CardHeader className="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20">
                    <CardTitle className="flex items-center gap-2">
                        <Database className="h-5 w-5 text-blue-600" />
                        Project Information
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="grid gap-4 md:grid-cols-2">
                        <div>
                            <p className="text-sm font-medium">Project ID</p>
                            <p className="text-sm text-muted-foreground font-mono">{project.id}</p>
                        </div>
                        <div>
                            <p className="text-sm font-medium">Azure Folder Path</p>
                            <p className="text-sm text-muted-foreground font-mono">{project.azure_folder_path}</p>
                        </div>
                        <div>
                            <p className="text-sm font-medium">Created</p>
                            <p className="text-sm text-muted-foreground">
                                {new Date(project.created_at).toLocaleString()}
                            </p>
                        </div>
                        <div>
                            <p className="text-sm font-medium">Last Updated</p>
                            <p className="text-sm text-muted-foreground">
                                {new Date(project.updated_at).toLocaleString()}
                            </p>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Danger Zone */}
            <Card className="shadow-lg border-2 border-red-200 dark:border-red-800">
                <CardHeader className="bg-gradient-to-r from-red-50 to-rose-50 dark:from-red-950/20 dark:to-rose-950/20">
                    <CardTitle className="flex items-center gap-2 text-red-600">
                        <AlertTriangle className="h-5 w-5" />
                        Danger Zone
                    </CardTitle>
                    <CardDescription>
                        Irreversible and destructive actions
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="space-y-4">
                        <div className="flex items-center justify-between p-4 border border-red-200 dark:border-red-800 rounded-lg">
                            <div>
                                <p className="font-medium text-red-600">Delete Project</p>
                                <p className="text-sm text-muted-foreground">
                                    Permanently delete this project and all its data. This action cannot be undone.
                                </p>
                            </div>

                            <AlertDialog>
                                <AlertDialogTrigger asChild>
                                    <Button variant="destructive" className="flex items-center gap-2">
                                        <Trash2 className="h-4 w-4" />
                                        Delete Project
                                    </Button>
                                </AlertDialogTrigger>
                                <AlertDialogContent>
                                    <AlertDialogHeader>
                                        <AlertDialogTitle>Delete Project</AlertDialogTitle>
                                        <AlertDialogDescription>
                                            Are you sure you want to delete "{project.name}"? This will permanently
                                            delete the project, all its files, chat history, and cannot be undone.
                                        </AlertDialogDescription>
                                    </AlertDialogHeader>
                                    <AlertDialogFooter>
                                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                                        <AlertDialogAction
                                            onClick={handleDeleteProject}
                                            disabled={isDeleting}
                                            className="bg-red-600 hover:bg-red-700"
                                        >
                                            {isDeleting ? (
                                                <>
                                                    <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                                                    Deleting...
                                                </>
                                            ) : (
                                                <>
                                                    <Trash2 className="h-4 w-4 mr-2" />
                                                    Delete Project
                                                </>
                                            )}
                                        </AlertDialogAction>
                                    </AlertDialogFooter>
                                </AlertDialogContent>
                            </AlertDialog>
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
};

export default ProjectSettings;