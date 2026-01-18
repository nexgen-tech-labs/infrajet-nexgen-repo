import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Send, Square, Paperclip, Smile, Zap, Loader2 } from "lucide-react";
import { useState, useRef, useEffect } from "react";

interface ChatInputProps {
  onSendMessage: (message: string) => void;
  onStopGeneration: () => void;
  isLoading: boolean;
}

const ChatInput = ({
  onSendMessage,
  onStopGeneration,
  isLoading
}: ChatInputProps) => {
  const [message, setMessage] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  
  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [message]);
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isLoading) {
      onStopGeneration();
    } else if (message.trim()) {
      onSendMessage(message.trim());
      setMessage("");
    }
  };
  
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const quickPrompts = [
    "Create an S3 bucket with versioning",
    "Set up a VPC with public and private subnets",
    "Deploy an ECS cluster with load balancer",
    "Create a Lambda function with API Gateway"
  ];

  const handleQuickPrompt = (prompt: string) => {
    setMessage(prompt);
    textareaRef.current?.focus();
  };
  
  return (
    <div className="border-t bg-white/95 backdrop-blur-sm">
      <div className="p-4 space-y-4">
        {/* Quick Prompts */}
        {!isLoading && message.length === 0 && (
          <div className="space-y-2">
            <p className="text-xs font-medium text-slate-600">Quick prompts:</p>
            <div className="flex flex-wrap gap-2">
              {quickPrompts.map((prompt, index) => (
                <Button
                  key={index}
                  variant="outline"
                  size="sm"
                  onClick={() => handleQuickPrompt(prompt)}
                  className="text-xs h-7 px-3 bg-slate-50 hover:bg-slate-100 border-slate-200 text-slate-700"
                >
                  <Zap className="w-3 h-3 mr-1" />
                  {prompt}
                </Button>
              ))}
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex gap-3">
          <div className="flex-1 relative">
            <Textarea 
              ref={textareaRef}
              value={message} 
              onChange={(e) => setMessage(e.target.value)} 
              onKeyPress={handleKeyPress} 
              placeholder="Describe the infrastructure you need... (Press Enter to send, Shift+Enter for new line)" 
              disabled={isLoading} 
              className="min-h-[44px] max-h-[120px] resize-none pr-12 bg-white border-slate-200 focus:border-blue-300 focus:ring-1 focus:ring-blue-200 rounded-xl" 
            />
            
            {/* Input Actions */}
            <div className="absolute right-2 bottom-2 flex items-center gap-1">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0 text-slate-400 hover:text-slate-600"
                disabled={isLoading}
              >
                <Paperclip className="w-3 h-3" />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0 text-slate-400 hover:text-slate-600"
                disabled={isLoading}
              >
                <Smile className="w-3 h-3" />
              </Button>
            </div>
          </div>
          
          <Button 
            type="submit" 
            disabled={!isLoading && !message.trim()} 
            variant={isLoading ? "destructive" : "default"}
            size="lg"
            className="px-6 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300"
          >
            {isLoading ? (
              <>
                <Square className="w-4 h-4 mr-2" />
                Stop
              </>
            ) : (
              <>
                <Send className="w-4 h-4 mr-2" />
                Send
              </>
            )}
          </Button>
        </form>
        
        {/* Status and Tips */}
        <div className="flex items-center justify-between text-xs text-slate-500">
          <div className="flex items-center gap-4">
            {isLoading && (
              <div className="flex items-center gap-2">
                <Loader2 className="w-3 h-3 animate-spin text-blue-500" />
                <span>Generating response...</span>
              </div>
            )}
            {!isLoading && message.length > 0 && (
              <span>{message.length} characters</span>
            )}
          </div>
          
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-xs px-2 py-0.5">
              <Zap className="w-3 h-3 mr-1" />
              AI Powered
            </Badge>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatInput;