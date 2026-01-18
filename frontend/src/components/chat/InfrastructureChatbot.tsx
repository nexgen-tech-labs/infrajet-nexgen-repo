import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
    Bot,
    User,
    Send,
    Wifi,
    WifiOff,
    CheckCircle,
    AlertCircle,
    Code,
    Download,
    FileText,
    Loader2,
    Zap,
    MessageSquare
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { useWebSocket } from '@/hooks/useWebSocket';
import { API_CONFIG, getWebSocketUrl, getApiUrl } from '@/config/api';
import {
    Message,
    Clarification,
    GeneratedFile,
    WebSocketEvent
} from '@/types/chat';

export const InfrastructureChatbot: React.FC = () => {
    const { user, session } = useAuth();
    const [messages, setMessages] = useState<Message[]>([]);
    const [inputMessage, setInputMessage] = useState('');

    const [isLoading, setIsLoading] = useState(false);
    const [currentClarification, setCurrentClarification] = useState<Clarification | null>(null);
    const [generationProgress, setGenerationProgress] = useState(0);
    const [generatedFiles, setGeneratedFiles] = useState<GeneratedFile[]>([]);

    const messagesEndRef = useRef<HTMLDivElement>(null);
    const wsUrl = getWebSocketUrl(API_CONFIG.WS_ENDPOINTS.ENHANCED_CHAT, session?.access_token || '');

    const addSystemMessage = (content: string) => {
        const message: Message = {
            id: Date.now().toString(),
            type: 'system',
            content,
            timestamp: new Date()
        };
        setMessages(prev => [...prev, message]);
    };

    const addBotMessage = (content: string, status?: Message['status'], confidence?: number) => {
        const message: Message = {
            id: Date.now().toString(),
            type: 'bot',
            content,
            timestamp: new Date(),
            status,
            confidence
        };
        setMessages(prev => [...prev, message]);
    };

    const addUserMessage = (content: string) => {
        const message: Message = {
            id: Date.now().toString(),
            type: 'user',
            content,
            timestamp: new Date()
        };
        setMessages(prev => [...prev, message]);
    };

    const handleWebSocketEvent = (event: WebSocketEvent) => {
        switch (event.event_type) {
            case 'analysis_started':
                addBotMessage('🤖 Analyzing your request...', 'analyzing');
                setIsLoading(true);
                break;

            case 'analysis_complete':
                addBotMessage(`✅ Analysis complete! ${event.message || ''}`, 'completed');
                setIsLoading(false);
                break;

            case 'clarification_needed':
                if (event.clarification_id && event.questions) {
                    const clarification: Clarification = {
                        id: event.clarification_id,
                        questions: event.questions.map((q, i) => ({
                            id: i.toString(),
                            question: q,
                            required: true
                        })),
                        round: event.round || 1,
                        maxRounds: event.max_rounds || 2,
                        responses: {}
                    };
                    setCurrentClarification(clarification);
                    addBotMessage(
                        `I need some clarification to generate the best code for you. (Round ${clarification.round} of ${clarification.maxRounds})`,
                        'clarifying'
                    );
                }
                setIsLoading(false);
                break;

            case 'clarification_timeout':
                addBotMessage('⏱️ Clarification timeout reached, proceeding with available information...', 'completed');
                setCurrentClarification(null);
                break;

            case 'generation_started':
                addBotMessage('🚀 Starting code generation...', 'generating');
                setGenerationProgress(0);
                setIsLoading(true);
                break;

            case 'generation_progress':
                if (event.progress !== undefined) {
                    setGenerationProgress(event.progress);
                }
                break;

            case 'generation_completed':
                addBotMessage('✅ Code generation completed!', 'completed');
                setGenerationProgress(100);
                setIsLoading(false);
                break;

            case 'azure_files_saved':
                if (event.saved_files) {
                    setGeneratedFiles(event.saved_files);
                    addBotMessage(
                        `💾 Generated and saved ${event.saved_files.length} files to Azure File Share!`,
                        'completed'
                    );
                }
                break;

            case 'error':
                addBotMessage(`❌ Error: ${event.error || event.message}`, 'error');
                setIsLoading(false);
                setCurrentClarification(null);
                break;

            default:
                console.log('Unhandled WebSocket event:', event);
        }

        // Handle thread_id if needed for future features
        if (event.thread_id) {
            console.log('Thread ID:', event.thread_id);
        }
    };

    const { isConnected } = useWebSocket({
        url: wsUrl,
        onMessage: handleWebSocketEvent,
        onConnect: () => addSystemMessage('Connected to Infrastructure Chatbot'),
        onDisconnect: () => addSystemMessage('Disconnected from server'),
        onError: (error) => console.error('WebSocket error:', error)
    });

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    useEffect(() => {
        // Add welcome message on component mount
        const welcomeMessage: Message = {
            id: 'welcome',
            type: 'bot',
            content: "👋 Welcome to the Infrastructure Chatbot! I can help you generate production-ready infrastructure code for AWS, Azure, and GCP. Just describe what you need and I'll analyze your request, ask clarifying questions if needed, and generate the code automatically.",
            timestamp: new Date(),
            status: 'completed'
        };
        setMessages([welcomeMessage]);
    }, []);



    const sendMessage = async () => {
        if (!inputMessage.trim() || !isConnected || !session?.access_token) return;

        const messageContent = inputMessage.trim();
        setInputMessage('');
        addUserMessage(messageContent);
        setIsLoading(true);

        try {
            const response = await fetch(getApiUrl(API_CONFIG.ENDPOINTS.ENHANCED_CHAT), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${session.access_token}`
                },
                body: JSON.stringify({
                    message: messageContent,
                    cloud_provider: 'AWS',
                    enable_realtime: true,
                    save_to_azure: true
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            if (data.thread_id) {
                console.log('Message sent, thread ID:', data.thread_id);
            }
        } catch (error) {
            console.error('Error sending message:', error);
            addBotMessage('❌ Failed to send message. Please try again.', 'error');
            setIsLoading(false);
        }
    };

    const handleClarificationResponse = (questionId: string, response: string) => {
        if (!currentClarification) return;

        setCurrentClarification(prev => prev ? {
            ...prev,
            responses: { ...prev.responses, [questionId]: response }
        } : null);
    };

    const submitClarification = async () => {
        if (!currentClarification || !session?.access_token) return;

        try {
            const response = await fetch(getApiUrl(`${API_CONFIG.ENDPOINTS.CLARIFICATIONS}/${currentClarification.id}/respond`), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${session.access_token}`
                },
                body: JSON.stringify({
                    responses: currentClarification.responses
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            addUserMessage(`Clarification responses: ${Object.values(currentClarification.responses).join(', ')}`);
            setCurrentClarification(null);
        } catch (error) {
            console.error('Error submitting clarification:', error);
            addBotMessage('❌ Failed to submit clarification. Please try again.', 'error');
        }
    };

    const downloadFile = async (file: GeneratedFile) => {
        try {
            const response = await fetch(getApiUrl(`${API_CONFIG.ENDPOINTS.AZURE_FILES}/${file.azure_path}`), {
                headers: {
                    'Authorization': `Bearer ${session?.access_token}`
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = file.filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } catch (error) {
            console.error('Error downloading file:', error);
        }
    };

    const getStatusIcon = (status?: Message['status']) => {
        switch (status) {
            case 'analyzing':
                return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
            case 'clarifying':
                return <MessageSquare className="h-4 w-4 text-yellow-500" />;
            case 'generating':
                return <Code className="h-4 w-4 text-purple-500" />;
            case 'completed':
                return <CheckCircle className="h-4 w-4 text-green-500" />;
            case 'error':
                return <AlertCircle className="h-4 w-4 text-red-500" />;
            default:
                return null;
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    };

    return (
        <div className="flex flex-col h-full max-w-4xl mx-auto">
            {/* Header */}
            <Card className="rounded-b-none border-b-0">
                <CardHeader className="pb-4">
                    <div className="flex items-center justify-between">
                        <CardTitle className="flex items-center gap-2">
                            <Bot className="h-6 w-6 text-blue-600" />
                            🤖 Infrastructure Chatbot
                        </CardTitle>
                        <div className="flex items-center gap-2">
                            {isConnected ? (
                                <Badge variant="outline" className="text-green-600 border-green-600">
                                    <Wifi className="h-3 w-3 mr-1" />
                                    Connected
                                </Badge>
                            ) : (
                                <Badge variant="outline" className="text-red-600 border-red-600">
                                    <WifiOff className="h-3 w-3 mr-1" />
                                    Disconnected
                                </Badge>
                            )}
                        </div>
                    </div>
                    <p className="text-sm text-muted-foreground">
                        Describe your infrastructure needs and I'll generate production-ready code with intelligent analysis and clarifications.
                    </p>
                    <div className="flex flex-wrap gap-2 mt-3">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setInputMessage("Create an S3 bucket with versioning enabled")}
                            disabled={isLoading}
                        >
                            S3 Bucket Example
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setInputMessage("Set up a web server with load balancer")}
                            disabled={isLoading}
                        >
                            Web Server Example
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setInputMessage("Create a VPC with public and private subnets")}
                            disabled={isLoading}
                        >
                            VPC Example
                        </Button>
                    </div>
                </CardHeader>
            </Card>

            {/* Messages */}
            <Card className="flex-1 rounded-none border-x border-t-0 border-b-0">
                <CardContent className="p-0 h-full">
                    <ScrollArea className="h-full p-4">
                        <div className="space-y-4">
                            {messages.map((message) => (
                                <div
                                    key={message.id}
                                    className={`flex gap-3 ${message.type === 'user' ? 'justify-end' : 'justify-start'
                                        }`}
                                >
                                    {message.type !== 'user' && (
                                        <div className="flex-shrink-0">
                                            {message.type === 'bot' ? (
                                                <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
                                                    <Bot className="h-4 w-4 text-blue-600" />
                                                </div>
                                            ) : (
                                                <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center">
                                                    <Zap className="h-4 w-4 text-gray-600" />
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    <div
                                        className={`max-w-[80%] rounded-lg px-4 py-2 ${message.type === 'user'
                                            ? 'bg-blue-600 text-white'
                                            : message.type === 'system'
                                                ? 'bg-gray-100 text-gray-700'
                                                : 'bg-gray-50 text-gray-900'
                                            }`}
                                    >
                                        <div className="flex items-start gap-2">
                                            <div className="flex-1">
                                                <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                                                <div className="flex items-center gap-2 mt-1">
                                                    <span className="text-xs opacity-70">
                                                        {message.timestamp.toLocaleTimeString()}
                                                    </span>
                                                    {message.confidence && (
                                                        <Badge variant="secondary" className="text-xs">
                                                            {message.confidence}% confidence
                                                        </Badge>
                                                    )}
                                                </div>
                                            </div>
                                            {getStatusIcon(message.status)}
                                        </div>
                                    </div>

                                    {message.type === 'user' && (
                                        <div className="flex-shrink-0">
                                            <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center">
                                                <User className="h-4 w-4 text-white" />
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ))}

                            {/* Generation Progress */}
                            {isLoading && generationProgress > 0 && (
                                <div className="flex justify-start">
                                    <div className="bg-gray-50 rounded-lg px-4 py-2 max-w-[80%]">
                                        <div className="flex items-center gap-2 mb-2">
                                            <Code className="h-4 w-4 text-purple-500" />
                                            <span className="text-sm font-medium">Generating code...</span>
                                        </div>
                                        <Progress value={generationProgress} className="w-full" />
                                        <p className="text-xs text-muted-foreground mt-1">
                                            {generationProgress}% complete
                                        </p>
                                    </div>
                                </div>
                            )}

                            {/* Clarification Questions */}
                            {currentClarification && (
                                <div className="flex justify-start">
                                    <div className="bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3 max-w-[80%]">
                                        <div className="space-y-3">
                                            {currentClarification.questions.map((question, index) => (
                                                <div key={question.id} className="space-y-2">
                                                    <label className="text-sm font-medium text-gray-900">
                                                        {index + 1}. {question.question}
                                                        {question.required && <span className="text-red-500 ml-1">*</span>}
                                                    </label>
                                                    <Textarea
                                                        placeholder="Your answer..."
                                                        value={currentClarification.responses[question.id] || ''}
                                                        onChange={(e) => handleClarificationResponse(question.id, e.target.value)}
                                                        className="min-h-[60px]"
                                                    />
                                                </div>
                                            ))}
                                            <Button
                                                onClick={submitClarification}
                                                className="w-full"
                                                disabled={Object.keys(currentClarification.responses).length === 0}
                                            >
                                                Submit Answers
                                            </Button>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* Generated Files */}
                            {generatedFiles.length > 0 && (
                                <div className="flex justify-start">
                                    <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-3 max-w-[80%]">
                                        <div className="flex items-center gap-2 mb-3">
                                            <FileText className="h-4 w-4 text-green-600" />
                                            <span className="text-sm font-medium text-green-900">Generated Files</span>
                                        </div>
                                        <div className="space-y-2">
                                            {generatedFiles.map((file, index) => (
                                                <div key={index} className="flex items-center justify-between bg-white rounded px-3 py-2">
                                                    <div className="flex items-center gap-2">
                                                        <Code className="h-4 w-4 text-gray-500" />
                                                        <span className="text-sm font-medium">{file.filename}</span>
                                                        <Badge variant="secondary" className="text-xs">
                                                            {(file.size / 1024).toFixed(1)} KB
                                                        </Badge>
                                                    </div>
                                                    <Button
                                                        size="sm"
                                                        variant="outline"
                                                        onClick={() => downloadFile(file)}
                                                    >
                                                        <Download className="h-3 w-3 mr-1" />
                                                        Download
                                                    </Button>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                        <div ref={messagesEndRef} />
                    </ScrollArea>
                </CardContent>
            </Card>

            {/* Input */}
            <Card className="rounded-t-none border-t-0">
                <CardContent className="p-4">
                    <div className="flex gap-2">
                        <Textarea
                            placeholder="Describe your infrastructure needs... (e.g., 'Create an S3 bucket with versioning enabled')"
                            value={inputMessage}
                            onChange={(e) => setInputMessage(e.target.value)}
                            onKeyDown={handleKeyDown}
                            className="min-h-[60px] resize-none"
                            disabled={!isConnected || isLoading}
                        />
                        <Button
                            onClick={sendMessage}
                            disabled={!inputMessage.trim() || !isConnected || isLoading}
                            className="px-4"
                        >
                            {isLoading ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                                <Send className="h-4 w-4" />
                            )}
                        </Button>
                    </div>

                    {!isConnected && (
                        <Alert className="mt-3">
                            <AlertCircle className="h-4 w-4" />
                            <AlertDescription>
                                Not connected to the server. Make sure your backend is running on localhost:8000.
                                <br />
                                <span className="text-sm text-muted-foreground mt-1 block">
                                    You can still use the example prompts above to see the interface in action.
                                </span>
                            </AlertDescription>
                        </Alert>
                    )}
                </CardContent>
            </Card>
        </div>
    );
};