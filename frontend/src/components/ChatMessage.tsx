
import { Copy, Check, User, Bot, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { useState } from "react";
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import CodeEditor from "@/components/CodeEditor";

interface ChatMessageProps {
  message: string;
  isUser: boolean;
  isCode?: boolean;
  language?: string;
}

const ChatMessage = ({ message, isUser, isCode, language }: ChatMessageProps) => {
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
        const detectedLanguage = firstLineEnd > 0 ? codeContent.slice(0, firstLineEnd).trim() : '';
        const code = firstLineEnd > 0 ? codeContent.slice(firstLineEnd + 1) : codeContent;

        return (
          <div key={index} className="relative my-2">
            <div className="bg-slate-900 rounded-lg overflow-hidden">
              <div className="flex items-center justify-between px-3 py-2 bg-slate-800">
                <span className="text-xs text-slate-400">{detectedLanguage || 'text'}</span>
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
                language={detectedLanguage || 'text'}
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
          <Dialog key={index}>
            <DialogTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="mx-1 h-6 text-xs bg-blue-50 hover:bg-blue-100 border-blue-200 text-blue-700"
              >
                <FileText className="w-3 h-3 mr-1" />
                {fileName}
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-4xl max-h-[80vh]">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <FileText className="w-4 h-4" />
                  {fileName}
                </DialogTitle>
              </DialogHeader>
              <div className="h-[60vh]">
                  <CodeEditor
                      value=""
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
    <div className="flex gap-3 p-4 bg-slate-700 rounded-lg">
      <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
        isUser ? "bg-blue-600" : "bg-gradient-to-r from-purple-600 to-blue-600"
      }`}>
        {isUser ? <User className="w-4 h-4 text-white" /> : <Bot className="w-4 h-4 text-white" />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm font-medium text-slate-300">
            {isUser ? "You" : "infraJet"}
          </span>
          {language && (
            <span className="text-xs bg-slate-700 text-slate-300 px-2 py-1 rounded">
              {language}
            </span>
          )}
        </div>
        <div className="relative">
          {isCode ? (
            <div className="bg-slate-900 border border-slate-700 rounded-lg p-3 overflow-x-auto">
              <pre className="text-sm text-slate-300 whitespace-pre-wrap">
                <code>{message}</code>
              </pre>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleCopyCode(message)}
                className="absolute top-2 right-2 h-8 w-8 p-0 hover:bg-slate-700"
              >
                {copiedCode === message ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4 text-slate-400" />}
              </Button>
            </div>
          ) : (
            <div className="text-slate-300 whitespace-pre-wrap">
              {renderMessageContent(message)}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ChatMessage;
