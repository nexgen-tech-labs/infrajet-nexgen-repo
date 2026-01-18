import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import {
    FileText,
    RefreshCw,
    Search,
    Filter,
    History,
    CheckCircle,
    XCircle,
    Clock,
    Code,
    Download,
    Eye,
    MoreHorizontal,
    Calendar,
    User,
    Zap,
    GitBranch,
    Github,
    Plus
} from 'lucide-react';
import { DialogTrigger } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { useToast } from '@/hooks/use-toast';
import { useProjectFiles } from '@/hooks/useProjectFiles';
import { usePushProjectToGitHub } from '@/hooks/useGitHubIntegration';
import { getAuthToken } from '@/services/infrajetApi';
import { formatDistanceToNow } from 'date-fns';
import CodeEditor from '@/components/CodeEditor';

interface ProjectFileManagerProps {
    projectId: string;
    className?: string;
}

const API_BASE_URL = window.__RUNTIME_CONFIG__?.INFRAJET_API_URL;

const ProjectFileManager: React.FC<ProjectFileManagerProps> = ({
    projectId,
    className
}) => {
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedGenerationId, setSelectedGenerationId] = useState<string | null>(null);
    const [showFilesDialog, setShowFilesDialog] = useState(false);
    const [pushDialogOpen, setPushDialogOpen] = useState(false);
    const [selectedBranch, setSelectedBranch] = useState<string>('main');
    const [pushCommitMessage, setPushCommitMessage] = useState<string>('Add generated infrastructure code');
    const [generationToPush, setGenerationToPush] = useState<string | null>(null);
    const [branches, setBranches] = useState<{ name: string; sha: string; protected: boolean }[]>([]);
    const [createNewBranch, setCreateNewBranch] = useState(false);
    const [newBranchName, setNewBranchName] = useState<string>('');
    const [showCreateBranch, setShowCreateBranch] = useState(false);
    const [isCreatingBranch, setIsCreatingBranch] = useState(false);

    const { toast } = useToast();

    // Generations functionality
    const {
        generations,
        selectedGeneration,
        selectedFile,
        fileContent,
        loading: loadingGenerations,
        loadingFiles: loadingGenFiles,
        loadingContent: loadingGenContent,
        fetchGenerations,
        selectGeneration,
        selectFile: selectGenFile,
        downloadFile: downloadGenFile
    } = useProjectFiles(projectId);

    // GitHub push functionality
    const pushGenerationMutation = usePushProjectToGitHub(projectId);

    // Load generations on mount
    useEffect(() => {
        fetchGenerations();
    }, [fetchGenerations]);

    // Load branches
    const loadBranches = useCallback(async () => {
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
        }
    }, [projectId, selectedBranch]);

    useEffect(() => {
        loadBranches();
    }, [loadBranches]);

    // Filter generations based on search query
    const filteredGenerations = generations.filter(generation =>
        generation.generation_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        generation.status.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (generation.description && generation.description.toLowerCase().includes(searchQuery.toLowerCase()))
    );

    const getStatusIcon = (status: string) => {
        switch (status.toLowerCase()) {
            case 'completed':
                return <CheckCircle className="h-4 w-4 text-green-500" />;
            case 'failed':
                return <XCircle className="h-4 w-4 text-red-500" />;
            case 'in_progress':
                return <Clock className="h-4 w-4 text-yellow-500" />;
            default:
                return <Clock className="h-4 w-4 text-gray-500" />;
        }
    };

    const getStatusColor = (status: string) => {
        switch (status.toLowerCase()) {
            case 'completed':
                return 'bg-green-100 text-green-800 border-green-200';
            case 'failed':
                return 'bg-red-100 text-red-800 border-red-200';
            case 'in_progress':
                return 'bg-yellow-100 text-yellow-800 border-yellow-200';
            default:
                return 'bg-gray-100 text-gray-800 border-gray-200';
        }
    };

    const handleViewFiles = async (generationId: string) => {
        setSelectedGenerationId(generationId);
        setShowFilesDialog(true);

        // Find the generation and select it
        const generation = generations.find(g => g.generation_id === generationId);
        if (generation) {
            await selectGeneration(generation);
        } else {
            // If not found, fetch all generations
            await fetchGenerations();
            const gen = generations.find(g => g.generation_id === generationId);
            if (gen) {
                await selectGeneration(gen);
            }
        }
    };

    const handlePushToGitHub = (generationId: string) => {
        setGenerationToPush(generationId);
        setPushDialogOpen(true);
    };

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

    const pushToGitHub = async () => {
        if (!generationToPush) return;

        try {
            await pushGenerationMutation.mutateAsync({
                generation_id: generationToPush,
                commit_message: pushCommitMessage
            });
            toast({
                title: "Success",
                description: "Generation pushed to GitHub successfully!",
            });
            setPushDialogOpen(false);
            setGenerationToPush(null);
        } catch (error) {
            toast({
                title: "Error",
                description: "Failed to push generation to GitHub",
                variant: "destructive",
            });
        }
    };

    return (
        <div className={`space-y-6 ${className}`}>
            {/* Enhanced Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-slate-800">Generated Files</h2>
                    <p className="text-slate-600 mt-1">View and manage your infrastructure code generations</p>
                </div>
                <div className="flex items-center gap-3">
                    <Badge variant="outline" className="text-sm px-3 py-1">
                        {generations.length} generations
                    </Badge>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={fetchGenerations}
                        disabled={loadingGenerations}
                        className="bg-white hover:bg-slate-50"
                    >
                        <RefreshCw className={`h-4 w-4 mr-2 ${loadingGenerations ? 'animate-spin' : ''}`} />
                        Refresh
                    </Button>
                </div>
            </div>

            {/* Search and Filter */}
            <Card>
                <CardContent className="pt-6">
                    <div className="flex items-center gap-4">
                        <div className="relative flex-1">
                            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-slate-400" />
                            <Input
                                placeholder="Search generations..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="pl-10 bg-white border-slate-200 focus:border-blue-300"
                            />
                        </div>
                        <Button variant="outline" size="sm">
                            <Filter className="h-4 w-4 mr-2" />
                            Filter
                        </Button>
                    </div>
                </CardContent>
            </Card>

            {/* Generations List */}
            <div className="space-y-4">
                {loadingGenerations ? (
                    Array.from({ length: 3 }).map((_, i) => (
                        <Card key={i}>
                            <CardContent className="pt-6">
                                <div className="flex items-center gap-4">
                                    <Skeleton className="h-12 w-12 rounded-lg" />
                                    <div className="flex-1 space-y-2">
                                        <Skeleton className="h-4 w-1/3" />
                                        <Skeleton className="h-3 w-1/2" />
                                    </div>
                                    <Skeleton className="h-8 w-20" />
                                </div>
                            </CardContent>
                        </Card>
                    ))
                ) : filteredGenerations.length === 0 ? (
                    <Card>
                        <CardContent className="pt-12 pb-12">
                            <div className="text-center space-y-4">
                                <div className="p-4 bg-slate-100 rounded-full w-16 h-16 mx-auto flex items-center justify-center">
                                    <Code className="h-8 w-8 text-slate-400" />
                                </div>
                                <div>
                                    <h3 className="text-lg font-semibold text-slate-700 mb-2">No generations found</h3>
                                    <p className="text-slate-500 max-w-md mx-auto">
                                        {searchQuery
                                            ? 'No generations match your search criteria. Try adjusting your search terms.'
                                            : 'Start a conversation in Terraform Chat to generate infrastructure code.'
                                        }
                                    </p>
                                </div>
                                {!searchQuery && (
                                    <Button
                                        variant="outline"
                                        className="mt-4"
                                        onClick={() => window.location.hash = '#terraform-chat'}
                                    >
                                        <Zap className="h-4 w-4 mr-2" />
                                        Start Terraform Chat
                                    </Button>
                                )}
                            </div>
                        </CardContent>
                    </Card>
                ) : (
                    filteredGenerations.map((generation) => (
                        <Card key={generation.generation_id} className="hover:shadow-md transition-shadow">
                            <CardContent className="pt-6">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-4 flex-1">
                                        <div className="p-3 bg-blue-100 rounded-lg">
                                            <History className="h-6 w-6 text-blue-600" />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-3 mb-2">
                                                <h3 className="font-semibold text-slate-800 truncate">
                                                    Generation {generation.generation_id.substring(0, 8)}
                                                </h3>
                                                <Badge
                                                    variant="outline"
                                                    className={`text-xs px-2 py-1 ${getStatusColor(generation.status)}`}
                                                >
                                                    <div className="flex items-center gap-1">
                                                        {getStatusIcon(generation.status)}
                                                        {generation.status}
                                                    </div>
                                                </Badge>
                                            </div>
                                            <div className="flex items-center gap-4 text-sm text-slate-500">
                                                <div className="flex items-center gap-1">
                                                    <Calendar className="h-3 w-3" />
                                                    {formatDistanceToNow(new Date(generation.created_at), { addSuffix: true })}
                                                </div>
                                                {generation.files && (
                                                    <div className="flex items-center gap-1">
                                                        <FileText className="h-3 w-3" />
                                                        {generation.files.length} files
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        {generation.files && generation.files.length > 0 && (
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={() => handleViewFiles(generation.generation_id)}
                                                className="bg-white hover:bg-blue-50 border-blue-200 text-blue-700"
                                            >
                                                <Eye className="h-4 w-4 mr-2" />
                                                View Files
                                            </Button>
                                        )}
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => handlePushToGitHub(generation.generation_id)}
                                            disabled={pushGenerationMutation.isPending}
                                            className="bg-white hover:bg-green-50 border-green-200 text-green-700"
                                        >
                                            <Download className="h-4 w-4 mr-2" />
                                            Push to GitHub
                                        </Button>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    ))
                )}
            </div>

            {/* Files Dialog */}
            <Dialog open={showFilesDialog} onOpenChange={setShowFilesDialog}>
                <DialogContent className="max-w-[95vw] max-h-[95vh] w-full h-full">
                    <DialogHeader className="pb-6 border-b">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-blue-100 rounded-lg">
                                    <FileText className="h-5 w-5 text-blue-600" />
                                </div>
                                <div>
                                    <DialogTitle className="text-xl font-semibold text-slate-800">
                                        Generated Files
                                    </DialogTitle>
                                    <DialogDescription className="text-sm text-slate-600 mt-1">
                                        View, edit, and download the infrastructure files generated for this conversation
                                    </DialogDescription>
                                </div>
                            </div>
                            <div className="flex items-center gap-2">
                                <Badge variant="outline" className="text-sm px-3 py-1">
                                    {selectedGeneration?.files?.length || 0} files
                                </Badge>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => setShowFilesDialog(false)}
                                    className="text-slate-600 hover:text-slate-800"
                                >
                                    Close
                                </Button>
                            </div>
                        </div>
                    </DialogHeader>

                    <div className="flex gap-6 h-[calc(95vh-120px)]">
                        {/* Files List */}
                        <div className="w-80 border-r border-slate-200 pr-6 flex flex-col">
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="font-semibold text-slate-800 text-lg">File Explorer</h3>
                            </div>

                            <div className="flex-1 overflow-y-auto">
                                {loadingGenFiles ? (
                                    <div className="flex items-center justify-center p-8">
                                        <div className="text-center space-y-3">
                                            <RefreshCw className="h-8 w-8 animate-spin text-blue-500 mx-auto" />
                                            <p className="text-sm text-slate-500">Loading files...</p>
                                        </div>
                                    </div>
                                ) : selectedGeneration?.files ? (
                                    <div className="space-y-1">
                                        {selectedGeneration.files.map((file, index) => {
                                            const fileExtension = file.name.split('.').pop()?.toLowerCase();
                                            const getFileIcon = () => {
                                                switch (fileExtension) {
                                                    case 'tf':
                                                    case 'tfvars':
                                                        return '🏗️';
                                                    case 'json':
                                                        return '📄';
                                                    case 'yaml':
                                                    case 'yml':
                                                        return '⚙️';
                                                    case 'md':
                                                        return '📝';
                                                    case 'sh':
                                                    case 'bash':
                                                        return '🔧';
                                                    default:
                                                        return '📄';
                                                }
                                            };

                                            return (
                                                <div
                                                    key={file.path}
                                                    onClick={() => selectGenFile(file)}
                                                    className={`p-3 rounded-xl border text-sm transition-all duration-200 cursor-pointer group ${selectedFile?.path === file.path
                                                            ? 'bg-blue-50 border-blue-200 shadow-sm ring-1 ring-blue-100'
                                                            : 'hover:bg-slate-50 hover:shadow-sm border-slate-200 hover:border-slate-300'
                                                        }`}
                                                >
                                                    <div className="flex items-center justify-between">
                                                        <div className="flex items-center gap-3 min-w-0 flex-1">
                                                            <div className="text-lg">{getFileIcon()}</div>
                                                            <div className="min-w-0 flex-1">
                                                                <p className="font-medium text-slate-800 truncate">{file.name}</p>
                                                                <div className="flex items-center gap-2 mt-1">
                                                                    <Badge variant="secondary" className="text-xs px-1.5 py-0.5">
                                                                        {fileExtension?.toUpperCase() || 'FILE'}
                                                                    </Badge>
                                                                    <span className="text-xs text-slate-500">
                                                                        {(file.size / 1024).toFixed(1)} KB
                                                                    </span>
                                                                </div>
                                                            </div>
                                                        </div>
                                                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                                            <Button
                                                                size="sm"
                                                                variant="ghost"
                                                                className="h-7 w-7 p-0 text-slate-500 hover:text-blue-600"
                                                                onClick={(e) => {
                                                                    e.stopPropagation();
                                                                    if (selectedGeneration) {
                                                                        downloadGenFile(selectedGeneration.generation_id, file.path);
                                                                    }
                                                                }}
                                                            >
                                                                <Download className="h-3.5 w-3.5" />
                                                            </Button>
                                                        </div>
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                ) : (
                                    <div className="text-center p-8 text-slate-500">
                                        <div className="p-4 bg-slate-100 rounded-full w-16 h-16 mx-auto mb-4 flex items-center justify-center">
                                            <FileText className="h-8 w-8 text-slate-400" />
                                        </div>
                                        <p className="text-sm font-medium mb-1">No files available</p>
                                        <p className="text-xs">Files will appear here after generation</p>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Code Editor */}
                        <div className="flex-1 min-w-0 flex flex-col">
                            {selectedFile ? (
                                <>
                                    {/* File Header */}
                                    <div className="flex items-center justify-between mb-4 p-4 bg-gradient-to-r from-slate-50 to-blue-50 rounded-xl border border-slate-200">
                                        <div className="flex items-center gap-4">
                                            <div className="p-3 bg-white rounded-lg shadow-sm border border-slate-200">
                                                <FileText className="h-6 w-6 text-blue-600" />
                                            </div>
                                            <div>
                                                <h3 className="font-semibold text-slate-800 text-lg">{selectedFile.name}</h3>
                                                <div className="flex items-center gap-3 mt-1">
                                                    <Badge variant="outline" className="text-sm px-2 py-1">
                                                        {selectedFile.name.split('.').pop()?.toUpperCase() || 'TEXT'}
                                                    </Badge>
                                                    <span className="text-sm text-slate-500">
                                                        {(selectedFile.size / 1024).toFixed(1)} KB
                                                    </span>
                                                    <span className="text-sm text-slate-500">
                                                        {selectedFile.path}
                                                    </span>
                                                </div>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <Button
                                                size="sm"
                                                variant="outline"
                                                onClick={() => {
                                                    if (selectedGeneration) {
                                                        downloadGenFile(selectedGeneration.generation_id, selectedFile.path);
                                                    }
                                                }}
                                                className="bg-white hover:bg-slate-50 border-slate-300"
                                            >
                                                <Download className="h-4 w-4 mr-2" />
                                                Download
                                            </Button>
                                        </div>
                                    </div>

                                    {/* Code Editor */}
                                    <div className="flex-1 min-h-0 border border-slate-200 rounded-xl overflow-hidden">
                                        {loadingGenContent ? (
                                            <div className="flex items-center justify-center h-full bg-slate-50">
                                                <div className="text-center space-y-4">
                                                    <RefreshCw className="h-8 w-8 animate-spin text-blue-500 mx-auto" />
                                                    <div>
                                                        <p className="text-sm font-medium text-slate-700">Loading file content...</p>
                                                        <p className="text-xs text-slate-500 mt-1">Please wait while we fetch the file</p>
                                                    </div>
                                                </div>
                                            </div>
                                        ) : (
                                            <div className="h-full">
                                                <CodeEditor
                                                    value={fileContent}
                                                    language={selectedFile.name.split('.').pop() || 'plaintext'}
                                                    height="100%"
                                                    readOnly={false}
                                                />
                                            </div>
                                        )}
                                    </div>
                                </>
                            ) : (
                                <div className="flex items-center justify-center h-full bg-gradient-to-br from-slate-50 to-blue-50 rounded-xl border-2 border-dashed border-slate-300">
                                    <div className="text-center space-y-6">
                                        <div className="p-6 bg-white rounded-full w-20 h-20 mx-auto flex items-center justify-center shadow-lg">
                                            <FileText className="h-10 w-10 text-slate-400" />
                                        </div>
                                        <div>
                                            <h3 className="text-xl font-semibold text-slate-700 mb-2">Select a file to view</h3>
                                            <p className="text-slate-500 max-w-md">
                                                Choose a file from the explorer on the left to view and edit its contents.
                                                You can also download individual files or edit them directly.
                                            </p>
                                        </div>
                                        <div className="flex items-center justify-center gap-4 text-sm text-slate-500">
                                            <div className="flex items-center gap-2">
                                                <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                                                <span>Syntax highlighting</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                                                <span>Live editing</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <div className="w-2 h-2 bg-purple-500 rounded-full"></div>
                                                <span>Download support</span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </DialogContent>
            </Dialog>

            {/* Push to GitHub Dialog */}
            <Dialog open={pushDialogOpen} onOpenChange={setPushDialogOpen}>
                <DialogContent className="max-w-md">
                    <DialogHeader>
                        <DialogTitle>Push Files to GitHub</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4">
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
                                                placeholder="feature/generated-infrastructure"
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
                                                    <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
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
                            <Label htmlFor="push-commit-message" className="text-sm font-medium">Commit Message</Label>
                            <Textarea
                                id="push-commit-message"
                                value={pushCommitMessage}
                                onChange={(e) => setPushCommitMessage(e.target.value)}
                                placeholder="Add generated infrastructure code"
                                rows={3}
                            />
                        </div>

                        <div className="flex gap-2">
                            <Button
                                onClick={pushToGitHub}
                                disabled={pushGenerationMutation.isPending || !pushCommitMessage.trim()}
                                className="flex-1"
                            >
                                {pushGenerationMutation.isPending ? (
                                    <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                                ) : (
                                    <Github className="h-4 w-4 mr-2" />
                                )}
                                Push to {selectedBranch}
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
        </div>
    );
};

export default ProjectFileManager;
