import React, { useState, useRef, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Send, Bot, Loader2, Wifi, WifiOff, FileText, Square, MessageSquare, User, Zap } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import CodeEditor from '@/components/CodeEditor';
import { useToast } from '@/hooks/use-toast';
import { useInfraJetAutonomousChat, ConversationThread, ConversationMessage } from '@/hooks/useInfraJetAutonomousChat';
import { ClarificationDialog } from './ClarificationDialog';
import { GenerationProgress } from './GenerationProgress';

interface InfraJetChatInterfaceProps {
    className?: string;
}

const MessageBubble: React.FC<{ message: ConversationMessage }> = ({ message }) => {
    const isUser = message.type === 'user';
    const isSystem = message.type === 'system';
    const isEvent = message.type === 'event';

    const getAvatarIcon = () => {
        if (isUser) return <User className="h-4 w-4" />;
        if (isSystem || isEvent) return <Zap className="h-4 w-4" />;
        return <Bot className="h-4 w-4" />;
    };

    const getAvatarColor = () => {
        if (isUser) return 'bg-blue-600 text-white';
        if (isSystem || isEvent) return 'bg-yellow-600 text-white';
        return 'bg-gradient-to-r from-purple-600 to-blue-600 text-white';
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
                        {isUser ? "You" : isSystem ? "System" : isEvent ? "Event" : "InfraJet AI"}
                    </span>
                </div>
                <div
                    className={`rounded-lg px-3 py-2 text-sm whitespace-pre-wrap ${isUser
                        ? 'bg-blue-600 text-white'
                        : isSystem
                            ? 'bg-yellow-50 text-yellow-800 border border-yellow-200'
                            : isEvent
                                ? 'bg-green-50 text-green-800 border border-green-200'
                                : 'bg-slate-700 text-slate-300'
                        }`}
                >
                    {message.content}
                </div>
                <span className="text-xs text-muted-foreground mt-1">
                    {formatDistanceToNow(new Date(message.timestamp), { addSuffix: true })}
                </span>
            </div>
        </div>
    );
};

interface GenerationIndicatorProps {
    message: string;
}


export const InfraJetChatInterface: React.FC<InfraJetChatInterfaceProps> = ({
    className
}) => {
    const [inputMessage, setInputMessage] = useState('');
    const [isSending, setIsSending] = useState(false);
    const [conversationThreads, setConversationThreads] = useState<ConversationThread[]>([]);
    const [viewingFile, setViewingFile] = useState<{ name: string; content: string } | null>(null);

    const scrollAreaRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const { toast } = useToast();

    // Use the autonomous chat hook
    const {
        isConnected,
        isGenerating,
        currentThreadId,
        messages,
        clarificationDialog,
        generationProgress,
        initChat,
        sendMessage,
        respondToClarification,
        getConversationThreads: fetchConversationThreads,
        switchToThread,
    } = useInfraJetAutonomousChat();

    // Initialize chat
    useEffect(() => {
        initChat();
        loadConversationThreads();
    }, [initChat]);

    const loadConversationThreads = async () => {
        const threads = await fetchConversationThreads();
        setConversationThreads(threads);
    };

    const handleSendMessage = async () => {
        console.log('🔍 handleSendMessage called');
        console.log('Input message:', inputMessage);
        console.log('Is sending:', isSending);
        console.log('Is generating:', isGenerating);

        if (!inputMessage.trim() || isSending || isGenerating) {
            console.log('❌ Message send blocked - conditions not met');
            return;
        }

        const messageContent = inputMessage.trim();
        console.log('📤 Sending message:', messageContent);

        setInputMessage('');
        setIsSending(true);

        try {
            console.log('🚀 Calling sendMessage hook...');
            const result = await sendMessage(messageContent);
            console.log('✅ Send message result:', result);
        } catch (error) {
            console.error('❌ Failed to send message:', error);
            toast({
                title: "Failed to send message",
                description: "Please try again",
                variant: "destructive",
            });
        } finally {
            console.log('🔄 Setting isSending to false');
            setIsSending(false);
        }
    };

    const handleClarificationResponse = async (responses: { [key: string]: string }) => {
        if (!clarificationDialog) return;

        await respondToClarification(clarificationDialog.request_id, responses);
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
                            InfraJet Autonomous Chat
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
                            {currentThreadId && (
                                <Badge variant="outline">
                                    Thread: {currentThreadId.slice(0, 8)}...
                                </Badge>
                            )}
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
                                        <Bot className="h-12 w-12 mx-auto opacity-50" />
                                        <p>Start an autonomous conversation</p>
                                        <p className="text-sm">Describe your infrastructure needs and I'll analyze, clarify, and generate code automatically</p>
                                    </div>
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    {messages.map((message) => (
                                        <MessageBubble key={message.id} message={message} />
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
                            <div className="flex gap-2">
                                <Textarea
                                    ref={textareaRef}
                                    value={inputMessage}
                                    onChange={(e) => setInputMessage(e.target.value)}
                                    onKeyPress={handleKeyPress}
                                    placeholder="Describe your infrastructure needs... (e.g., 'Create an S3 bucket with versioning and encryption')"
                                    className="min-h-[60px] max-h-[120px] resize-none"
                                    disabled={isSending || isGenerating}
                                />
                                <Button
                                    onClick={handleSendMessage}
                                    disabled={!inputMessage.trim() || isSending || isGenerating}
                                    size="icon"
                                    className="shrink-0 h-[60px] w-[60px]"
                                >
                                    {isSending ? (
                                        <Loader2 className="h-5 w-5 animate-spin" />
                                    ) : isGenerating ? (
                                        <Square className="h-5 w-5" />
                                    ) : (
                                        <Send className="h-5 w-5" />
                                    )}
                                </Button>
                            </div>

                            {/* Helpful tips */}
                            {!isGenerating && inputMessage.length === 0 && (
                                <div className="text-xs text-muted-foreground space-y-1 mt-2">
                                    <p>🤖 <strong>Autonomous AI:</strong> I'll analyze your request and ask for clarification if needed</p>
                                    <p>• "Create a VPC with public and private subnets" • "Set up an ECS cluster with load balancer"</p>
                                </div>
                            )}
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Conversation Threads */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <MessageSquare className="h-5 w-5" />
                        Conversations
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {conversationThreads.length === 0 ? (
                        <div className="text-center text-muted-foreground py-8">
                            <MessageSquare className="w-12 h-12 mx-auto mb-2 opacity-50" />
                            <p>No conversations yet</p>
                            <p className="text-sm">Start a conversation to see threads here</p>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {conversationThreads.map((thread) => (
                                <div
                                    key={thread.thread_id}
                                    className={`border rounded-lg p-3 cursor-pointer hover:bg-gray-50 ${currentThreadId === thread.thread_id ? 'border-blue-500 bg-blue-50' : ''
                                        }`}
                                    onClick={() => switchToThread(thread.thread_id)}
                                >
                                    <div className="flex items-center justify-between mb-2">
                                        <h4 className="font-medium text-sm truncate">{thread.title}</h4>
                                        <Badge variant="secondary" className="text-xs">
                                            {thread.message_count} msgs
                                        </Badge>
                                    </div>
                                    <div className="text-xs text-muted-foreground">
                                        {formatDistanceToNow(new Date(thread.last_message_at), { addSuffix: true })}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Clarification Dialog */}
            {clarificationDialog && (
                <ClarificationDialog
                    isOpen={true}
                    questions={clarificationDialog.questions}
                    contextSummary={clarificationDialog.context_summary}
                    onRespond={handleClarificationResponse}
                    onCancel={() => { }} // Handled by the dialog
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