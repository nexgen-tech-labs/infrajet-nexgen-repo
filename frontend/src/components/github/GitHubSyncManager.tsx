import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import {
    Github,
    RefreshCw,
    Upload,
    Loader2,
    ExternalLink,
    CheckCircle,
    XCircle,
    Plus,
    Link,
    Settings,
    GitBranch,
    Unlink
} from 'lucide-react';
import { githubApi, GitHubRepository, GitHubStatusResponse, getAuthToken } from '@/services/infrajetApi';
import { useToast } from '@/hooks/use-toast';
import { useGitHub } from '@/contexts/GitHubContext';
import { useProject } from '@/hooks/useProjects';
import { useGitHubIntegrationFlow, useProjectGitHubStatus } from '@/hooks/useGitHubIntegration';

interface GitHubSyncManagerProps {
    className?: string;
    projectId?: string;
    githubToken?: string;
}

const API_BASE_URL = window.__RUNTIME_CONFIG__?.INFRAJET_API_URL;

export const GitHubSyncManager: React.FC<GitHubSyncManagerProps> = ({
    className,
    projectId,
    githubToken,
}) => {
    const { data: project } = useProject(projectId || '');
    const { data: githubStatus, isLoading: githubLoading } = useProjectGitHubStatus(projectId || '');
    const {
        isConnected,
        repos: contextRepos,
        loading: contextLoading,
        refreshRepos: contextRefreshRepos
    } = useGitHub();
    const {
        linkToGitHub,
        pushToGitHub,
        createRepository,
        isLinking,
        isPushingProject,
        isCreatingRepo,
        linkError,
        installations
    } = useGitHubIntegrationFlow(projectId || '');
    const { toast } = useToast();
    const [status, setStatus] = useState<GitHubStatusResponse | null>(null);
    const [repositories, setRepositories] = useState<GitHubRepository[]>([]);
    const [loading, setLoading] = useState(false);
    const [loadingStatus, setLoadingStatus] = useState(true);
    const [loadingRepos, setLoadingRepos] = useState(false);
    const [showCreateRepoModal, setShowCreateRepoModal] = useState(false);
    const [showLinkRepoModal, setShowLinkRepoModal] = useState(false);
    const [newRepoName, setNewRepoName] = useState('');
    const [newRepoDescription, setNewRepoDescription] = useState('');
    const [newRepoPrivate, setNewRepoPrivate] = useState(false);
    const [pushCommitMessage, setPushCommitMessage] = useState('Push infrastructure code from InfraJet');
    const [branches, setBranches] = useState<{ name: string; sha: string; protected: boolean }[]>([]);
    const [selectedBranch, setSelectedBranch] = useState<string>('main');
    const [newBranchName, setNewBranchName] = useState<string>('');
    const [showCreateBranch, setShowCreateBranch] = useState(false);
    const [isLoadingBranches, setIsLoadingBranches] = useState(false);
    const [isCreatingBranch, setIsCreatingBranch] = useState(false);
    const [isUnlinking, setIsUnlinking] = useState(false);

    useEffect(() => {
        checkStatus();
    }, []);

    // Load repositories when status is checked and user is connected
    useEffect(() => {
        if (status?.data.connected && repositories.length === 0) {
            loadRepositories();
        }
    }, [status?.data.connected]);

    const checkStatus = async () => {
        setLoadingStatus(true);
        try {
            const response = await githubApi.getStatus();
            setStatus(response);
        } catch (error: any) {
            console.error('Failed to check GitHub status:', error);
            setStatus(null);
        } finally {
            setLoadingStatus(false);
        }
    };

    const getConnectUrl = async () => {
        try {
            const response = await githubApi.getConnectUrl();

            // Open in popup window
            const popup = window.open(
                response.data.authorization_url,
                'github-oauth',
                'width=600,height=700,scrollbars=yes,resizable=yes'
            );

            if (!popup) {
                toast({
                    title: 'Popup blocked',
                    description: 'Please allow popups for this site to connect GitHub',
                    variant: 'destructive',
                });
                return;
            }

            // Listen for messages from the popup
            const messageListener = async (event: MessageEvent) => {
                if (event.origin !== window.location.origin) return;

                if (event.data.type === 'github_oauth_callback') {
                    window.removeEventListener('message', messageListener);

                    if (event.data.error) {
                        toast({
                            title: 'GitHub Connection Failed',
                            description: event.data.error_description || event.data.error,
                            variant: 'destructive',
                        });
                        return;
                    }

                    if (event.data.code) {
                        try {
                            // Parent window (authenticated) calls /connect with the code
                            const connectResponse = await githubApi.connect({ code: event.data.code });
                            toast({
                                title: 'GitHub connected successfully',
                                description: connectResponse.message,
                            });

                            // Check if backend returned installation_id
                            if (connectResponse.data?.primary_installation_id) {
                                // Has installation, load repositories
                                await loadRepositories();
                                toast({
                                    title: 'Ready to sync',
                                    description: 'Your repositories are loaded and ready to sync.',
                                });
                            } else {
                                // No installation found, redirect to GitHub App installation
                                const appSlug = window.__RUNTIME_CONFIG__?.GITHUB_APP_SLUG;
                                const installUrl = `https://github.com/apps/${appSlug}/installations/new`;
                                window.open(installUrl, '_blank');

                                toast({
                                    title: 'GitHub App Installation Required',
                                    description: 'Please install the GitHub App, then return here and click "Load Repositories".',
                                });
                            }

                            await checkStatus();
                        } catch (error: any) {
                            toast({
                                title: 'Failed to connect GitHub',
                                description: error.message,
                                variant: 'destructive',
                            });
                        }
                    }
                }
            };

            window.addEventListener('message', messageListener);

            // Check if popup is closed without completing OAuth
            const checkClosed = setInterval(() => {
                if (popup.closed) {
                    clearInterval(checkClosed);
                    window.removeEventListener('message', messageListener);
                }
            }, 1000);

        } catch (error: any) {
            toast({
                title: 'Failed to get connection URL',
                description: error.message,
                variant: 'destructive',
            });
        }
    };

    const connectGitHub = async (code: string) => {
        try {
            const response = await githubApi.connect({ code });
            toast({
                title: 'GitHub connected successfully',
                description: response.message,
            });
            await checkStatus();
        } catch (error: any) {
            toast({
                title: 'Failed to connect GitHub',
                description: error.message,
                variant: 'destructive',
            });
        }
    };

    const loadRepositories = async () => {
        if (!status?.data.connected) {
            console.log('Not loading repositories - user not connected');
            return;
        }

        console.log('Loading repositories...');
        setLoadingRepos(true);
        try {
            const response = await githubApi.getRepositories();
            console.log('Repositories response:', response);
            setRepositories(response.data.repositories);
            console.log('Set repositories:', response.data.repositories.length, 'repos');
        } catch (error: any) {
            console.error('Error loading repositories:', error);
            toast({
                title: 'Failed to load repositories',
                description: error.message,
                variant: 'destructive',
            });
        } finally {
            setLoadingRepos(false);
        }
    };

    const disconnectGitHub = async () => {
        try {
            await githubApi.disconnect();
            toast({
                title: 'GitHub disconnected',
                description: 'GitHub account disconnected successfully.',
            });
            setStatus(null);
            setRepositories([]);
        } catch (error: any) {
            toast({
                title: 'Failed to disconnect GitHub',
                description: error.message,
                variant: 'destructive',
            });
        }
    };


    const handleCreateAndLinkRepo = async () => {
        if (!newRepoName.trim()) {
            toast({
                title: "Repository name required",
                description: "Please enter a repository name",
                variant: "destructive",
            });
            return;
        }

        try {
            // Create the repository
            await createRepository({
                installation_id: installations[0]?.id || 0, // Use first available installation
                name: newRepoName,
                description: newRepoDescription,
                private: newRepoPrivate,
            });

            // Link the repository to the project
            await linkToGitHub({
                installation_id: installations[0]?.id || 0,
                create_repo: false, // Repo already created
                repo_name: newRepoName,
            });

            setShowCreateRepoModal(false);
            setNewRepoName('');
            setNewRepoDescription('');
            setNewRepoPrivate(false);

        } catch (error) {
            console.error('Error creating and linking repository:', error);
            // Error handling is done by the hooks
        }
    };

    const handleLinkExistingRepo = async (repo: any) => {
        try {
            await linkToGitHub({
                installation_id: installations[0]?.id || 0,
                create_repo: false,
                repo_name: repo.name,
            });

            setShowLinkRepoModal(false);

        } catch (error) {
            console.error('Error linking repository:', error);
            // Error handling is done by the hooks
        }
    };

    const loadBranches = useCallback(async () => {
        if (!githubStatus?.data?.github_linked || !projectId) return;

        setIsLoadingBranches(true);
        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/github/projects/${projectId}/branches`, {
                headers: {
                    'Authorization': `Bearer ${await getAuthToken()}`,
                },
            });

            if (!response.ok) {
                throw new Error('Failed to load branches');
            }

            const data = await response.json();
            setBranches(data.data.branches || []);
            if (data.data.default_branch && !selectedBranch) {
                setSelectedBranch(data.data.default_branch);
            }
        } catch (error) {
            console.error('Failed to load branches:', error);
            toast({
                title: "Failed to load branches",
                description: "Could not load available branches",
                variant: "destructive",
            });
        } finally {
            setIsLoadingBranches(false);
        }
    }, [githubStatus?.data?.github_linked, projectId, selectedBranch, toast]);

    // Load branches when GitHub is linked
    useEffect(() => {
        if (githubStatus?.data?.github_linked) {
            loadBranches();
        }
    }, [githubStatus?.data?.github_linked, loadBranches]);

    const createBranch = async () => {
        if (!newBranchName.trim()) {
            toast({
                title: "Branch name required",
                description: "Please enter a branch name",
                variant: "destructive",
            });
            return;
        }

        setIsCreatingBranch(true);
        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/github/projects/${projectId}/branches`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${await getAuthToken()}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    new_branch_name: newBranchName.trim(),
                    source_branch: selectedBranch,
                }),
            });

            if (!response.ok) {
                throw new Error('Failed to create branch');
            }

            const data = await response.json();
            toast({
                title: "Branch created",
                description: `Branch "${newBranchName}" created successfully`,
            });

            setNewBranchName('');
            setShowCreateBranch(false);
            setSelectedBranch(newBranchName);
            // Reload branches
            await loadBranches();
        } catch (error) {
            console.error('Failed to create branch:', error);
            toast({
                title: "Failed to create branch",
                description: "Could not create the new branch",
                variant: "destructive",
            });
        } finally {
            setIsCreatingBranch(false);
        }
    };

    const unlinkProject = async () => {
        if (!projectId) return;

        setIsUnlinking(true);
        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/github/projects/${projectId}/unlink-repo`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${await getAuthToken()}`,
                },
            });

            if (!response.ok) {
                throw new Error('Failed to unlink project');
            }

            toast({
                title: "Project unlinked",
                description: "Project has been unlinked from GitHub repository",
            });

            // Refresh the GitHub status
            window.location.reload();
        } catch (error) {
            console.error('Failed to unlink project:', error);
            toast({
                title: "Failed to unlink",
                description: "Could not unlink the project from GitHub",
                variant: "destructive",
            });
        } finally {
            setIsUnlinking(false);
        }
    };

    const handlePushCode = async () => {
        if (!projectId || !githubStatus?.data?.github_linked) {
            toast({
                title: "Error",
                description: "Project not linked to GitHub",
                variant: "destructive",
            });
            return;
        }

        try {
            const repoParts = githubStatus.data.github_repo_name.split('/');
            const repoOwner = repoParts[0];
            const repoName = repoParts[1];

            // For project push, we need to get all project files
            // This is a simplified version - in a real implementation,
            // you'd fetch all project files and push them
            const data = await githubApi.pushProjectToGitHub(projectId, {
                commit_message: pushCommitMessage.trim() || 'Push infrastructure code from InfraJet'
            });

            toast({
                title: "Code Pushed Successfully",
                description: `Pushed ${data.data.files_synced} files to ${data.data.repository_url}`,
            });

            // Refresh the GitHub status to show updated sync time
            // The hook will automatically refetch

        } catch (error: any) {
            console.error('Error pushing code:', error);
            toast({
                title: "Failed to Push Code",
                description: error.message || "An unexpected error occurred while pushing code",
                variant: "destructive",
            });
        }
    };

    if (loadingStatus) {
        return (
            <Card className={className}>
                <CardHeader>
                    <Skeleton className="h-6 w-48" />
                    <Skeleton className="h-4 w-64" />
                </CardHeader>
                <CardContent>
                    <div className="space-y-4">
                        <Skeleton className="h-20 w-full" />
                        <Skeleton className="h-10 w-32" />
                    </div>
                </CardContent>
            </Card>
        );
    }

    return (
        <>
            <Card className={className}>
                <CardHeader>
                    <div className="flex items-center justify-between">
                        <div>
                            <CardTitle className="flex items-center gap-2">
                                <Github className="h-5 w-5" />
                                GitHub Integration
                            </CardTitle>
                            <CardDescription>
                                Link this project to a GitHub repository and push your code
                            </CardDescription>
                        </div>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={checkStatus}
                            disabled={loadingStatus}
                        >
                            {loadingStatus ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                                <RefreshCw className="h-4 w-4" />
                            )}
                        </Button>
                    </div>
                </CardHeader>
                <CardContent className="space-y-6">
                    {/* GitHub Connection Status */}
                    <div className="space-y-3">
                        <h4 className="font-semibold">GitHub Account</h4>
                        <div className="flex items-center justify-between p-4 border rounded-lg">
                            <div className="flex items-center gap-3">
                                {status?.data.connected ? (
                                    <>
                                        <CheckCircle className="h-8 w-8 text-green-600" />
                                        <div>
                                            <p className="font-medium">Connected</p>
                                            <p className="text-sm text-muted-foreground">
                                                {status.data.username}
                                            </p>
                                        </div>
                                    </>
                                ) : (
                                    <>
                                        <XCircle className="h-8 w-8 text-gray-400" />
                                        <div>
                                            <p className="font-medium">Not Connected</p>
                                            <p className="text-sm text-muted-foreground">
                                                Connect your GitHub account first
                                            </p>
                                        </div>
                                    </>
                                )}
                            </div>
                            <div className="flex gap-2">
                                {status?.data.connected ? (
                                    <Button variant="outline" onClick={disconnectGitHub}>
                                        Disconnect
                                    </Button>
                                ) : (
                                    <Button onClick={getConnectUrl}>
                                        Connect GitHub
                                    </Button>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Project Repository Status */}
                    {project && (
                        <div className="space-y-3">
                            <h4 className="font-semibold">Project Repository</h4>
                            <div className="p-4 border rounded-lg">
                                <div className="flex items-center justify-between mb-4">
                                    <div className="flex items-center gap-3">
                                        {githubLoading ? (
                                            <>
                                                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                                                <div>
                                                    <p className="font-medium">Checking repository status...</p>
                                                    <p className="text-sm text-muted-foreground">
                                                        Loading GitHub integration status
                                                    </p>
                                                </div>
                                            </>
                                        ) : githubStatus?.data?.github_linked ? (
                                            <>
                                                <CheckCircle className="h-6 w-6 text-green-600" />
                                                <div>
                                                    <p className="font-medium text-green-800">Linked to Repository</p>
                                                    <p className="text-sm text-green-700">
                                                        {githubStatus.data.github_repo_name}
                                                    </p>
                                                    {githubStatus.data.last_github_sync && (
                                                        <p className="text-xs text-muted-foreground mt-1">
                                                            Last sync: {new Date(githubStatus.data.last_github_sync).toLocaleString()}
                                                        </p>
                                                    )}
                                                </div>
                                            </>
                                        ) : (
                                            <>
                                                <XCircle className="h-6 w-6 text-orange-500" />
                                                <div>
                                                    <p className="font-medium">Not Linked</p>
                                                    <p className="text-sm text-muted-foreground">
                                                        Link this project to push code to GitHub
                                                    </p>
                                                </div>
                                            </>
                                        )}
                                    </div>
                                    {githubStatus?.data?.github_linked && (
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={unlinkProject}
                                            disabled={isUnlinking}
                                        >
                                            {isUnlinking ? (
                                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                            ) : (
                                                <Unlink className="h-4 w-4 mr-2" />
                                            )}
                                            Unlink
                                        </Button>
                                    )}
                                </div>

                                {/* Link Repository Options - Only show when not linked and connected */}
                                {!githubStatus?.data?.github_linked && status?.data.connected && (
                                    <div className="space-y-3 pt-4 border-t">
                                        <p className="text-sm font-medium">Link Repository</p>
                                        <div className="flex gap-2">
                                            <Dialog open={showCreateRepoModal} onOpenChange={setShowCreateRepoModal}>
                                                <DialogTrigger asChild>
                                                    <Button variant="outline">
                                                        <Plus className="h-4 w-4 mr-2" />
                                                        Create & Link New Repository
                                                    </Button>
                                                </DialogTrigger>
                                                <DialogContent>
                                                    <DialogHeader>
                                                        <DialogTitle>Create New Repository</DialogTitle>
                                                    </DialogHeader>
                                                    <div className="space-y-4">
                                                        <div>
                                                            <Label htmlFor="repo-name">Repository Name</Label>
                                                            <Input
                                                                id="repo-name"
                                                                value={newRepoName}
                                                                onChange={(e) => setNewRepoName(e.target.value)}
                                                                placeholder={`${project.name.toLowerCase().replace(/\s+/g, '-')}-infra`}
                                                            />
                                                        </div>
                                                        <div>
                                                            <Label htmlFor="repo-description">Description</Label>
                                                            <Textarea
                                                                id="repo-description"
                                                                value={newRepoDescription}
                                                                onChange={(e) => setNewRepoDescription(e.target.value)}
                                                                placeholder={`Infrastructure code for ${project.name}`}
                                                            />
                                                        </div>
                                                        <div className="flex items-center space-x-2">
                                                            <Switch
                                                                id="repo-private"
                                                                checked={newRepoPrivate}
                                                                onCheckedChange={setNewRepoPrivate}
                                                            />
                                                            <Label htmlFor="repo-private">Private repository</Label>
                                                        </div>
                                                        <div className="flex gap-2">
                                                            <Button
                                                                onClick={handleCreateAndLinkRepo}
                                                                disabled={isCreatingRepo || isPushingProject}
                                                                className="flex-1"
                                                            >
                                                                {isCreatingRepo || isPushingProject ? (
                                                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                                                ) : (
                                                                    <Plus className="h-4 w-4 mr-2" />
                                                                )}
                                                                Create & Link Repository
                                                            </Button>
                                                            <Button
                                                                variant="outline"
                                                                onClick={() => setShowCreateRepoModal(false)}
                                                            >
                                                                Cancel
                                                            </Button>
                                                        </div>
                                                    </div>
                                                </DialogContent>
                                            </Dialog>

                                            <Dialog open={showLinkRepoModal} onOpenChange={setShowLinkRepoModal}>
                                                <DialogTrigger asChild>
                                                    <Button>
                                                        <Link className="h-4 w-4 mr-2" />
                                                        Link Existing Repository
                                                    </Button>
                                                </DialogTrigger>
                                                <DialogContent className="max-w-2xl">
                                                    <DialogHeader>
                                                        <DialogTitle>Link Existing Repository</DialogTitle>
                                                    </DialogHeader>
                                                    <div className="space-y-4">
                                                        <p className="text-sm text-muted-foreground">
                                                            Select an existing repository to link to this project.
                                                        </p>
                                                        {repositories.length > 0 ? (
                                                            <div className="grid gap-2 max-h-60 overflow-y-auto">
                                                                {repositories.map((repo) => (
                                                                    <Card
                                                                        key={repo.id}
                                                                        className="cursor-pointer transition-colors hover:bg-muted/50"
                                                                        onClick={() => handleLinkExistingRepo(repo)}
                                                                    >
                                                                        <CardContent className="p-3">
                                                                            <div className="flex items-center justify-between">
                                                                                <div>
                                                                                    <h4 className="font-medium">{repo.name}</h4>
                                                                                    <p className="text-sm text-muted-foreground">{repo.full_name}</p>
                                                                                </div>
                                                                                <div className="flex items-center gap-2">
                                                                                    {repo.private && <Badge variant="secondary">Private</Badge>}
                                                                                    <Link className="h-4 w-4" />
                                                                                </div>
                                                                            </div>
                                                                        </CardContent>
                                                                    </Card>
                                                                ))}
                                                            </div>
                                                        ) : (
                                                            <div className="text-center py-8 text-muted-foreground">
                                                                <Github className="h-12 w-12 mx-auto mb-4 opacity-50" />
                                                                <p>No repositories found.</p>
                                                                <p className="text-sm">Click "Load Repositories" to fetch your repositories.</p>
                                                            </div>
                                                        )}
                                                        <div className="flex gap-2">
                                                            <Button
                                                                variant="outline"
                                                                onClick={loadRepositories}
                                                                disabled={loadingRepos}
                                                                className="flex-1"
                                                            >
                                                                {loadingRepos ? (
                                                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                                                ) : (
                                                                    <RefreshCw className="h-4 w-4 mr-2" />
                                                                )}
                                                                Load Repositories
                                                            </Button>
                                                            <Button
                                                                variant="outline"
                                                                onClick={() => setShowLinkRepoModal(false)}
                                                            >
                                                                Cancel
                                                            </Button>
                                                        </div>
                                                    </div>
                                                </DialogContent>
                                            </Dialog>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    {/* Push Code Section - Only show when project is linked */}
                    {githubStatus?.data?.github_linked && (
                        <div className="space-y-3">
                            <h4 className="font-semibold">Push Code to Repository</h4>
                            <Card className="border-blue-200 bg-blue-50/50">
                                <CardContent className="pt-4 space-y-4">
                                    <div className="flex items-center gap-3">
                                        <Upload className="h-6 w-6 text-blue-600" />
                                        <div className="flex-1">
                                            <p className="font-medium text-blue-800">Push Project Code</p>
                                            <p className="text-sm text-blue-700">
                                                Push all generated infrastructure code to {githubStatus.data.github_repo_name}
                                            </p>
                                        </div>
                                    </div>

                                    {/* Branch Selection */}
                                    <div className="flex gap-2 items-end">
                                        <div className="flex-1">
                                            <Label htmlFor="push-branch-select" className="text-sm font-medium">Branch</Label>
                                            <Select value={selectedBranch} onValueChange={setSelectedBranch}>
                                                <SelectTrigger id="push-branch-select">
                                                    <SelectValue placeholder="Select branch" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {branches.map((branch) => (
                                                        <SelectItem key={branch.name} value={branch.name}>
                                                            <div className="flex items-center gap-2">
                                                                <GitBranch className="h-3 w-3" />
                                                                {branch.name}
                                                                {branch.protected && <Badge variant="secondary" className="text-xs">Protected</Badge>}
                                                            </div>
                                                        </SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                        </div>

                                        {/* Create New Branch */}
                                        <Dialog open={showCreateBranch} onOpenChange={setShowCreateBranch}>
                                            <DialogTrigger asChild>
                                                <Button size="sm" variant="outline">
                                                    <Plus className="h-3 w-3 mr-1" />
                                                    New Branch
                                                </Button>
                                            </DialogTrigger>
                                            <DialogContent>
                                                <DialogHeader>
                                                    <DialogTitle>Create New Branch</DialogTitle>
                                                </DialogHeader>
                                                <div className="space-y-4">
                                                    <div>
                                                        <Label htmlFor="push-branch-name">Branch Name</Label>
                                                        <Input
                                                            id="push-branch-name"
                                                            value={newBranchName}
                                                            onChange={(e) => setNewBranchName(e.target.value)}
                                                            placeholder="feature/terraform-updates"
                                                        />
                                                    </div>
                                                    <div>
                                                        <Label>Source Branch</Label>
                                                        <Select value={selectedBranch} onValueChange={setSelectedBranch}>
                                                            <SelectTrigger>
                                                                <SelectValue />
                                                            </SelectTrigger>
                                                            <SelectContent>
                                                                {branches.map((branch) => (
                                                                    <SelectItem key={branch.name} value={branch.name}>
                                                                        {branch.name}
                                                                    </SelectItem>
                                                                ))}
                                                            </SelectContent>
                                                        </Select>
                                                    </div>
                                                    <div className="flex gap-2">
                                                        <Button
                                                            onClick={createBranch}
                                                            disabled={isCreatingBranch || !newBranchName.trim()}
                                                            className="flex-1"
                                                        >
                                                            {isCreatingBranch ? (
                                                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                                            ) : (
                                                                <Plus className="h-4 w-4 mr-2" />
                                                            )}
                                                            Create Branch
                                                        </Button>
                                                        <Button
                                                            variant="outline"
                                                            onClick={() => setShowCreateBranch(false)}
                                                        >
                                                            Cancel
                                                        </Button>
                                                    </div>
                                                </div>
                                            </DialogContent>
                                        </Dialog>
                                    </div>

                                    <div className="space-y-2">
                                        <Label htmlFor="commit-message" className="text-sm font-medium">Commit Message</Label>
                                        <Input
                                            id="commit-message"
                                            value={pushCommitMessage}
                                            onChange={(e) => setPushCommitMessage(e.target.value)}
                                            placeholder="Push infrastructure code from InfraJet"
                                            className="bg-white"
                                        />
                                    </div>

                                    <div className="flex justify-end">
                                        <Button
                                            onClick={handlePushCode}
                                            disabled={isPushingProject}
                                        >
                                            {isPushingProject ? (
                                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                            ) : (
                                                <Upload className="h-4 w-4 mr-2" />
                                            )}
                                            Push to {selectedBranch}
                                        </Button>
                                    </div>
                                </CardContent>
                            </Card>
                        </div>
                    )}
                </CardContent>
            </Card>
        </>
    );
};