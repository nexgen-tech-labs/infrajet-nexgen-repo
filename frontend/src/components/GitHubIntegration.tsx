import React, { useState, useEffect, useMemo } from 'react';
import { useGitHub } from '@/contexts/GitHubContext';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useToast } from '@/hooks/use-toast';
import { GitBranch, Github, Settings, ExternalLink, Plus, RefreshCw, Upload, CheckCircle, AlertCircle, Loader2, Search, X } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { createRepo } from '@/services/githubService';
import { githubApi } from '@/services/infrajetApi';
import SettingsDialog from './SettingsDialog';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';

interface GitHubIntegrationProps {
  onCodePush?: (files: { path: string; content: string }[], repoInfo: { name: string; url: string }) => void;
  generatedCode?: string;
}

const GitHubIntegration = ({ onCodePush, generatedCode }: GitHubIntegrationProps = {}) => {
  const {
    isConnected,
    githubUser,
    selectedRepo,
    repos,
    organizations,
    selectedOrganization,
    connectToGitHub,
    disconnectFromGitHub,
    selectRepo,
    selectOrganization,
    refreshRepos,
    pushCode,
    loading
  } = useGitHub();
  const { toast } = useToast();
  const [isCreateRepoOpen, setIsCreateRepoOpen] = useState(false);
  const [isPushCodeOpen, setIsPushCodeOpen] = useState(false);
  const [isRepoModalOpen, setIsRepoModalOpen] = useState(false);
  const [newRepoName, setNewRepoName] = useState('');
  const [newRepoDescription, setNewRepoDescription] = useState('Generated infrastructure code');
  const [newRepoPrivate, setNewRepoPrivate] = useState(false);
  const [commitMessage, setCommitMessage] = useState('Add generated infrastructure code');
  const [autoCreateRepo, setAutoCreateRepo] = useState(true);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [repoSearchQuery, setRepoSearchQuery] = useState('');
  const [connectionStatus, setConnectionStatus] = useState<'checking' | 'connected' | 'disconnected'>('checking');
  const [localRepos, setLocalRepos] = useState<any[]>([]);
  const [loadingRepos, setLoadingRepos] = useState(false);

  // Filtered repositories based on search query
  const filteredRepos = useMemo(() => {
    if (!repoSearchQuery.trim()) return localRepos;
    return localRepos.filter(repo =>
      repo.name.toLowerCase().includes(repoSearchQuery.toLowerCase()) ||
      repo.full_name.toLowerCase().includes(repoSearchQuery.toLowerCase())
    );
  }, [localRepos, repoSearchQuery]);

  useEffect(() => {
    if (isConnected && localRepos.length === 0) {
      loadRepositories();
    }
    setConnectionStatus(isConnected ? 'connected' : 'disconnected');
  }, [isConnected, localRepos.length]);

  const loadRepositories = async () => {
    if (!isConnected) return;

    setLoadingRepos(true);
    try {
      console.log('GitHubIntegration: Loading repositories...');
      const response = await githubApi.getRepositories();
      console.log('GitHubIntegration: Repositories response:', response);
      setLocalRepos(response.data.repositories);
      console.log('GitHubIntegration: Set repositories:', response.data.repositories.length, 'repos');
    } catch (error: any) {
      console.error('GitHubIntegration: Error loading repositories:', error);
      toast({
        title: 'Failed to load repositories',
        description: error.message,
        variant: 'destructive',
      });
    } finally {
      setLoadingRepos(false);
    }
  };

  // Generate a hash-based repo name for temporary repos
  const generateTempRepoName = () => {
    const timestamp = Date.now();
    const hash = timestamp.toString(36);
    return `infrajet-temp-${hash}`;
  };

  const handleCreateRepo = async () => {
    if (!newRepoName.trim()) {
      toast({
        title: "Validation Error",
        description: "Repository name is required",
        variant: "destructive",
      });
      return;
    }

    // Validate repository name format
    const repoNameRegex = /^[a-zA-Z0-9._-]+$/;
    if (!repoNameRegex.test(newRepoName)) {
      toast({
        title: "Invalid Repository Name",
        description: "Repository name can only contain letters, numbers, hyphens, underscores, and periods",
        variant: "destructive",
      });
      return;
    }

    try {
      const result = await createRepo(
        '', // token will be handled in the service
        newRepoName,
        newRepoDescription,
        newRepoPrivate,
        selectedOrganization
      );

      setIsCreateRepoOpen(false);
      setNewRepoName('');
      setNewRepoDescription('Generated infrastructure code');
      setNewRepoPrivate(false);

      await loadRepositories();

      toast({
        title: "Repository Created",
        description: `Successfully created ${result.name} ${newRepoPrivate ? '(Private)' : '(Public)'}`,
      });
    } catch (error) {
      console.error('Repository creation error:', error);
      toast({
        title: "Failed to Create Repository",
        description: error.message || "An unexpected error occurred while creating the repository",
        variant: "destructive",
      });
    }
  };

  const handlePushCode = async () => {
    try {
      let targetRepo = selectedRepo;

      // If auto-create is enabled and no repo is selected, create a temporary repo
      if (autoCreateRepo && !targetRepo) {
        const tempRepoName = generateTempRepoName();
        toast({
          title: "Creating Repository",
          description: `Creating temporary repository: ${tempRepoName}`,
        });

        await createRepo('', tempRepoName, 'Temporary repository for generated infrastructure code', newRepoPrivate, selectedOrganization);
        await loadRepositories();

        // Find the newly created repo from the current repos list
        targetRepo = localRepos.find(repo => repo.name === tempRepoName);

        if (targetRepo) {
          selectRepo(targetRepo);
          toast({
            title: "Repository Created",
            description: `Successfully created ${tempRepoName}`,
          });
        } else {
          throw new Error('Failed to find created repository');
        }
      }

      if (!targetRepo) {
        toast({
          title: "No Repository Selected",
          description: "Please select a repository or enable auto-create to proceed",
          variant: "destructive",
        });
        return;
      }

      const files = [
        {
          path: 'infrastructure.tf',
          content: generatedCode || '# Generated infrastructure code\n# Add your Terraform configuration here'
        }
      ];

      toast({
        title: "Pushing Code",
        description: `Pushing to ${targetRepo.name}...`,
      });

      await pushCode(files, commitMessage);

      setIsPushCodeOpen(false);
      setCommitMessage('Add generated infrastructure code');

      toast({
        title: "Code Pushed Successfully",
        description: `Infrastructure code pushed to ${targetRepo.name}`,
      });

      // Call the callback if provided
      onCodePush?.(files, { name: targetRepo.name, url: targetRepo.html_url });

    } catch (error) {
      console.error('Push code error:', error);

      let errorMessage = "An unexpected error occurred while pushing code";
      if (error.message) {
        if (error.message.includes('permission')) {
          errorMessage = "You don't have permission to push to this repository";
        } else if (error.message.includes('not found')) {
          errorMessage = "Repository not found. Please check the repository name and try again";
        } else if (error.message.includes('rate limit')) {
          errorMessage = "GitHub API rate limit exceeded. Please try again later";
        } else {
          errorMessage = error.message;
        }
      }

      toast({
        title: "Failed to Push Code",
        description: errorMessage,
        variant: "destructive",
      });
    }
  };

  const handleQuickPush = async () => {
    if (!selectedRepo && !autoCreateRepo) {
      toast({
        title: "Repository Required",
        description: "Please select a repository first or enable auto-create in settings",
        variant: "destructive",
      });
      return;
    }

    if (!generatedCode) {
      toast({
        title: "No Code to Push",
        description: "Please generate some infrastructure code first",
        variant: "destructive",
      });
      return;
    }

    await handlePushCode();
  };

  // Connection Status Component
  const ConnectionStatus = () => {
    if (connectionStatus === 'checking') {
      return (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span className="text-sm">Checking connection...</span>
        </div>
      );
    }

    if (connectionStatus === 'connected') {
      return (
        <div className="flex items-center gap-2 text-green-600">
          <CheckCircle className="w-4 h-4" />
          <span className="text-sm font-medium">Connected</span>
        </div>
      );
    }

    return (
      <div className="flex items-center gap-2 text-orange-600">
        <AlertCircle className="w-4 h-4" />
        <span className="text-sm font-medium">Not Connected</span>
      </div>
    );
  };

  if (!isConnected) {
    return (
      <>
        <div className="flex items-center gap-2">
          <Button
            onClick={() => setIsSettingsOpen(true)}
            variant="outline"
            size="sm"
            className="flex items-center gap-2 bg-background/80 border-border hover:bg-accent hover:text-accent-foreground"
            title="Open settings"
          >
            <Settings className="w-4 h-4" />
            <span className="hidden sm:inline">Settings</span>
          </Button>

          <Dialog>
            <DialogTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="flex items-center gap-2 bg-background/80 border-border hover:bg-accent hover:text-accent-foreground"
                title="Connect to GitHub"
              >
                <Github className="w-4 h-4" />
                <span className="hidden sm:inline">Connect GitHub</span>
              </Button>
            </DialogTrigger>
            <DialogContent className="bg-background border-border max-w-md">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2 text-foreground">
                  <Github className="w-5 h-5" />
                  Connect to GitHub
                </DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <div className="text-center p-6 rounded-lg bg-muted/30">
                  <Github className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
                  <h3 className="text-lg font-semibold mb-2">Connect Your GitHub Account</h3>
                  <p className="text-sm text-muted-foreground mb-4">
                    Link your GitHub account to sync projects and push generated infrastructure code.
                  </p>
                  <Button
                    onClick={async () => {
                      try {
                        await connectToGitHub();
                      } catch (error) {
                        toast({
                          title: "Connection Failed",
                          description: error.message || "Failed to initiate GitHub connection",
                          variant: "destructive",
                        });
                      }
                    }}
                    className="w-full"
                  >
                    <Github className="w-4 h-4 mr-2" />
                    Connect GitHub Account
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>
        <SettingsDialog open={isSettingsOpen} onOpenChange={setIsSettingsOpen} />
      </>
    );
  }

  return (
    <>
      <div className="flex items-center gap-2">
        {/* Settings Button */}
        <Button
          onClick={() => setIsSettingsOpen(true)}
          variant="outline"
          size="sm"
          className="flex items-center gap-2 bg-background/80 border-border hover:bg-accent hover:text-accent-foreground"
          title="Open settings"
        >
          <Settings className="w-4 h-4" />
          <span className="hidden sm:inline">Settings</span>
        </Button>

        {/* Main GitHub Integration Dialog */}
        <Dialog>
          <DialogTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              className="flex items-center gap-2 bg-background/80 border-border hover:bg-accent hover:text-accent-foreground"
              title="Manage GitHub integration"
            >
              <Github className="w-4 h-4" />
              <span className="hidden sm:inline">GitHub</span>
              <ConnectionStatus />
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-background border-border max-w-2xl max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-foreground">
                <Github className="w-5 h-5" />
                GitHub Integration
              </DialogTitle>
            </DialogHeader>

            <div className="space-y-6">
              {/* User Profile Card */}
              {githubUser && (
                <Card>
                  <CardContent className="p-4">
                    <div className="flex items-center gap-3">
                      <img
                        src={githubUser.avatar_url}
                        alt={githubUser.name}
                        className="w-12 h-12 rounded-full border-2 border-border"
                      />
                      <div className="flex-1">
                        <h3 className="font-semibold text-foreground">{githubUser.name}</h3>
                        <p className="text-sm text-muted-foreground">@{githubUser.login}</p>
                        <ConnectionStatus />
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={async () => {
                          try {
                            await disconnectFromGitHub();
                            toast({
                              title: "Disconnected",
                              description: "Successfully disconnected from GitHub",
                            });
                          } catch (error) {
                            toast({
                              title: "Disconnect Failed",
                              description: error.message || "Failed to disconnect from GitHub",
                              variant: "destructive",
                            });
                          }
                        }}
                        className="text-destructive hover:text-destructive"
                      >
                        Disconnect
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Organization Selection */}
              <div className="space-y-2">
                <Label className="text-foreground font-medium">Organization</Label>
                <Select
                  value={selectedOrganization || 'personal'}
                  onValueChange={(value) => {
                    selectOrganization(value);
                  }}
                >
                  <SelectTrigger className="bg-background border-border text-foreground">
                    <SelectValue placeholder="Choose organization" />
                  </SelectTrigger>
                  <SelectContent className="bg-background border-border">
                    <SelectItem value="personal" className="text-foreground hover:bg-accent">
                      <div className="flex items-center gap-2">
                        <Github className="w-4 h-4" />
                        <span>Personal Account</span>
                      </div>
                    </SelectItem>
                    {organizations.map((org) => (
                      <SelectItem key={org.id} value={org.login} className="text-foreground hover:bg-accent">
                        <div className="flex items-center gap-2">
                          <img src={org.avatar_url} alt={org.login} className="w-4 h-4 rounded-full" />
                          <span>{org.login}</span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <Separator />

              {/* Repository Selection */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <Label className="text-foreground font-medium">Repository</Label>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={async () => {
                        try {
                          await loadRepositories();
                          toast({
                            title: "Repositories Refreshed",
                            description: "Repository list has been updated",
                          });
                        } catch (error) {
                          toast({
                            title: "Refresh Failed",
                            description: error.message || "Failed to refresh repositories",
                            variant: "destructive",
                          });
                        }
                      }}
                      disabled={loadingRepos}
                      className="border-border hover:bg-accent"
                    >
                      <RefreshCw className={`w-4 h-4 ${loadingRepos ? 'animate-spin' : ''}`} />
                      <span className="ml-2">Refresh</span>
                    </Button>
                    <Dialog open={isCreateRepoOpen} onOpenChange={setIsCreateRepoOpen}>
                      <DialogTrigger asChild>
                        <Button variant="outline" size="sm" className="border-border hover:bg-accent">
                          <Plus className="w-4 h-4 mr-2" />
                          Create
                        </Button>
                      </DialogTrigger>
                      <DialogContent className="bg-background border-border">
                        <DialogHeader>
                          <DialogTitle className="text-foreground">Create New Repository</DialogTitle>
                        </DialogHeader>
                        <div className="space-y-4">
                          <div>
                            <Label htmlFor="repo-name" className="text-foreground">Repository Name</Label>
                            <Input
                              id="repo-name"
                              value={newRepoName}
                              onChange={(e) => setNewRepoName(e.target.value)}
                              placeholder="my-awesome-repo"
                              className="bg-background border-border text-foreground"
                            />
                          </div>
                          <div>
                            <Label htmlFor="repo-description" className="text-foreground">Description</Label>
                            <Textarea
                              id="repo-description"
                              value={newRepoDescription}
                              onChange={(e) => setNewRepoDescription(e.target.value)}
                              placeholder="Repository description..."
                              className="bg-background border-border text-foreground"
                            />
                          </div>
                          <div className="flex items-center space-x-2">
                            <Switch
                              id="repo-private"
                              checked={newRepoPrivate}
                              onCheckedChange={setNewRepoPrivate}
                            />
                            <Label htmlFor="repo-private" className="text-foreground">Private repository</Label>
                          </div>
                          <div className="flex gap-2">
                            <Button onClick={handleCreateRepo} disabled={loading} className="flex-1">
                              {loading ? 'Creating...' : 'Create Repository'}
                            </Button>
                            <Button variant="outline" onClick={() => setIsCreateRepoOpen(false)}>
                              Cancel
                            </Button>
                          </div>
                        </div>
                      </DialogContent>
                    </Dialog>
                  </div>
                </div>

                {/* Repository Search */}
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    placeholder="Search repositories..."
                    value={repoSearchQuery}
                    onChange={(e) => setRepoSearchQuery(e.target.value)}
                    className="pl-10 bg-background border-border text-foreground"
                  />
                  {repoSearchQuery && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="absolute right-2 top-1/2 transform -translate-y-1/2 h-6 w-6 p-0"
                      onClick={() => setRepoSearchQuery('')}
                    >
                      <X className="w-4 h-4" />
                    </Button>
                  )}
                </div>

                {/* Repository Grid */}
                <div className="grid grid-cols-1 gap-2 max-h-60 overflow-y-auto">
                  {filteredRepos.map((repo) => (
                    <div
                      key={repo.id}
                      onClick={() => selectRepo(repo)}
                      className={`p-3 rounded-lg border cursor-pointer transition-all hover:shadow-md ${
                        selectedRepo?.id === repo.id
                          ? 'border-primary bg-primary/5 shadow-sm'
                          : 'border-border bg-muted/30 hover:bg-muted/50'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <GitBranch className="w-4 h-4 text-muted-foreground" />
                          <div>
                            <h4 className="font-medium text-foreground">{repo.name}</h4>
                            <p className="text-sm text-muted-foreground">{repo.full_name}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {repo.private && <Badge variant="outline" className="text-xs">Private</Badge>}
                          <a
                            href={repo.html_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary hover:text-primary/80"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <ExternalLink className="w-4 h-4" />
                          </a>
                        </div>
                      </div>
                    </div>
                  ))}
                  {filteredRepos.length === 0 && repoSearchQuery && (
                    <div className="text-center py-8 text-muted-foreground">
                      <Search className="w-8 h-8 mx-auto mb-2 opacity-50" />
                      <p>No repositories found matching "{repoSearchQuery}"</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Selected Repository Display */}
              {selectedRepo && (
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <GitBranch className="w-4 h-4" />
                      Selected Repository
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="pt-0">
                    <div className="flex items-center justify-between">
                      <div>
                        <h4 className="font-medium text-foreground">{selectedRepo.name}</h4>
                        <p className="text-sm text-muted-foreground">{selectedRepo.full_name}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        {selectedRepo.private && <Badge variant="outline">Private</Badge>}
                        <a
                          href={selectedRepo.html_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-primary hover:text-primary/80"
                        >
                          <ExternalLink className="w-4 h-4" />
                        </a>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          </DialogContent>
        </Dialog>

        {/* Quick Push Button */}
        <Button
          onClick={handleQuickPush}
          size="sm"
          className="flex items-center gap-2"
          title="Push code to GitHub (auto-creates repo if needed)"
          disabled={loading}
        >
          <Upload className="w-4 h-4" />
          <span className="hidden sm:inline">{loading ? 'Pushing...' : 'Push Code'}</span>
        </Button>

        {/* Advanced Push Dialog */}
        {generatedCode && (
          <Dialog open={isPushCodeOpen} onOpenChange={setIsPushCodeOpen}>
            <DialogTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="flex items-center gap-2"
                title="Advanced push options"
              >
                <Settings className="w-4 h-4" />
              </Button>
            </DialogTrigger>
            <DialogContent className="bg-background border-border">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2 text-foreground">
                  <Upload className="w-5 h-5" />
                  Push Code to GitHub
                </DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <div className="flex items-center space-x-2">
                  <Switch
                    id="auto-create"
                    checked={autoCreateRepo}
                    onCheckedChange={setAutoCreateRepo}
                  />
                  <Label htmlFor="auto-create" className="text-foreground">
                    Auto-create temporary repository if none selected
                  </Label>
                </div>

                {selectedRepo ? (
                  <Card>
                    <CardContent className="p-3">
                      <div className="flex items-center gap-2">
                        <GitBranch className="w-4 h-4 text-muted-foreground" />
                        <span className="text-foreground">Target: {selectedRepo.name}</span>
                        {selectedRepo.private && <Badge variant="outline" className="text-xs">Private</Badge>}
                      </div>
                    </CardContent>
                  </Card>
                ) : autoCreateRepo ? (
                  <Card>
                    <CardContent className="p-3">
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <Plus className="w-4 h-4" />
                        <span className="text-sm">Will create: {generateTempRepoName()}</span>
                      </div>
                    </CardContent>
                  </Card>
                ) : (
                  <Card className="border-destructive/20 bg-destructive/5">
                    <CardContent className="p-3">
                      <div className="flex items-center gap-2 text-destructive">
                        <AlertCircle className="w-4 h-4" />
                        <span className="text-sm">Select a repository or enable auto-create</span>
                      </div>
                    </CardContent>
                  </Card>
                )}

                <div>
                  <Label htmlFor="commit-message" className="text-foreground">Commit Message</Label>
                  <Input
                    id="commit-message"
                    value={commitMessage}
                    onChange={(e) => setCommitMessage(e.target.value)}
                    placeholder="Add generated infrastructure code"
                    className="bg-background border-border text-foreground"
                  />
                </div>

                <div className="flex gap-2">
                  <Button onClick={handlePushCode} disabled={loading} className="flex-1">
                    {loading ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Pushing...
                      </>
                    ) : (
                      <>
                        <Upload className="w-4 h-4 mr-2" />
                        Push Code
                      </>
                    )}
                  </Button>
                  <Button variant="outline" onClick={() => setIsPushCodeOpen(false)}>
                    Cancel
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        )}
      </div>
      <SettingsDialog open={isSettingsOpen} onOpenChange={setIsSettingsOpen} />
    </>
  );
};

export default GitHubIntegration;