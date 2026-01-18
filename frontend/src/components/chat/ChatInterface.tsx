import React, { useState, useRef, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Send, User, Bot, Loader2, Wifi, WifiOff, FileText, Code, Copy, Eye, Check, Paperclip } from 'lucide-react';
import { useChatState } from '@/hooks/useChat';
// import { useProjectWebSocket } from '@/hooks/useWebSocket'; // Removed - not implemented
import { ChatMessage } from '@/services/infrajetApi';
import { formatDistanceToNow } from 'date-fns';
import { useQueryClient } from '@tanstack/react-query';
import { chatKeys } from '@/hooks/useChat';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import CodeEditor from '@/components/CodeEditor';
import { sanitizeAndValidateChatMessage } from '@/lib/inputSanitizer';
import { useToast } from '@/hooks/use-toast';

interface ChatInterfaceProps {
    projectId: string;
    className?: string;
}

const MessageBubble: React.FC<{ message: ChatMessage; projectId: string }> = ({ message, projectId }) => {
    const isUser = message.message_type === 'user';
    const [copiedCode, setCopiedCode] = useState<string | null>(null);
    const [viewingFile, setViewingFile] = useState<string | null>(null);

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
                const fileExtension = fileName.split('.').pop()?.toLowerCase();
                
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
                    <Dialog key={index}>
                        <DialogTrigger asChild>
                            <Button
                                variant="outline"
                                size="sm"
                                className="mx-1 h-7 px-3 text-xs bg-gradient-to-r from-blue-50 to-indigo-50 hover:from-blue-100 hover:to-indigo-100 border-blue-200 text-blue-700 hover:border-blue-300 transition-all duration-200 shadow-sm"
                            >
                                <span className="mr-1">{getFileIcon()}</span>
                                <span className="font-medium">{fileName}</span>
                                <Badge variant="secondary" className="ml-2 text-xs px-1.5 py-0.5">
                                    {fileExtension?.toUpperCase() || 'FILE'}
                                </Badge>
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="max-w-6xl max-h-[90vh]">
                            <DialogHeader className="pb-4">
                                <DialogTitle className="flex items-center gap-3">
                                    <div className="p-2 bg-blue-100 rounded-lg">
                                        <FileText className="w-5 h-5 text-blue-600" />
                                    </div>
                                    <div>
                                        <span className="text-lg font-semibold">{fileName}</span>
                                        <Badge variant="outline" className="ml-2 text-xs">
                                            {fileExtension?.toUpperCase() || 'TEXT'}
                                        </Badge>
                                    </div>
                                </DialogTitle>
                            </DialogHeader>
                            <div className="h-[70vh] border border-slate-200 rounded-lg overflow-hidden">
                                <CodeEditor
                                    value={`// File: ${fileName}\n// Loading file content...`}
                                    language={fileName.split('.').pop() || 'text'}
                                    readOnly={true}
                                    height="100%"
                                />
                            </div>
                        </DialogContent>
                    </Dialog>
                );
            }

            // Regular text
            return <span key={index}>{part}</span>;
        });
    };

    return (
        <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
            <Avatar className="h-8 w-8">
                <AvatarFallback>
                    {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                </AvatarFallback>
            </Avatar>

            <div className={`flex flex-col max-w-[80%] ${isUser ? 'items-end' : 'items-start'}`}>
                <div
                    className={`rounded-lg px-3 py-2 text-sm ${isUser
                        ? 'bg-primary text-primary-foreground'
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

const ChatSkeleton: React.FC = () => (
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
);

export const ChatInterface: React.FC<ChatInterfaceProps> = ({
    projectId,
    className
}) => {
    const [inputMessage, setInputMessage] = useState('');
    const [selectedFiles, setSelectedFiles] = useState<string[]>([]);
    const [generationStatus, setGenerationStatus] = useState<{
        isGenerating: boolean;
        jobId?: string;
        message?: string;
    }>({ isGenerating: false });
    const scrollAreaRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const queryClient = useQueryClient();
    const { toast } = useToast();

    const {
        messages,
        isLoading,
        error,
        sendMessage,
        isSending,
    } = useChatState(projectId);

    // WebSocket connection for real-time updates (simplified for now)
    const [isConnected] = useState(true); // Assume connected for now
    const [connectionState] = useState<'connected' | 'connecting' | 'disconnected'>('connected');

    // Auto-scroll to bottom when new messages arrive
    useEffect(() => {
        if (scrollAreaRef.current) {
            const scrollContainer = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]');
            if (scrollContainer) {
                scrollContainer.scrollTop = scrollContainer.scrollHeight;
            }
        }
    }, [messages]);

    // Auto-resize textarea
    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
        }
    }, [inputMessage]);

    const handleSendMessage = async () => {
        if (!inputMessage.trim() || isSending) return;

        let messageContent = inputMessage.trim();

        // Add file references to the message
        if (selectedFiles.length > 0) {
            const fileRefs = selectedFiles.map(file => `@${file}`).join(' ');
            messageContent = `${fileRefs}\n\n${messageContent}`;
        }

        // Sanitize and validate the message
        const { sanitized, isValid, error: validationError } = sanitizeAndValidateChatMessage(messageContent);

        if (!isValid) {
            toast({
                title: "Invalid message",
                description: validationError,
                variant: "destructive",
            });
            return;
        }

        setInputMessage('');
        setSelectedFiles([]);

        try {
            await sendMessage(sanitized, 'user');
            // Here you could also trigger an AI response
            // For now, we'll just send the user message
        } catch (error) {
            // Error is handled by the hook
        }
    };

    const handleFileSelect = (fileName: string) => {
        if (!selectedFiles.includes(fileName)) {
            setSelectedFiles(prev => [...prev, fileName]);
        }
    };

    const removeFile = (fileName: string) => {
        setSelectedFiles(prev => prev.filter(f => f !== fileName));
    };

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    };

    if (error) {
        return (
            <Card className={className}>
                <CardContent className="pt-6">
                    <div className="text-center text-red-600">
                        Failed to load chat: {error.message}
                    </div>
                </CardContent>
            </Card>
        );
    }

    return (
        <Card className={className}>
            <CardHeader>
                <CardTitle className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Bot className="h-5 w-5" />
                        Project Chat
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
                                    {connectionState === 'connecting' ? 'Connecting...' : 'Disconnected'}
                                </>
                            )}
                        </Badge>
                        {generationStatus.isGenerating && (
                            <Badge variant="outline" className="flex items-center gap-1">
                                <Loader2 className="h-3 w-3 animate-spin" />
                                Generating...
                            </Badge>
                        )}
                    </div>
                </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
                <div className="flex flex-col h-[500px]">
                    {/* Messages Area */}
                    <ScrollArea ref={scrollAreaRef} className="flex-1 p-4">
                        {isLoading ? (
                            <ChatSkeleton />
                        ) : messages.length === 0 ? (
                            <div className="flex items-center justify-center h-full text-muted-foreground">
                                <div className="text-center space-y-2">
                                    <Bot className="h-12 w-12 mx-auto opacity-50" />
                                    <p>Start a conversation about your project</p>
                                    <p className="text-sm">Ask questions, get help, or discuss your infrastructure</p>
                                </div>
                            </div>
                        ) : (
                            <div className="space-y-4">
                                {messages.map((message) => (
                                    <MessageBubble key={message.id} message={message} projectId={projectId} />
                                ))}
                                {isSending && (
                                    <div className="flex gap-3">
                                        <Avatar className="h-8 w-8">
                                            <AvatarFallback>
                                                <Loader2 className="h-4 w-4 animate-spin" />
                                            </AvatarFallback>
                                        </Avatar>
                                        <div className="bg-muted rounded-lg px-3 py-2">
                                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                                <Loader2 className="h-3 w-3 animate-spin" />
                                                Sending message...
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </ScrollArea>

                    {/* Input Area */}
                    <div className="border-t p-4">
                        {/* Selected Files */}
                        {selectedFiles.length > 0 && (
                            <div className="mb-3 flex flex-wrap gap-2">
                                {selectedFiles.map((file) => (
                                    <Badge key={file} variant="secondary" className="flex items-center gap-1">
                                        <FileText className="w-3 h-3" />
                                        {file}
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => removeFile(file)}
                                            className="h-4 w-4 p-0 hover:bg-destructive hover:text-destructive-foreground"
                                        >
                                            ×
                                        </Button>
                                    </Badge>
                                ))}
                            </div>
                        )}

                        <div className="flex gap-2">
                            <div className="flex-1 space-y-2">
                                <Textarea
                                    ref={textareaRef}
                                    value={inputMessage}
                                    onChange={(e) => setInputMessage(e.target.value)}
                                    onKeyPress={handleKeyPress}
                                    placeholder="Type your message... (Press Enter to send, Shift+Enter for new line)"
                                    className="min-h-[40px] max-h-[120px] resize-none"
                                    disabled={isSending}
                                />

                                {/* File Selection */}
                                <div className="flex items-center gap-2">
                                    <Dialog>
                                        <DialogTrigger asChild>
                                            <Button variant="outline" size="sm" className="h-8">
                                                <Paperclip className="w-4 h-4 mr-2" />
                                                Attach Files
                                            </Button>
                                        </DialogTrigger>
                                        <DialogContent className="max-w-md">
                                            <DialogHeader>
                                                <DialogTitle>Select Project Files</DialogTitle>
                                            </DialogHeader>
                                            <div className="max-h-64 overflow-y-auto">
                                                <div className="text-center text-muted-foreground py-8">
                                                    <FileText className="w-12 h-12 mx-auto mb-2 opacity-50" />
                                                    <p>No files available for selection.</p>
                                                </div>
                                            </div>
                                        </DialogContent>
                                    </Dialog>
                                </div>
                            </div>

                            <Button
                                onClick={handleSendMessage}
                                disabled={(!inputMessage.trim() && selectedFiles.length === 0) || isSending}
                                size="icon"
                                className="shrink-0"
                            >
                                {isSending ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                    <Send className="h-4 w-4" />
                                )}
                            </Button>
                        </div>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};