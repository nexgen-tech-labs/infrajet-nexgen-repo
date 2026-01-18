import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import {
  MessageSquare,
  Plus,
  Bot,
  User,
  Zap,
  Clock,
  Cloud,
  Loader2,
  ChevronDown,
  Wifi,
  WifiOff,
  FileText,
  Download,
  Search,
  MoreVertical,
  ChevronLeft,
  RefreshCw,
  Edit3
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { useUserChats } from '@/hooks/useUserChats';
import { useProjectFiles } from '@/hooks/useProjectFiles';
import { ConversationThread, Message } from '@/types/chat';
import CodeEditor from '@/components/CodeEditor';
import ChatInput from '@/components/ChatInput';
import { GenerationProgress } from './GenerationProgress';

interface UserChatsProps {
  projectId: string;
  userId: string;
  className?: string;
}

const ThreadsSidebar: React.FC<{
  threads: ConversationThread[];
  selectedThread: ConversationThread | null;
  onSelectThread: (thread: ConversationThread) => void;
  onNewChat: () => void;
  loading: boolean;
  hasMore: boolean;
  onLoadMore: () => void;
}> = ({ threads, selectedThread, onSelectThread, onNewChat, loading, hasMore, onLoadMore }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [sortBy, setSortBy] = useState<string>('recent');

  // Filter and sort threads
  const filteredThreads = threads
    .filter(thread => {
      const matchesSearch = thread.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                           thread.cloud_provider?.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesStatus = filterStatus === 'all' || thread.status === filterStatus;
      return matchesSearch && matchesStatus;
    })
    .sort((a, b) => {
      switch (sortBy) {
        case 'recent':
          return new Date(b.last_message_at).getTime() - new Date(a.last_message_at).getTime();
        case 'oldest':
          return new Date(a.last_message_at).getTime() - new Date(b.last_message_at).getTime();
        case 'messages':
          return (b.message_count || 0) - (a.message_count || 0);
        case 'title':
          return (a.title || '').localeCompare(b.title || '');
        default:
          return 0;
      }
    });

  return (
    <div className="w-full lg:w-80 border-r bg-gradient-to-b from-slate-50 to-white">
      {/* Header */}
      <div className="p-4 border-b bg-white/80 backdrop-blur-sm">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-slate-800">Chat History</h2>
          <Button onClick={onNewChat} size="sm" className="bg-blue-600 hover:bg-blue-700">
            <Plus className="h-4 w-4 mr-2" />
            New Chat
          </Button>
        </div>

        {/* Search */}
        <div className="relative mb-3">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-slate-400" />
          <Input
            placeholder="Search conversations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10 bg-white border-slate-200 focus:border-blue-300"
          />
        </div>

        {/* Filters */}
        <div className="flex gap-2">
          <Select value={filterStatus} onValueChange={setFilterStatus}>
            <SelectTrigger className="w-24 h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All</SelectItem>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
            </SelectContent>
          </Select>

          <Select value={sortBy} onValueChange={setSortBy}>
            <SelectTrigger className="w-28 h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="recent">Recent</SelectItem>
              <SelectItem value="oldest">Oldest</SelectItem>
              <SelectItem value="messages">Messages</SelectItem>
              <SelectItem value="title">Title</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Threads List */}
      <ScrollArea className="h-[calc(100vh-200px)]">
        <div className="p-2">
          {filteredThreads.length > 0 ? (
            <div className="space-y-1">
              {filteredThreads.map((thread) => (
                <div
                  key={thread.thread_id}
                  onClick={() => onSelectThread(thread)}
                  className={`group p-3 rounded-xl cursor-pointer transition-all duration-200 ${
                    selectedThread?.thread_id === thread.thread_id
                      ? 'bg-blue-50 border-2 border-blue-200 shadow-sm'
                      : 'hover:bg-slate-50 hover:shadow-sm border-2 border-transparent'
                  }`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                      <div className={`p-1.5 rounded-lg ${
                        thread.status === 'active' 
                          ? 'bg-green-100 text-green-600' 
                          : 'bg-slate-100 text-slate-500'
                      }`}>
                        <MessageSquare className="h-3.5 w-3.5" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <h3 className="font-medium text-sm text-slate-800 truncate">
                          {thread.title || 'Untitled Chat'}
                        </h3>
                        <div className="flex items-center gap-2 mt-1">
                          {thread.cloud_provider && (
                            <Badge variant="outline" className="text-xs px-1.5 py-0.5">
                              <Cloud className="h-2.5 w-2.5 mr-1" />
                              {thread.cloud_provider}
                            </Badge>
                          )}
                          <Badge 
                            variant={thread.status === 'active' ? 'default' : 'secondary'} 
                            className="text-xs px-1.5 py-0.5"
                          >
                            {thread.status}
                          </Badge>
                        </div>
                      </div>
                    </div>
                    
                    <div className="opacity-0 group-hover:opacity-100 transition-opacity">
                      <Button variant="ghost" size="sm" className="h-6 w-6 p-0">
                        <MoreVertical className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-xs text-slate-500">
                    <div className="flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {(() => {
                        try {
                          return formatDistanceToNow(new Date(thread.last_message_at), { addSuffix: true });
                        } catch {
                          return 'Unknown time';
                        }
                      })()}
                    </div>
                    {thread.message_count && (
                      <span className="bg-slate-100 px-2 py-0.5 rounded-full">
                        {thread.message_count} messages
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-6 text-center text-slate-500">
              <MessageSquare className="h-12 w-12 mx-auto mb-3 opacity-50" />
              <p className="text-sm font-medium mb-1">No conversations found</p>
              <p className="text-xs">
                {searchQuery ? 'Try adjusting your search terms' : 'Start a new conversation to see threads here'}
              </p>
            </div>
          )}

          {loading && (
            <div className="flex items-center justify-center p-4">
              <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
            </div>
          )}

          {hasMore && !loading && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onLoadMore}
              className="w-full mt-2 text-slate-600 hover:text-slate-800"
            >
              <ChevronDown className="h-4 w-4 mr-2" />
              Load More
            </Button>
          )}
        </div>
      </ScrollArea>
    </div>
  );
};

const MessageBubble: React.FC<{
  message: Message;
  onViewFiles?: (generationId: string) => void;
  onClarificationResponse?: (responses: { [key: string]: string }) => void;
}> = ({ message, onViewFiles, onClarificationResponse }) => {
  const isUser = message.type === 'user';
  const isSystem = message.type === 'system';
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
      onClarificationResponse(responses);
      setResponses({});
    }
  };

  const renderClarificationInputs = () => {
    if (!message.clarification_questions) return null;

    return (
      <div className="mt-3 space-y-3">
        {message.clarification_questions.map((question) => (
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
    <div className={`flex gap-4 ${isUser ? 'flex-row-reverse' : 'flex-row'} group`}>
      <Avatar className="h-10 w-10 ring-2 ring-white shadow-sm">
        <AvatarFallback className={getAvatarColor()}>
          {getAvatarIcon()}
        </AvatarFallback>
      </Avatar>

      <div className={`flex flex-col max-w-[75%] ${isUser ? 'items-end' : 'items-start'}`}>
        <div className="flex items-center gap-2 mb-2">
          <span className="text-sm font-semibold text-slate-700">
            {isUser ? "You" : isSystem ? "System" : isClarificationRequest ? "Clarification Needed" : "InfraJet AI"}
          </span>
          <Badge variant="outline" className="text-xs px-2 py-0.5">
            {message.type}
          </Badge>
          {message.status && (
            <Badge 
              variant={message.status === 'completed' ? 'default' : 'secondary'} 
              className="text-xs px-2 py-0.5"
            >
              {message.status}
            </Badge>
          )}
        </div>
        
        <div className={`rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap shadow-sm transition-all duration-200 group-hover:shadow-md ${getMessageStyle()}`}>
          <div className="prose prose-sm max-w-none">
            {message.content}
          </div>
          {renderClarificationInputs()}
        </div>
        
        <div className="flex items-center justify-between mt-2">
          <div className="flex items-center gap-2">
            {message.generation_id && onViewFiles && (
              <Button
                variant="outline"
                size="sm"
                className="h-7 px-3 text-xs bg-white hover:bg-blue-50 border-blue-200 text-blue-700 hover:border-blue-300 transition-colors"
                onClick={() => onViewFiles(message.generation_id!)}
              >
                <FileText className="h-3 w-3 mr-1" />
                View Generated Files
              </Button>
            )}
          </div>
          <span className="text-xs text-slate-500">
            {(() => {
              try {
                return formatDistanceToNow(message.timestamp, { addSuffix: true });
              } catch {
                return 'Invalid time';
              }
            })()}
          </span>
        </div>
      </div>
    </div>
  );
};

const ChatMain: React.FC<{
  selectedThread: ConversationThread | null;
  messages: Message[];
  messagesKey: number;
  loadingMessages: boolean;
  hasMore: boolean;
  isConnected: boolean;
  generationProgress: any;
  onLoadMore: () => void;
  onViewFiles: (generationId: string) => void;
  onReconnectWebSocket: () => void;
  onClarificationResponse: (responses: { [key: string]: string }) => void;
}> = ({ selectedThread, messages, messagesKey, loadingMessages, hasMore, isConnected, generationProgress, onLoadMore, onViewFiles, onReconnectWebSocket, onClarificationResponse }) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);

  // Enhanced scroll behavior
  const scrollToBottom = useCallback((smooth = true) => {
    if (scrollRef.current) {
      const scrollContainer = scrollRef.current.querySelector('[data-radix-scroll-area-viewport]');
      if (scrollContainer) {
        scrollContainer.scrollTo({
          top: scrollContainer.scrollHeight,
          behavior: smooth ? 'smooth' : 'auto'
        });
      }
    }
  }, []);

  // Check if user is at bottom of scroll
  const checkScrollPosition = useCallback(() => {
    if (scrollRef.current) {
      const scrollContainer = scrollRef.current.querySelector('[data-radix-scroll-area-viewport]');
      if (scrollContainer) {
        const { scrollTop, scrollHeight, clientHeight } = scrollContainer;
        const atBottom = scrollHeight - scrollTop - clientHeight < 100;
        setIsAtBottom(atBottom);
        setShowScrollToBottom(!atBottom && messages.length > 0);
      }
    }
  }, [messages.length]);

  // Auto-scroll to bottom when new messages arrive (only if user was already at bottom)
  useEffect(() => {
    if (isAtBottom) {
      scrollToBottom(false);
    }
  }, [messages, messagesKey, isAtBottom, scrollToBottom]);

  // Add scroll listener
  useEffect(() => {
    const scrollContainer = scrollRef.current?.querySelector('[data-radix-scroll-area-viewport]');
    if (scrollContainer) {
      scrollContainer.addEventListener('scroll', checkScrollPosition);
      return () => scrollContainer.removeEventListener('scroll', checkScrollPosition);
    }
  }, [checkScrollPosition]);

  return (
    <div className="flex-1 flex flex-col bg-white min-h-0">
      {/* Enhanced Header */}
      {selectedThread && (
        <div className="p-4 border-b bg-gradient-to-r from-slate-50 to-white flex-shrink-0">
          <div className="flex items-center justify-between">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 bg-blue-100 rounded-lg">
                  <MessageSquare className="h-5 w-5 text-blue-600" />
                </div>
                <div className="min-w-0 flex-1">
                  <h2 className="text-lg font-semibold text-slate-800 truncate">
                    {selectedThread.thread_id ? (selectedThread.title || 'Untitled Chat') : 'New Chat'}
                  </h2>
                  <div className="flex items-center gap-4 text-sm text-slate-500 mt-1">
                    {selectedThread.cloud_provider && (
                      <div className="flex items-center gap-1">
                        <Cloud className="h-3 w-3" />
                        <span className="font-medium">{selectedThread.cloud_provider}</span>
                      </div>
                    )}
                    <div className="flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {(() => {
                        try {
                          return formatDistanceToNow(new Date(selectedThread.created_at), { addSuffix: true });
                        } catch {
                          return 'Unknown';
                        }
                      })()}
                    </div>
                    {selectedThread.message_count && (
                      <div className="flex items-center gap-1">
                        <span>{selectedThread.message_count} messages</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
            
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-2">
                {isConnected ? (
                  <Badge variant="outline" className="text-green-600 border-green-200 bg-green-50">
                    <Wifi className="h-3 w-3 mr-1" />
                    Live
                  </Badge>
                ) : (
                  <Badge variant="outline" className="text-red-600 border-red-200 bg-red-50">
                    <WifiOff className="h-3 w-3 mr-1" />
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={onReconnectWebSocket}
                      className="h-auto p-0 text-red-600 hover:text-red-800 ml-1"
                    >
                      Reconnect
                    </Button>
                  </Badge>
                )}
              </div>
              
              <Badge variant={selectedThread.status === 'active' ? 'default' : 'secondary'}>
                {selectedThread.status}
              </Badge>
            </div>
          </div>
        </div>
      )}

      {/* AI disclaimer */}
      <div className="px-4 py-2 bg-red-50 dark:bg-red-950/20 border-b border-red-200 dark:border-red-800">
        <div className="text-xs text-red-600 dark:text-red-400">
          <strong>Note:</strong> InfraJet can make mistakes. Please double-check all generated code and configurations before deploying to production.
        </div>
      </div>

      {/* Messages Area with Enhanced Scroll */}
      <div className="flex-1 relative min-h-0">
        <ScrollArea ref={scrollRef} className="h-full">
          <div className="p-4">
            {!selectedThread ? (
              <div className="flex items-center justify-center h-full min-h-[400px] text-slate-500">
                <div className="text-center space-y-4">
                  <div className="p-4 bg-slate-100 rounded-full w-16 h-16 mx-auto flex items-center justify-center">
                    <MessageSquare className="h-8 w-8 text-slate-400" />
                  </div>
                  <div>
                    <h3 className="text-lg font-medium text-slate-700 mb-2">Select a conversation</h3>
                    <p className="text-sm">Choose from the sidebar or start a new chat to begin</p>
                  </div>
                </div>
              </div>
            ) : messages.length === 0 && loadingMessages ? (
              <div className="flex items-center justify-center h-full min-h-[400px]">
                <div className="text-center space-y-3">
                  <Loader2 className="h-8 w-8 animate-spin text-blue-500 mx-auto" />
                  <p className="text-sm text-slate-500">Loading messages...</p>
                </div>
              </div>
            ) : messages.length === 0 ? (
              <div className="flex items-center justify-center h-full min-h-[400px] text-slate-500">
                <div className="text-center space-y-4">
                  <div className="p-4 bg-blue-100 rounded-full w-16 h-16 mx-auto flex items-center justify-center">
                    <MessageSquare className="h-8 w-8 text-blue-500" />
                  </div>
                  <div>
                    <h3 className="text-lg font-medium text-slate-700 mb-2">Start the conversation</h3>
                    <p className="text-sm">Send your first message to begin this chat</p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="space-y-6 max-w-4xl mx-auto">
                {messages.map((message, index) => (
                  <MessageBubble
                    key={`${message.id}-${messagesKey}`}
                    message={message}
                    onViewFiles={onViewFiles}
                    onClarificationResponse={message.is_clarification_request ? onClarificationResponse : undefined}
                  />
                ))}

                {loadingMessages && (
                  <div className="flex items-center justify-center p-6">
                    <div className="flex items-center gap-2 text-slate-500">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span className="text-sm">Loading more messages...</span>
                    </div>
                  </div>
                )}

                {hasMore && !loadingMessages && (
                  <div className="flex justify-center p-4">
                    <Button variant="outline" size="sm" onClick={onLoadMore} className="bg-white">
                      Load More Messages
                    </Button>
                  </div>
                )}
              </div>
            )}
          </div>
        </ScrollArea>

        {/* Scroll to Bottom Button */}
        {showScrollToBottom && (
          <Button
            onClick={() => scrollToBottom(true)}
            className="absolute bottom-4 right-4 h-10 w-10 rounded-full shadow-lg bg-blue-600 hover:bg-blue-700"
            size="sm"
          >
            <ChevronDown className="h-4 w-4" />
          </Button>
        )}
      </div>

      {/* Enhanced Generation Progress */}
      {generationProgress && (
        <div className="border-t bg-gradient-to-r from-blue-50 to-indigo-50 p-4 flex-shrink-0">
          <GenerationProgress
            status={generationProgress.status}
            progressPercentage={generationProgress.progress_percentage}
            currentStep={generationProgress.current_step}
          />
        </div>
      )}
    </div>
  );
};
// Removed GenerationsSidebar - moved to Files tab

export const UserChats: React.FC<UserChatsProps> = ({
  projectId,
  userId,
  className
}) => {
  const [activeTab, setActiveTab] = useState('threads');
  const [showFilesDialog, setShowFilesDialog] = useState(false);
  const [selectedGenerationId, setSelectedGenerationId] = useState<string | null>(null);

  const {
    threads,
    selectedThread,
    messages,
    messagesKey,
    loading,
    loadingMessages,
    hasMore,
    isConnected,
    sendingMessage,
    isGenerating,
    generationProgress,
    clarificationDialog,
    selectThread,
    createNewThread,
    loadMoreMessages,
    loadMoreThreads,
    sendMessage,
    respondToClarification,
    reconnectWebSocket
  } = useUserChats(projectId, userId);

  const {
    generations,
    selectedGeneration,
    selectedFile,
    fileContent,
    loading: loadingGenerations,
    loadingFiles,
    loadingContent,
    fetchGenerations,
    selectGeneration,
    selectFile,
    downloadFile
  } = useProjectFiles(projectId);

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

  const handleClarificationResponse = async (responses: { [key: string]: string }) => {
    try {
      await respondToClarification(responses);
    } catch (error) {
      console.error('Failed to respond to clarification:', error);
    }
  };

  // Debug logging for generation progress
  useEffect(() => {
    console.log('🎨 GenerationProgress state:', generationProgress);
  }, [generationProgress]);

  // Temporary test button to manually trigger progress bar
  const testProgressBar = () => {
    console.log('🧪 Testing progress bar manually');
    // This will be removed after debugging
  };

  // Removed generations functionality - moved to Files tab

  return (
    <div className={`flex flex-col lg:flex-row h-screen bg-gradient-to-br from-slate-50 to-white ${className}`}>
      {/* Threads Sidebar - Enhanced mobile behavior */}
      <div className={`${selectedThread && selectedThread.thread_id ? 'hidden lg:flex' : 'flex'} lg:flex`}>
        <ThreadsSidebar
          threads={threads}
          selectedThread={selectedThread}
          onSelectThread={selectThread}
          onNewChat={createNewThread}
          loading={loading}
          hasMore={hasMore}
          onLoadMore={loadMoreThreads}
        />
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
        <ChatMain
          selectedThread={selectedThread}
          messages={messages}
          messagesKey={messagesKey}
          loadingMessages={loadingMessages}
          hasMore={hasMore}
          isConnected={isConnected}
          generationProgress={generationProgress}
          onLoadMore={loadMoreMessages}
          onViewFiles={handleViewFiles}
          onReconnectWebSocket={reconnectWebSocket}
          onClarificationResponse={handleClarificationResponse}
        />

        {/* Enhanced Chat Input */}
        {selectedThread && (
          <div className="border-t bg-white/80 backdrop-blur-sm flex-shrink-0">
            <ChatInput
              onSendMessage={(message) => sendMessage(message)}
              onStopGeneration={() => {/* TODO: Implement stop generation */}}
              isLoading={sendingMessage}
            />
          </div>
        )}

        {/* Enhanced Mobile Navigation */}
        {selectedThread && selectedThread.thread_id && (
          <div className="lg:hidden border-t bg-white/90 backdrop-blur-sm flex-shrink-0">
            <div className="p-3">
              <Button
                variant="outline"
                size="sm"
                onClick={createNewThread}
                className="w-full bg-white hover:bg-slate-50"
              >
                <ChevronLeft className="h-4 w-4 mr-2" />
                Back to Conversations
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Enhanced Files Dialog */}
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
            {/* Enhanced Files List */}
            <div className="w-80 border-r border-slate-200 pr-6 flex flex-col">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-slate-800 text-lg">File Explorer</h3>
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 w-8 p-0 text-slate-500 hover:text-slate-700"
                  >
                    <RefreshCw className="h-4 w-4" />
                  </Button>
                </div>
              </div>
              
              <ScrollArea className="flex-1">
                {loadingGenerations || loadingFiles ? (
                  <div className="flex items-center justify-center p-8">
                    <div className="text-center space-y-3">
                      <Loader2 className="h-8 w-8 animate-spin text-blue-500 mx-auto" />
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
                          onClick={() => selectFile(file)}
                          className={`p-3 rounded-xl border text-sm transition-all duration-200 cursor-pointer group ${
                            selectedFile?.path === file.path
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
                                    downloadFile(selectedGeneration.generation_id, file.path);
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
              </ScrollArea>
            </div>

            {/* Enhanced Code Editor */}
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
                        className="bg-white hover:bg-slate-50 border-slate-300"
                      >
                        <Edit3 className="h-4 w-4 mr-2" />
                        Edit
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          if (selectedGeneration) {
                            downloadFile(selectedGeneration.generation_id, selectedFile.path);
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
                    {loadingContent ? (
                      <div className="flex items-center justify-center h-full bg-slate-50">
                        <div className="text-center space-y-4">
                          <Loader2 className="h-8 w-8 animate-spin text-blue-500 mx-auto" />
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
    </div>
  );
};