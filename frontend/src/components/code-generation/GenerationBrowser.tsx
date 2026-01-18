import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
    FileText,
    Download,
    Eye,
    Loader2,
    CheckCircle,
    XCircle,
    Clock,
    Archive,
    Github,
    GitBranch,
    Plus
} from 'lucide-react';
import { InfraJetChat, JobResult, githubApi, getAuthToken } from '@/services/infrajetApi';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/hooks/use-toast';
import { useProjectGitHubStatus } from '@/hooks/useGitHubIntegration';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import JSZip from 'jszip';

interface GenerationBrowserProps {
    projectId: string;
    className?: string;
}

interface Generation {
    generation_id: string;
    query: string;
    scenario: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    created_at: string;
    updated_at: string;
    generation_hash: string;
    error_message: string | null;
    files: any[];
    file_count: number;
    description?: string;
    summary?: string;
    generated_files?: Record<string, string>;
}

const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
    const getStatusConfig = (status: string) => {
        switch (status) {
            case 'pending':
                return { variant: 'secondary' as const, icon: Clock, label: 'Pending' };
            case 'running':
                return { variant: 'default' as const, icon: Loader2, label: 'Running' };
            case 'completed':
                return { variant: 'default' as const, icon: CheckCircle, label: 'Completed' };
            case 'failed':
                return { variant: 'destructive' as const, icon: XCircle, label: 'Failed' };
            default:
                return { variant: 'secondary' as const, icon: Clock, label: status };
        }
    };

    const config = getStatusConfig(status);
    const Icon = config.icon;

    return (
        <Badge variant={config.variant} className="flex items-center gap-1">
            <Icon className={`h-3 w-3 ${status === 'running' ? 'animate-spin' : ''}`} />
            {config.label}
        </Badge>
    );
};

const FileViewerModal: React.FC<{
    isOpen: boolean;
    onClose: () => void;
    files: Record<string, string>;
    generationId: string;
    onDownloadFile: (fileName: string, content: string) => void;
    onDownloadAll: () => void;
}> = ({ isOpen, onClose, files, generationId, onDownloadFile, onDownloadAll }) => {
    const [selectedFile, setSelectedFile] = useState<string>(Object.keys(files)[0] || '');

    const getLanguage = (filename: string) => {
        const ext = filename.split('.').pop()?.toLowerCase();
        switch (ext) {
            case 'tf': return 'hcl';
            case 'json': return 'json';
            case 'yaml':
            case 'yml': return 'yaml';
            case 'py': return 'python';
            case 'js': return 'javascript';
            case 'ts': return 'typescript';
            case 'sh': return 'bash';
            default: return 'text';
        }
    };

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent className="max-w-6xl max-h-[80vh] overflow-hidden">
                <DialogHeader>
                    <DialogTitle className="flex items-center justify-between">
                        <span>Generation Files - {generationId}</span>
                        <div className="flex gap-2">
                            <Button
                                size="sm"
                                variant="outline"
                                onClick={onDownloadAll}
                                className="flex items-center gap-2"
                            >
                                <Archive className="h-4 w-4" />
                                Download All
                            </Button>
                        </div>
                    </DialogTitle>
                </DialogHeader>
                <div className="flex flex-col h-full">
                    <Tabs value={selectedFile} onValueChange={setSelectedFile} className="flex-1 flex flex-col">
                        <TabsList className="flex w-full overflow-x-auto mb-4">
                            {Object.keys(files).map((filename) => (
                                <TabsTrigger key={filename} value={filename} className="text-xs flex-shrink-0">
                                    {filename}
                                </TabsTrigger>
                            ))}
                        </TabsList>
                        <div className="flex-1 overflow-hidden">
                            {Object.entries(files).map(([filename, content]) => (
                                <TabsContent key={filename} value={filename} className="h-full">
                                    <div className="relative h-full">
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            className="absolute top-2 right-2 z-10"
                                            onClick={() => onDownloadFile(filename, content)}
                                        >
                                            <Download className="h-3 w-3" />
                                        </Button>
                                        <SyntaxHighlighter
                                            language={getLanguage(filename)}
                                            style={oneDark}
                                            className="h-full !bg-muted rounded-lg"
                                            showLineNumbers
                                            wrapLines
                                            customStyle={{
                                                margin: 0,
                                                height: '100%',
                                                fontSize: '14px'
                                            }}
                                        >
                                            {content}
                                        </SyntaxHighlighter>
                                    </div>
                                </TabsContent>
                            ))}
                        </div>
                    </Tabs>
                </div>
            </DialogContent>
        </Dialog>
    );
};

export const GenerationBrowser: React.FC<GenerationBrowserProps> = ({
    projectId,
    className
}) => {
    const [generations, setGenerations] = useState<Generation[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedGeneration, setSelectedGeneration] = useState<Generation | null>(null);
    const [modalOpen, setModalOpen] = useState(false);
    const [pushDialogOpen, setPushDialogOpen] = useState(false);
    const [selectedBranch, setSelectedBranch] = useState<string>('main');
    const [pushCommitMessage, setPushCommitMessage] = useState<string>('Add generated infrastructure code');
    const [isPushing, setIsPushing] = useState(false);
    const [branches, setBranches] = useState<{ name: string; sha: string; protected: boolean }[]>([]);
    const { toast } = useToast();
    const { data: githubStatus } = useProjectGitHubStatus(projectId);

    const chat = useMemo(() => {
        // We'll initialize this properly in the fetchGenerations function
        return null as any;
    }, []);

    const fetchGenerations = useCallback(async () => {
        try {
            setLoading(true);
            const token = await getAuthToken();
            const chatInstance = new InfraJetChat(projectId, token);
            const response = await chatInstance.getGenerations();
            // Add created_at - in real implementation, this would come from API
            const generationsWithDate = response.generations.map(gen => ({
                ...gen,
                created_at: new Date().toISOString()
            }));
            setGenerations(generationsWithDate);
        } catch (error) {
            toast({
                title: "Error",
                description: "Failed to load generations",
                variant: "destructive",
            });
        } finally {
            setLoading(false);
        }
    }, [projectId, toast]);

    useEffect(() => {
        fetchGenerations();
    }, [fetchGenerations]);

    const handleViewFiles = (generation: Generation) => {
        setSelectedGeneration(generation);
        setModalOpen(true);
    };

    const downloadFile = (fileName: string, content: string) => {
        const blob = new Blob([content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = fileName;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    const downloadAllFiles = async () => {
        if (!selectedGeneration?.generated_files) return;

        try {
            const zip = new JSZip();
            Object.entries(selectedGeneration.generated_files).forEach(([filename, content]) => {
                zip.file(filename, content);
            });

            const content = await zip.generateAsync({ type: 'blob' });
            const url = URL.createObjectURL(content);
            const a = document.createElement('a');
            a.href = url;
            a.download = `generation-${selectedGeneration.generation_id}.zip`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            toast({
                title: "Download Started",
                description: "Bulk download has been initiated",
            });
        } catch (error) {
            toast({
                title: "Download Failed",
                description: "Failed to create bulk download",
                variant: "destructive",
            });
        }
    };

    const loadBranches = useCallback(async () => {
        if (!githubStatus?.data?.github_linked || !projectId) return;

        try {
            const response = await fetch(`${window.__RUNTIME_CONFIG__?.INFRAJET_API_URL}/api/v1/github/projects/${projectId}/branches`, {
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
        }
    }, [githubStatus?.data?.github_linked, projectId, selectedBranch]);

    useEffect(() => {
        if (githubStatus?.data?.github_linked) {
            loadBranches();
        }
    }, [githubStatus?.data?.github_linked, loadBranches]);

    const pushToGitHub = async () => {
        if (!selectedGeneration?.generated_files || !githubStatus?.data?.github_linked) {
            toast({
                title: "Error",
                description: "No files to push or GitHub not linked",
                variant: "destructive",
            });
            return;
        }

        setIsPushing(true);
        try {
            const repoParts = githubStatus.data.github_repo_name.split('/');
            const repoOwner = repoParts[0];
            const repoName = repoParts[1];

            await githubApi.syncFiles(repoOwner, repoName, {
                files_content: selectedGeneration.generated_files,
                commit_message: pushCommitMessage,
                branch: selectedBranch
            });

            toast({
                title: "Files pushed to GitHub",
                description: `Successfully pushed ${Object.keys(selectedGeneration.generated_files).length} files to ${githubStatus.data.github_repo_name} on branch ${selectedBranch}`,
            });

            setPushDialogOpen(false);
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

    const handlePushToGitHub = (generation: Generation) => {
        setSelectedGeneration(generation);
        setPushDialogOpen(true);
    };

    if (loading) {
        return (
            <Card className={className}>
                <CardContent className="flex items-center justify-center py-8">
                    <Loader2 className="h-8 w-8 animate-spin" />
                    <span className="ml-2">Loading generations...</span>
                </CardContent>
            </Card>
        );
    }

    return (
        <>
            <Card className={className}>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <FileText className="h-5 w-5" />
                        Code Generations1
                    </CardTitle>
                    <CardDescription>
                        Browse and download your generated infrastructure code
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {generations.length === 0 ? (
                        <div className="text-center py-8 text-muted-foreground">
                            No generations found for this project.
                        </div>
                    ) : (
                        <div className="space-y-4">
                            {generations.map((generation) => (
                                <Card key={generation.generation_id} className="p-4">
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-4">
                                            <StatusBadge status={generation.status} />
                                            <div>
                                                <p className="font-medium">Job {generation.generation_id}</p>
                                                <p className="text-sm text-muted-foreground">
                                                    {generation.generated_files ? Object.keys(generation.generated_files).length : 0} files •
                                                    Created {new Date(generation.created_at).toLocaleDateString()}
                                                </p>
                                            </div>
                                        </div>
                                        <div className="flex gap-2">
                                            <Button
                                                size="sm"
                                                variant="outline"
                                                onClick={() => handleViewFiles(generation)}
                                                disabled={!generation.generated_files || Object.keys(generation.generated_files).length === 0}
                                            >
                                                <Eye className="h-4 w-4 mr-2" />
                                                View Files
                                            </Button>
                                            {generation.generated_files && Object.keys(generation.generated_files).length > 0 && (
                                                <>
                                                    <Button
                                                        size="sm"
                                                        variant="outline"
                                                        onClick={() => handlePushToGitHub(generation)}
                                                        disabled={!githubStatus?.data?.github_linked}
                                                    >
                                                        <Github className="h-4 w-4 mr-2" />
                                                        Push to GitHub
                                                    </Button>
                                                    <Button
                                                        size="sm"
                                                        variant="outline"
                                                        onClick={downloadAllFiles}
                                                    >
                                                        <Download className="h-4 w-4 mr-2" />
                                                        Download All
                                                    </Button>
                                                </>
                                            )}
                                        </div>
                                    </div>
                                </Card>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            {selectedGeneration && (
                <FileViewerModal
                    isOpen={modalOpen}
                    onClose={() => setModalOpen(false)}
                    files={selectedGeneration.generated_files || {}}
                    generationId={selectedGeneration.generation_id}
                    onDownloadFile={downloadFile}
                    onDownloadAll={downloadAllFiles}
                />
            )}

            {/* Push to GitHub Dialog */}
            <Dialog open={pushDialogOpen} onOpenChange={setPushDialogOpen}>
                <DialogContent className="max-w-md">
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

                        <div>
                            <Label htmlFor="push-commit-message">Commit Message</Label>
                            <Textarea
                                id="push-commit-message"
                                value={pushCommitMessage}
                                onChange={(e) => setPushCommitMessage(e.target.value)}
                                placeholder="Add generated infrastructure code"
                                rows={3}
                            />
                        </div>

                        {selectedGeneration && (
                            <div className="text-sm text-muted-foreground">
                                This will push {Object.keys(selectedGeneration.generated_files || {}).length} file(s) to <strong>{githubStatus?.data?.github_repo_name}</strong> on branch <strong>{selectedBranch}</strong>
                            </div>
                        )}

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
                                onClick={() => setPushDialogOpen(false)}
                            >
                                Cancel
                            </Button>
                        </div>
                    </div>
                </DialogContent>
            </Dialog>
        </>
    );
};