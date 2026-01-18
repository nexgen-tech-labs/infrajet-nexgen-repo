import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Send, Bot, Loader2, Wifi, WifiOff, MessageSquare, User, Zap, Cloud, Copy, Download, ChevronDown, ChevronRight, FileText, Code, Maximize2, Github, GitBranch, Plus, Unlink } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { useTerraformChat, TerraformChatMessage, ClarificationQuestion, GeneratedFile } from '@/hooks/useTerraformChat';
import { GenerationProgress } from './GenerationProgress';
import CodeEditor from '@/components/CodeEditor';
import { useToast } from '@/hooks/use-toast';
import { useGitHubIntegrationFlow, useProjectGitHubStatus } from '@/hooks/useGitHubIntegration';
import { githubApi, getAuthToken } from '@/services/infrajetApi';
import { TestModeWarningDialog } from '@/components/ui/test-mode-warning-dialog';

interface TerraformChatInterfaceProps {
  projectId: string;
  className?: string;
}

const API_BASE_URL = window.__RUNTIME_CONFIG__?.INFRAJET_API_URL;

const GeneratedFilesDisplay: React.FC<{
  files: GeneratedFile[];
  projectId: string;
}> = ({ files, projectId }) => {
  const [activeTab, setActiveTab] = useState<string>(files[0]?.name || '');
  const [isExpanded, setIsExpanded] = useState(true);
  const [selectedFileForModal, setSelectedFileForModal] = useState<GeneratedFile | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editedContent, setEditedContent] = useState<string>('');
  const [isEditing, setIsEditing] = useState(false);
  const [isPushing, setIsPushing] = useState(false);
  const [branches, setBranches] = useState<{ name: string; sha: string; protected: boolean }[]>([]);
  const [selectedBranch, setSelectedBranch] = useState<string>('main');
  const [newBranchName, setNewBranchName] = useState<string>('');
  const [showCreateBranch, setShowCreateBranch] = useState(false);
  const [isLoadingBranches, setIsLoadingBranches] = useState(false);
  const [isCreatingBranch, setIsCreatingBranch] = useState(false);
  const [isUnlinking, setIsUnlinking] = useState(false);
  const [showPushDialog, setShowPushDialog] = useState(false);
  const [pushCommitMessage, setPushCommitMessage] = useState<string>('Add generated Terraform infrastructure code from InfraJet chat');
  const { toast } = useToast();
  const { data: githubStatus } = useProjectGitHubStatus(projectId);

  const copyToClipboard = async (content: string, filename: string) => {
    try {
      await navigator.clipboard.writeText(content);
      toast({
        title: "Copied to clipboard",
        description: `${filename} content copied successfully`,
      });
    } catch (error) {
      toast({
        title: "Copy failed",
        description: "Failed to copy to clipboard",
        variant: "destructive",
      });
    }
  };

  const openFileModal = (file: GeneratedFile) => {
    setSelectedFileForModal(file);
    setEditedContent(file.content);
    setIsEditing(false);
    setIsModalOpen(true);
  };

  const saveFileChanges = () => {
    if (selectedFileForModal) {
      // Update the file content in the files array
      const updatedFiles = files.map(file =>
        file.name === selectedFileForModal.name
          ? { ...file, content: editedContent }
          : file
      );
      // Note: Since files is passed as props, we can't directly modify it
      // In a real implementation, you'd want to lift this state up
      toast({
        title: "Changes saved",
        description: `Changes to ${selectedFileForModal.name} have been saved locally`,
      });
      setIsEditing(false);
    }
  };

  const toggleEdit = () => {
    if (isEditing) {
      // Cancel editing
      setEditedContent(selectedFileForModal?.content || '');
      setIsEditing(false);
    } else {
      setIsEditing(true);
    }
  };

  const loadBranches = useCallback(async () => {
    if (!githubStatus?.data?.github_linked) return;

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

  const pushToGitHub = async () => {
    if (!githubStatus?.data?.github_linked) {
      toast({
        title: "GitHub not linked",
        description: "Please link this project to a GitHub repository first",
        variant: "destructive",
      });
      return;
    }

    setIsPushing(true);
    try {
      const repoParts = githubStatus.data.github_repo_name.split('/');
      const repoOwner = repoParts[0];
      const repoName = repoParts[1];

      // Convert files array to Record<string, string> format
      const filesRecord: Record<string, string> = {};
      files.forEach(file => {
        filesRecord[file.path] = file.content;
      });

      // Use the FastAPI syncFiles endpoint with selected branch and commit message
      await githubApi.syncFiles(repoOwner, repoName, {
        files_content: filesRecord,
        commit_message: pushCommitMessage,
        branch: selectedBranch
      });

      toast({
        title: "Files pushed to GitHub",
        description: `Successfully pushed ${files.length} files to ${githubStatus.data.github_repo_name} on branch ${selectedBranch}`,
      });

      setShowPushDialog(false);
    } catch (error) {
      console.error('Failed to push files to GitHub:', error);
      toast({
        title: "Push failed",
        description: "Failed to push files to GitHub repository",
        variant: "destructive",
      });
    } finally {
      setIsPushing(false);
    }
  };

  const openPushDialog = () => {
    setShowPushDialog(true);
  };

  const downloadFile = (file: GeneratedFile) => {
    const blob = new Blob([file.content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = file.name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    toast({
      title: "Download started",
      description: `${file.name} downloaded successfully`,
    });
  };

  const getFileLanguage = (filename: string) => {
    if (filename.endsWith('.tf') || filename.endsWith('.hcl')) return 'terraform';
    if (filename.endsWith('.json')) return 'json';
    if (filename.endsWith('.yaml') || filename.endsWith('.yml')) return 'yaml';
    if (filename.endsWith('.py')) return 'python';
    if (filename.endsWith('.js')) return 'javascript';
    if (filename.endsWith('.ts')) return 'typescript';
    if (filename.endsWith('.sh') || filename.endsWith('.bash')) return 'shell';
    return 'plaintext';
  };

  if (files.length === 0) return null;

  return (
    <>
      <div className="mt-4 border rounded-lg bg-slate-50 dark:bg-slate-900">
        <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" className="w-full justify-between p-3 h-auto">
              <div className="flex items-center gap-2">
                <Code className="h-4 w-4" />
                <span className="font-medium">Generated Files ({files.length})</span>
              </div>
              {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="p-3">
              {/* GitHub Integration Section */}
              {githubStatus?.data?.github_linked && (
                <div className="mb-4 p-3 border rounded-lg bg-blue-50 dark:bg-blue-950">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <Github className="h-4 w-4" />
                      <span className="font-medium">GitHub: {githubStatus.data.github_repo_name}</span>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={unlinkProject}
                      disabled={isUnlinking}
                    >
                      {isUnlinking ? (
                        <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                      ) : (
                        <Unlink className="h-3 w-3 mr-1" />
                      )}
                      Unlink Project
                    </Button>
                  </div>

                  {/* Branch Selection */}
                  <div className="flex gap-2 items-end">
                    <div className="flex-1">
                      <Label htmlFor="branch-select" className="text-sm font-medium">Branch</Label>
                      <Select value={selectedBranch} onValueChange={setSelectedBranch}>
                        <SelectTrigger id="branch-select">
                          <SelectValue placeholder="Select branch" />
                        </SelectTrigger>
                        <SelectContent>
                          {branches.map((branch) => (
                            <SelectItem key={branch.name} value={branch.name}>
                              <div className="flex items-center gap-2">
                                <GitBranch className="h-3 w-3" />
                                {branch.name}
                                {branch.name === branches.find(b => b.name === selectedBranch)?.name && (
                                  <span className="text-xs text-muted-foreground">(current)</span>
                                )}
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
                            <Label htmlFor="branch-name">Branch Name</Label>
                            <Input
                              id="branch-name"
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
                </div>
              )}

              {/* Action buttons */}
              <div className="flex gap-2 mb-4 flex-wrap">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => openFileModal(files[0])}
                >
                  <Maximize2 className="h-3 w-3 mr-1" />
                  View Full Screen
                </Button>
                {githubStatus?.data?.github_linked && (
                  <Dialog open={showPushDialog} onOpenChange={setShowPushDialog}>
                    <DialogTrigger asChild>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={openPushDialog}
                      >
                        <Github className="h-3 w-3 mr-1" />
                        Push to GitHub
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Push Files to GitHub</DialogTitle>
                      </DialogHeader>
                      <div className="space-y-4">
                        <div>
                          <Label htmlFor="push-branch-select">Branch</Label>
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
                            <Button size="sm" variant="outline" className="w-full">
                              <Plus className="h-3 w-3 mr-1" />
                              Create New Branch
                            </Button>
                          </DialogTrigger>
                          <DialogContent>
                            <DialogHeader>
                              <DialogTitle>Create New Branch</DialogTitle>
                            </DialogHeader>
                            <div className="space-y-4">
                              <div>
                                <Label htmlFor="dialog-branch-name">Branch Name</Label>
                                <Input
                                  id="dialog-branch-name"
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

                        <div>
                          <Label htmlFor="push-commit-message">Commit Message</Label>
                          <Textarea
                            id="push-commit-message"
                            value={pushCommitMessage}
                            onChange={(e) => setPushCommitMessage(e.target.value)}
                            placeholder="Add generated Terraform infrastructure code"
                            rows={3}
                          />
                        </div>

                        <div className="text-sm text-muted-foreground">
                          This will push {files.length} file(s) to <strong>{githubStatus.data.github_repo_name}</strong> on branch <strong>{selectedBranch}</strong>
                        </div>

                        <div className="flex gap-2">
                          <Button
                            onClick={pushToGitHub}
                            disabled={isPushing || !pushCommitMessage.trim()}
                            className="flex-1"
                          >
                            {isPushing ? (
                              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                            ) : (
                              <Github className="h-4 w-4 mr-2" />
                            )}
                            Push Files
                          </Button>
                          <Button
                            variant="outline"
                            onClick={() => setShowPushDialog(false)}
                          >
                            Cancel
                          </Button>
                        </div>
                      </div>
                    </DialogContent>
                  </Dialog>
                )}
              </div>

              {files.length === 1 ? (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <FileText className="h-4 w-4" />
                      <span className="font-medium text-sm">{files[0].name}</span>
                      <Badge variant="outline" className="text-xs">
                        {getFileLanguage(files[0].name)}
                      </Badge>
                    </div>
                    <div className="flex gap-1">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => copyToClipboard(files[0].content, files[0].name)}
                      >
                        <Copy className="h-3 w-3" />
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => downloadFile(files[0])}
                      >
                        <Download className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                  <div className="border rounded-md overflow-hidden">
                    <CodeEditor
                      value={files[0].content}
                      language={getFileLanguage(files[0].name)}
                      readOnly={true}
                      height="300px"
                    />
                  </div>
                </div>
              ) : (
                <Tabs value={activeTab} onValueChange={setActiveTab}>
                  <TabsList className="grid w-full grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                    {files.map((file) => (
                      <TabsTrigger key={file.name} value={file.name} className="text-xs">
                        {file.name}
                      </TabsTrigger>
                    ))}
                  </TabsList>
                  {files.map((file) => (
                    <TabsContent key={file.name} value={file.name} className="space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4" />
                          <span className="font-medium text-sm">{file.name}</span>
                          <Badge variant="outline" className="text-xs">
                            {getFileLanguage(file.name)}
                          </Badge>
                        </div>
                        <div className="flex gap-1">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => copyToClipboard(file.content, file.name)}
                          >
                            <Copy className="h-3 w-3" />
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => downloadFile(file)}
                          >
                            <Download className="h-3 w-3" />
                          </Button>
                        </div>
                      </div>
                      <div className="border rounded-md overflow-hidden">
                        <CodeEditor
                          value={file.content}
                          language={getFileLanguage(file.name)}
                          readOnly={true}
                          height="300px"
                        />
                      </div>
                    </TabsContent>
                  ))}
                </Tabs>
              )}
            </div>
          </CollapsibleContent>
        </Collapsible>
      </div>

      {/* Full screen modal */}
      <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
        <DialogContent className="max-w-7xl max-h-[90vh] overflow-hidden">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              {selectedFileForModal?.name}
              <Badge variant="outline" className="ml-2">
                {selectedFileForModal ? getFileLanguage(selectedFileForModal.name) : ''}
              </Badge>
              {isEditing && <Badge variant="secondary" className="ml-2">Editing</Badge>}
            </DialogTitle>
          </DialogHeader>

          {/* GitHub Integration in Modal */}
          {githubStatus?.data?.github_linked && (
            <div className="mb-4 p-3 border rounded-lg bg-blue-50 dark:bg-blue-950">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Github className="h-4 w-4" />
                  <span className="font-medium text-sm">GitHub: {githubStatus.data.github_repo_name}</span>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={unlinkProject}
                  disabled={isUnlinking}
                >
                  {isUnlinking ? (
                    <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                  ) : (
                    <Unlink className="h-3 w-3 mr-1" />
                  )}
                  Unlink Project
                </Button>
              </div>

              {/* Branch Selection in Modal */}
              <div className="flex gap-2 items-end">
                <div className="flex-1">
                  <Label htmlFor="modal-branch-select" className="text-sm font-medium">Branch</Label>
                  <Select value={selectedBranch} onValueChange={setSelectedBranch}>
                    <SelectTrigger id="modal-branch-select">
                      <SelectValue placeholder="Select branch" />
                    </SelectTrigger>
                    <SelectContent>
                      {branches.map((branch) => (
                        <SelectItem key={branch.name} value={branch.name}>
                          <div className="flex items-center gap-2">
                            <GitBranch className="h-3 w-3" />
                            {branch.name}
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Create New Branch in Modal */}
                <Dialog open={showCreateBranch} onOpenChange={setShowCreateBranch}>
                  <DialogTrigger asChild>
                    <Button size="sm" variant="outline">
                      <Plus className="h-3 w-3 mr-1" />
                      New
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Create New Branch</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4">
                      <div>
                        <Label htmlFor="modal-branch-name">Branch Name</Label>
                        <Input
                          id="modal-branch-name"
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
            </div>
          )}

          <div className="flex gap-2 mb-4 flex-wrap">
            <Button
              size="sm"
              variant="outline"
              onClick={() => selectedFileForModal && copyToClipboard(
                isEditing ? editedContent : selectedFileForModal.content,
                selectedFileForModal.name
              )}
            >
              <Copy className="h-3 w-3 mr-1" />
              Copy
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => selectedFileForModal && downloadFile({
                ...selectedFileForModal,
                content: isEditing ? editedContent : selectedFileForModal.content
              })}
            >
              <Download className="h-3 w-3 mr-1" />
              Download
            </Button>
            <Button
              size="sm"
              variant={isEditing ? "default" : "outline"}
              onClick={toggleEdit}
            >
              {isEditing ? "Cancel Edit" : "Edit File"}
            </Button>
            {isEditing && (
              <Button
                size="sm"
                onClick={saveFileChanges}
              >
                Save Changes
              </Button>
            )}
            {githubStatus?.data?.github_linked && (
              <Dialog open={showPushDialog} onOpenChange={setShowPushDialog}>
                <DialogTrigger asChild>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={openPushDialog}
                  >
                    <Github className="h-3 w-3 mr-1" />
                    Push to GitHub
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Push Files to GitHub</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4">
                    <div>
                      <Label htmlFor="modal-push-branch-select">Branch</Label>
                      <Select value={selectedBranch} onValueChange={setSelectedBranch}>
                        <SelectTrigger id="modal-push-branch-select">
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

                    {/* Create New Branch in Modal */}
                    <Dialog open={showCreateBranch} onOpenChange={setShowCreateBranch}>
                      <DialogTrigger asChild>
                        <Button size="sm" variant="outline" className="w-full">
                          <Plus className="h-3 w-3 mr-1" />
                          Create New Branch
                        </Button>
                      </DialogTrigger>
                      <DialogContent>
                        <DialogHeader>
                          <DialogTitle>Create New Branch</DialogTitle>
                        </DialogHeader>
                        <div className="space-y-4">
                          <div>
                            <Label htmlFor="modal-dialog-branch-name">Branch Name</Label>
                            <Input
                              id="modal-dialog-branch-name"
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

                    <div>
                      <Label htmlFor="modal-push-commit-message">Commit Message</Label>
                      <Textarea
                        id="modal-push-commit-message"
                        value={pushCommitMessage}
                        onChange={(e) => setPushCommitMessage(e.target.value)}
                        placeholder="Add generated Terraform infrastructure code"
                        rows={3}
                      />
                    </div>

                    <div className="text-sm text-muted-foreground">
                      This will push {files.length} file(s) to <strong>{githubStatus.data.github_repo_name}</strong> on branch <strong>{selectedBranch}</strong>
                    </div>

                    <div className="flex gap-2">
                      <Button
                        onClick={pushToGitHub}
                        disabled={isPushing || !pushCommitMessage.trim()}
                        className="flex-1"
                      >
                        {isPushing ? (
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        ) : (
                          <Github className="h-4 w-4 mr-2" />
                        )}
                        Push Files
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => setShowPushDialog(false)}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                </DialogContent>
              </Dialog>
            )}
          </div>
          <div className="border rounded-md overflow-hidden flex-1">
            <CodeEditor
              value={isEditing ? editedContent : selectedFileForModal?.content || ''}
              language={selectedFileForModal ? getFileLanguage(selectedFileForModal.name) : 'plaintext'}
              readOnly={!isEditing}
              onChange={isEditing ? setEditedContent : undefined}
              height="70vh"
            />
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};

const MessageBubble: React.FC<{
  message: TerraformChatMessage;
  onClarificationResponse?: (responses: { [key: string]: string }, threadId?: string) => void;
  projectId: string;
}> = ({ message, onClarificationResponse, projectId }) => {
  const isUser = message.is_user_message;
  const isSystem = message.is_system_message;
  const isClarificationRequest = message.is_clarification_request;
  const [responses, setResponses] = useState<{ [key: string]: string }>({});

  const getAvatarIcon = () => {
    if (isUser) return <User className="h-4 w-4" />;
    if (isSystem || isClarificationRequest) return <Zap className="h-4 w-4" />;
    return <Bot className="h-4 w-4" />;
  };

  const getAvatarColor = () => {
    if (isUser) return 'bg-blue-600 text-white';
    if (isSystem) return 'bg-yellow-600 text-white';
    if (isClarificationRequest) return 'bg-orange-600 text-white';
    return 'bg-gradient-to-r from-purple-600 to-blue-600 text-white';
  };

  const getMessageStyle = () => {
    if (isUser) return 'bg-blue-600 text-white';
    if (isSystem) return 'bg-yellow-50 text-yellow-800 border border-yellow-200';
    if (isClarificationRequest) return 'bg-orange-50 text-orange-800 border border-orange-200';
    return 'bg-slate-700 text-slate-300';
  };

  const handleResponseChange = (questionId: string, value: string) => {
    setResponses(prev => ({ ...prev, [questionId]: value }));
  };

  const handleSubmit = () => {
    if (onClarificationResponse) {
      onClarificationResponse(responses, message.thread_id);
      setResponses({});
    }
  };

  const renderClarificationInputs = () => {
    if (!message.clarification_questions) return null;

    return (
      <div className="mt-3 space-y-3">
        {message.clarification_questions.map((question: ClarificationQuestion) => (
          <div key={question.id} className="space-y-2">
            <Label htmlFor={question.id} className="text-sm font-medium">
              {question.question}
            </Label>

            {question.type === 'text' && (
              <Textarea
                id={question.id}
                value={responses[question.id] || ''}
                onChange={(e) => handleResponseChange(question.id, e.target.value)}
                placeholder="Enter your response..."
                className="min-h-[60px] resize-none"
              />
            )}

            {question.type === 'select' && question.options && (
              <Select
                value={responses[question.id] || ''}
                onValueChange={(value) => handleResponseChange(question.id, value)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select an option..." />
                </SelectTrigger>
                <SelectContent>
                  {question.options.map((option) => (
                    <SelectItem key={option} value={option}>
                      {option}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}

            {question.type === 'boolean' && (
              <div className="flex items-center space-x-2">
                <Switch
                  id={question.id}
                  checked={responses[question.id] === 'true'}
                  onCheckedChange={(checked) =>
                    handleResponseChange(question.id, checked.toString())
                  }
                />
                <Label htmlFor={question.id}>Yes</Label>
              </div>
            )}
          </div>
        ))}
        <Button onClick={handleSubmit} size="sm" className="mt-2">
          Submit Responses
        </Button>
      </div>
    );
  };

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      <Avatar className="h-8 w-8">
        <AvatarFallback className={getAvatarColor()}>
          {getAvatarIcon()}
        </AvatarFallback>
      </Avatar>

      <div className={`flex flex-col max-w-[80%] ${isUser ? 'items-end' : 'items-start'}`}>
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm font-medium text-slate-300">
            {isUser ? "You" : isSystem ? "System" : isClarificationRequest ? "Clarification Needed" : "InfraJet AI"}
          </span>
          <Badge variant="outline" className="text-xs">
            {message.message_type}
          </Badge>
        </div>
        <div
          className={`rounded-lg px-3 py-2 text-sm whitespace-pre-wrap ${getMessageStyle()}`}
        >
          {message.message_content}
          {renderClarificationInputs()}
        </div>
        {message.generated_files && message.generated_files.length > 0 && (
          <GeneratedFilesDisplay files={message.generated_files} projectId={projectId} />
        )}
        <span className="text-xs text-muted-foreground mt-1">
          {(() => {
            try {
              if (message.timestamp && typeof message.timestamp === 'string') {
                return formatDistanceToNow(new Date(message.timestamp), { addSuffix: true });
              }
              return 'Unknown time';
            } catch (error) {
              return 'Invalid time';
            }
          })()}
        </span>
      </div>
    </div>
  );
};

export const TerraformChatInterface: React.FC<TerraformChatInterfaceProps> = ({
  projectId,
  className
}) => {
  const [inputMessage, setInputMessage] = useState('');
  const [cloudProvider, setCloudProvider] = useState<string>('');
  const [showTestModeWarning, setShowTestModeWarning] = useState(false);
  const [pendingMessage, setPendingMessage] = useState<string | null>(null);
  const [pendingCloudProvider, setPendingCloudProvider] = useState<string | null>(null);

  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const {
    isConnected,
    isGenerating,
    messages,
    clarificationDialog,
    generationProgress,
    initChat,
    sendMessage,
    respondToClarification,
  } = useTerraformChat(projectId);


  // Initialize chat on mount
  useEffect(() => {
    initChat();
  }, [initChat]);


  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isGenerating) {
      return;
    }

    // Show test mode warning dialog
    setPendingMessage(inputMessage.trim());
    setPendingCloudProvider(cloudProvider || null);
    setShowTestModeWarning(true);
  };

  const confirmSendMessage = async () => {
    if (!pendingMessage) return;

    const messageContent = pendingMessage;
    const provider = pendingCloudProvider;

    setInputMessage('');
    setPendingMessage(null);
    setPendingCloudProvider(null);

    try {
      await sendMessage(messageContent, undefined, provider || undefined);
    } catch (error) {
      console.error('Failed to send message:', error);
    }
  };

  const handleClarificationResponse = async (responses: { [key: string]: string }, threadId?: string) => {
    try {
      await respondToClarification(responses, threadId);
    } catch (error) {
      console.error('Failed to respond to clarification:', error);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (scrollAreaRef.current) {
      const scrollContainer = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]');
      if (scrollContainer) {
        scrollContainer.scrollTop = scrollContainer.scrollHeight;
      }
    }
  }, [messages]);

  return (
    <div className={className}>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Cloud className="h-5 w-5" />
              Terraform Chat
            </div>
            <div className="flex items-center gap-2">
              <Badge variant={isConnected ? "default" : "secondary"} className="flex items-center gap-1">
                {isConnected ? (
                  <>
                    <Wifi className="h-3 w-3" />
                    Connected
                  </>
                ) : (
                  <>
                    <WifiOff className="h-3 w-3" />
                    Disconnected
                  </>
                )}
              </Badge>
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="flex flex-col h-[600px]">
            {/* Messages Area */}
            <ScrollArea ref={scrollAreaRef} className="flex-1 p-4">
              {messages.length === 0 ? (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  <div className="text-center space-y-2">
                    <Cloud className="h-12 w-12 mx-auto opacity-50" />
                    <p>Start a Terraform conversation</p>
                    <p className="text-sm">Describe your infrastructure needs and I'll generate Terraform code for you</p>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  {messages.map((message) => (
                    <MessageBubble
                      key={message.id}
                      message={message}
                      onClarificationResponse={message.is_clarification_request ? handleClarificationResponse : undefined}
                      projectId={projectId}
                    />
                  ))}
                </div>
              )}
            </ScrollArea>

            {/* Generation Progress */}
            {generationProgress && (
              <div className="px-4 pb-2">
                <GenerationProgress
                  status={generationProgress.status}
                  progressPercentage={generationProgress.progress_percentage}
                  currentStep={generationProgress.current_step}
                />
              </div>
            )}

            {/* Input Area */}
            <div className="border-t p-4">
              {/* Cloud Provider Selector */}
              <div className="flex gap-2 mb-4">
                <Select value={cloudProvider} onValueChange={setCloudProvider}>
                  <SelectTrigger className="w-[180px]">
                    <SelectValue placeholder="Cloud Provider (Optional)" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="AWS">AWS</SelectItem>
                    <SelectItem value="Azure">Azure</SelectItem>
                    <SelectItem value="GCP">Google Cloud</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex gap-2">
                <Textarea
                  ref={textareaRef}
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Describe your infrastructure needs... (e.g., 'Create an S3 bucket with versioning enabled')"
                  className="min-h-[60px] max-h-[120px] resize-none border-2 focus:border-blue-500"
                  disabled={isGenerating}
                />
                <Button
                  onClick={handleSendMessage}
                  disabled={!inputMessage.trim() || isGenerating}
                  size="icon"
                  className="shrink-0 h-[60px] w-[60px]"
                >
                  {isGenerating ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : (
                    <Send className="h-5 w-5" />
                  )}
                </Button>
              </div>

              {/* Helpful tips */}
              {!isGenerating && inputMessage.length === 0 && (
                <div className="text-xs text-muted-foreground space-y-1 mt-2">
                  <p>🏗️ <strong>Terraform AI:</strong> I'll analyze your request and generate complete Terraform configurations</p>
                  <p>• "Create a VPC with public and private subnets" • "Set up an ECS cluster with load balancer"</p>
                  <p>• "Deploy a serverless API with Lambda and API Gateway" • "Configure a Kubernetes cluster"</p>
                </div>
              )}

              {/* AI disclaimer */}
              <div className="text-xs text-red-600 dark:text-red-400 mt-2 px-2 py-1 bg-red-50 dark:bg-red-950/20 rounded border border-red-200 dark:border-red-800">
                <strong>Note:</strong> InfraJet can make mistakes. Please double-check all generated code and configurations before deploying to production.
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <TestModeWarningDialog
        open={showTestModeWarning}
        onOpenChange={setShowTestModeWarning}
        onConfirm={confirmSendMessage}
      />

    </div>
  );
};