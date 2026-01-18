
import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { useGitHub } from '@/contexts/GitHubContext';
import { useToast } from '@/components/ui/use-toast';
import { Github, Upload, Loader2 } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';

interface PushToGitHubButtonProps {
  code: string;
  provider: string;
  filename?: string;
}

const PushToGitHubButton: React.FC<PushToGitHubButtonProps> = ({ 
  code, 
  provider, 
  filename 
}) => {
  const { isConnected, selectedRepo, pushCode, loading } = useGitHub();
  const { toast } = useToast();
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [commitMessage, setCommitMessage] = useState('');
  const [customFilename, setCustomFilename] = useState(filename || '');

  const getDefaultFilename = () => {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const extension = provider === 'terraform' ? 'tf' : 'yaml';
    return `${provider}-infrastructure-${timestamp}.${extension}`;
  };

  const handlePushToGitHub = async () => {
    if (!commitMessage.trim()) {
      toast({
        title: "Error",
        description: "Commit message is required",
        variant: "destructive",
      });
      return;
    }

    const finalFilename = customFilename || getDefaultFilename();
    
    try {
      await pushCode([
        {
          path: `infrastructure/${finalFilename}`,
          content: code
        }
      ], commitMessage);

      toast({
        title: "Success",
        description: "Code pushed to GitHub successfully!",
      });
      
      setIsDialogOpen(false);
      setCommitMessage('');
      setCustomFilename('');
    } catch (error) {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    }
  };

  if (!isConnected || !selectedRepo) {
    return null;
  }

  return (
    <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
      <DialogTrigger asChild>
        <Button 
          variant="outline" 
          className="border-slate-600 hover:bg-slate-700 text-slate-200"
        >
          <Upload className="w-4 h-4 mr-2" />
          Push to GitHub
        </Button>
      </DialogTrigger>
      <DialogContent className="bg-slate-800 border-slate-700">
        <DialogHeader>
          <DialogTitle className="text-slate-200">Push to GitHub</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="p-3 rounded-lg bg-slate-700/50">
            <p className="text-sm text-slate-400">Repository:</p>
            <p className="text-slate-200">{selectedRepo.full_name}</p>
          </div>
          
          <div>
            <Label htmlFor="filename" className="text-slate-200">Filename</Label>
            <Input
              id="filename"
              value={customFilename}
              onChange={(e) => setCustomFilename(e.target.value)}
              placeholder={getDefaultFilename()}
              className="bg-slate-700 border-slate-600 text-slate-200"
            />
          </div>
          
          <div>
            <Label htmlFor="commit-message" className="text-slate-200">Commit Message</Label>
            <Textarea
              id="commit-message"
              value={commitMessage}
              onChange={(e) => setCommitMessage(e.target.value)}
              placeholder="Add generated infrastructure code"
              className="bg-slate-700 border-slate-600 text-slate-200"
            />
          </div>
          
          <div className="flex gap-2">
            <Button 
              onClick={handlePushToGitHub} 
              disabled={loading}
              className="flex-1"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Upload className="w-4 h-4 mr-2" />
              )}
              Push to GitHub
            </Button>
            <Button 
              variant="outline" 
              onClick={() => setIsDialogOpen(false)}
              className="border-slate-600"
            >
              Cancel
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default PushToGitHubButton;
