import React, { useState, useRef, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Send, User, Bot, Loader2, Wifi, WifiOff, FileText, Code, Copy, Check, Square, Download, Eye } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import CodeEditor from '@/components/CodeEditor';
import { useInfraJetChat, useFileDownload } from '@/hooks/useInfraJetChat';
import { ChatMessage, GenerationFile } from '@/services/infrajetApi';
import { GenerationProgress } from './GenerationProgress';

interface SimpleChatInterfaceProps {
    projectId: string;
    className?: string;
}

const MessageBubble: React.FC<{
    message: ChatMessage;
    onFileView: (fileName: string, content: string) => void;
}> = ({ message, onFileView }) => {
    const isUser = message.message_type === 'user';
    const [copiedCode, setCopiedCode] = useState<string | null>(null);

    const handleCopyCode = async (code: string) => {
        await navigator.clipboard.writeText(code);
        setCopiedCode(code);
        setTimeout(() => setCopiedCode(null), 2000);
    };

    const renderMessageContent = (content: string) => {
        // Split content by code blocks and file references
        const parts = content.split(/(```[\s\S]*?```|@[\w/\-\.]+|\bfile:[\w/\-\.]+\b)/g);

        return parts.map((part, index) => {
            // Code block
            if (part.startsWith('```') && part.endsWith('```')) {
                const codeContent = part.slice(3, -3);
                const firstLineEnd = codeContent.indexOf('\n');
                const language = firstLineEnd > 0 ? codeContent.slice(0, firstLineEnd).trim() : '';
                const code = firstLineEnd > 0 ? codeContent.slice(firstLineEnd + 1) : codeContent;

                return (
                    <div key={index} className="relative my-2">
                        <div className="bg-slate-900 rounded-lg overflow-hidden">
                            <div className="flex items-center justify-between px-3 py-2 bg-slate-800">
                                <span className="text-xs text-slate-400">{language || 'text'}</span>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => handleCopyCode(code)}
                                    className="h-6 w-6 p-0 hover:bg-slate-700"
                                >
                                    {copiedCode === code ? (
                                        <Check className="w-3 h-3 text-green-400" />
                                    ) : (
                                        <Copy className="w-3 h-3 text-slate-400" />
                                    )}
                                </Button>
                            </div>
                            <SyntaxHighlighter
                                language={language || 'text'}
                                style={vscDarkPlus}
                                customStyle={{ margin: 0, background: 'transparent' }}
                                className="!bg-slate-900"
                            >
                                {code}
                            </SyntaxHighlighter>
                        </div>
                    </div>
                );
            }

            // File reference (@filename or file:filename)
            const fileMatch = part.match(/^(@|file:)[\w/\-\.]+$/);
            if (fileMatch) {
                const fileName = part.replace(/^(@|file:)/, '');
                return (
                    <Button
                        key={index}
                        variant="outline"
                        size="sm"
                        onClick={() => onFileView(fileName, `// File: ${fileName}\n// Content would be loaded from generation`)}
                        className="mx-1 h-6 text-xs bg-blue-50 hover:bg-blue-100 border-blue-200 text-blue-700"
                    >
                        <FileText className="w-3 h-3 mr-1" />
                        {fileName}
                    </Button>
                );
            }

            // Regular text
            return <span key={index}>{part}</span>;
        });
    };

    return (
        <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
            <Avatar className="h-8 w-8">
                <AvatarFallback className={isUser ? 'bg-blue-600 text-white' : 'bg-gradient-to-r from-purple-600 to-blue-600 text-white'}>
                    {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                </AvatarFallback>
            </Avatar>

            <div className={`flex flex-col max-w-[80%] ${isUser ? 'items-end' : 'items-start'}`}>
                <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium">
                        {isUser ? "You" : "infraJet"}
                    </span>
                </div>
                <div
                    className={`rounded-lg px-3 py-2 text-sm ${isUser
                        ? 'bg-blue-600 text-white'
                        : 'bg-muted text-muted-foreground'
                        }`}
                >
                    <div className="whitespace-pre-wrap">
                        {renderMessageContent(message.message_content)}
                    </div>
                </div>
                <span className="text-xs text-muted-foreground mt-1">
                    {formatDistanceToNow(new Date(message.timestamp), { addSuffix: true })}
                </span>
            </div>
        </div>
    );
};


const FilesModal: React.FC<{
    files: GenerationFile[];
    isOpen: boolean;
    onClose: () => void;
    onDownload: (files: GenerationFile[]) => void;
}> = ({ files, isOpen, onClose, onDownload }) => {
    const [selectedFile, setSelectedFile] = useState<GenerationFile | null>(files[0] || null);

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent className="max-w-6xl max-h-[90vh]">
                <DialogHeader>
                    <DialogTitle className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <FileText className="w-4 h-4" />
                            Generation Files ({files.length})
                        </div>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => onDownload(files)}
                        >
                            <Download className="w-4 h-4 mr-2" />
                            Download All
                        </Button>
                    </DialogTitle>
                </DialogHeader>
                <div className="flex h-[70vh] gap-4">
                    {/* File List */}
                    <div className="w-1/3 border-r pr-4">
                        <ScrollArea className="h-full">
                            <div className="space-y-2">
                                {files.map((file) => (
                                    <Button
                                        key={file.path}
                                        variant={selectedFile?.path === file.path ? "default" : "ghost"}
                                        size="sm"
                                        onClick={() => setSelectedFile(file)}
                                        className="w-full justify-start text-left"
                                    >
                                        <FileText className="w-4 h-4 mr-2" />
                                        <div className="flex-1 min-w-0">
                                            <div className="truncate">{file.name}</div>
                                            <div className="text-xs text-muted-foreground">
                                                {(file.size / 1024).toFixed(1)} KB
                                            </div>
                                        </div>
                                    </Button>
                                ))}
                            </div>
                        </ScrollArea>
                    </div>

                    {/* File Content */}
                    <div className="flex-1">
                        {selectedFile ? (
                            <div className="h-full">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-sm font-medium">{selectedFile.name}</span>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => navigator.clipboard.writeText(selectedFile.content || '')}
                                    >
                                        <Copy className="w-4 h-4" />
                                    </Button>
                                </div>
                                <CodeEditor
                                    value={selectedFile.content || '// Loading...'}
                                    language={selectedFile.name.split('.').pop() || 'text'}
                                    readOnly={true}
                                    height="calc(100% - 40px)"
                                />
                            </div>
                        ) : (
                            <div className="flex items-center justify-center h-full text-muted-foreground">
                                Select a file to view its content
                            </div>
                        )}
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    );
};

export const SimpleChatInterface: React.FC<SimpleChatInterfaceProps> = ({
    projectId,
    className
}) => {
    const [inputMessage, setInputMessage] = useState('');
    const [viewingFiles, setViewingFiles] = useState<GenerationFile[] | null>(null);
    const [viewingFile, setViewingFile] = useState<{ name: string; content: string } | null>(null);

    const scrollAreaRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const {
        messages,
        generations,
        isConnected,
        isLoading,
        isSending,
        generationStatus,
        sendMessage,
        getGenerationFiles,
    } = useInfraJetChat(projectId);

    const { downloadAsZip } = useFileDownload();

    const handleSendMessage = async () => {
        if (!inputMessage.trim() || isSending) return;

        const messageContent = inputMessage.trim();
        setInputMessage('');
        await sendMessage(messageContent, 'user');
    };

    const handleViewGenerationFiles = async (generationId: string) => {
        const files = await getGenerationFiles(generationId, true);
        setViewingFiles(files);
    };

    const handleDownloadFiles = async (files: GenerationFile[]) => {
        await downloadAsZip(files, `generation-files-${Date.now()}.zip`);
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
        <div className={`grid grid-cols-1 lg:grid-cols-3 gap-4 ${className}`}>
            {/* Chat Interface */}
            <Card className="lg:col-span-2">
                <CardHeader>
                    <CardTitle className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <Bot className="h-5 w-5" />
                            InfraJet Chat
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
                            {isLoading ? (
                                <div className="space-y-4">
                                    {Array.from({ length: 3 }).map((_, i) => (
                                        <div key={i} className={`flex gap-3 ${i % 2 === 0 ? 'flex-row-reverse' : 'flex-row'}`}>
                                            <Skeleton className="h-8 w-8 rounded-full" />
                                            <div className="flex flex-col max-w-[80%]">
                                                <Skeleton className="h-16 w-48 rounded-lg" />
                                                <Skeleton className="h-3 w-20 mt-1" />
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : messages.length === 0 ? (
                                <div className="flex items-center justify-center h-full text-muted-foreground">
                                    <div className="text-center space-y-2">
                                        <Bot className="h-12 w-12 mx-auto opacity-50" />
                                        <p>Start a conversation about your project</p>
                                        <p className="text-sm">Ask me to generate Terraform code, explain concepts, or help with infrastructure</p>
                                    </div>
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    {messages.map((message) => (
                                        <MessageBubble
                                            key={message.id}
                                            message={message}
                                            onFileView={(name, content) => setViewingFile({ name, content })}
                                        />
                                    ))}
                                    {generationStatus.isGenerating && (
                                        <div className="px-4">
                                            <GenerationProgress
                                                status={generationStatus.status || 'generating'}
                                                progressPercentage={generationStatus.progress || 0}
                                                currentStep={generationStatus.currentStep || generationStatus.message || 'Generating...'}
                                            />
                                        </div>
                                    )}
                                </div>
                            )}
                        </ScrollArea>

                        {/* Input Area */}
                        <div className="border-t p-4">
                            <div className="flex gap-2">
                                <Textarea
                                    ref={textareaRef}
                                    value={inputMessage}
                                    onChange={(e) => setInputMessage(e.target.value)}
                                    onKeyPress={handleKeyPress}
                                    placeholder="Ask me to generate Terraform code... (e.g., 'Create a VPC with public and private subnets')"
                                    className="min-h-[60px] max-h-[120px] resize-none"
                                    disabled={isSending || generationStatus.isGenerating}
                                />
                                <Button
                                    onClick={handleSendMessage}
                                    disabled={!inputMessage.trim() || isSending || generationStatus.isGenerating}
                                    size="icon"
                                    className="shrink-0 h-[60px] w-[60px]"
                                >
                                    {isSending ? (
                                        <Loader2 className="h-5 w-5 animate-spin" />
                                    ) : generationStatus.isGenerating ? (
                                        <Square className="h-5 w-5" />
                                    ) : (
                                        <Send className="h-5 w-5" />
                                    )}
                                </Button>
                            </div>

                            {/* Helpful tips */}
                            {!generationStatus.isGenerating && inputMessage.length === 0 && (
                                <div className="text-xs text-muted-foreground space-y-1 mt-2">
                                    <p>💡 <strong>Quick tips:</strong> Be specific about your infrastructure needs</p>
                                    <p>• "Create an S3 bucket with versioning" • "Set up ECS cluster with load balancer"</p>
                                </div>
                            )}
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Generation Browser */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Code className="h-5 w-5" />
                        Code Generations
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {generations.length === 0 ? (
                        <div className="text-center text-muted-foreground py-8">
                            <Code className="w-12 h-12 mx-auto mb-2 opacity-50" />
                            <p>No code generations yet</p>
                            <p className="text-sm">Start a conversation to generate infrastructure code</p>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {generations.map((generation) => (
                                <div key={generation.generation_id} className="border rounded-lg p-4">
                                    <div className="flex items-center justify-between mb-2">
                                        <h4 className="font-medium text-sm">{generation.query}</h4>
                                        <Badge variant={generation.status === 'completed' ? 'default' : generation.status === 'failed' ? 'destructive' : 'secondary'}>
                                            {generation.status}
                                        </Badge>
                                    </div>
                                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                                        <span>Files: {generation.file_count}</span>
                                        <span>Created: {formatDistanceToNow(new Date(generation.created_at), { addSuffix: true })}</span>
                                    </div>
                                    {generation.status === 'completed' && (
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => handleViewGenerationFiles(generation.generation_id)}
                                            className="mt-2 w-full"
                                        >
                                            <Eye className="w-4 h-4 mr-2" />
                                            View Files
                                        </Button>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Files Modal */}
            {viewingFiles && (
                <FilesModal
                    files={viewingFiles}
                    isOpen={true}
                    onClose={() => setViewingFiles(null)}
                    onDownload={handleDownloadFiles}
                />
            )}

            {/* File View Modal */}
            {viewingFile && (
                <Dialog open={true} onOpenChange={() => setViewingFile(null)}>
                    <DialogContent className="max-w-4xl max-h-[80vh]">
                        <DialogHeader>
                            <DialogTitle className="flex items-center gap-2">
                                <FileText className="w-4 h-4" />
                                {viewingFile.name}
                            </DialogTitle>
                        </DialogHeader>
                        <div className="h-[60vh]">
                            <CodeEditor
                                value={viewingFile.content}
                                language={viewingFile.name.split('.').pop() || 'text'}
                                readOnly={true}
                                height="100%"
                            />
                        </div>
                    </DialogContent>
                </Dialog>
            )}
        </div>
    );
};