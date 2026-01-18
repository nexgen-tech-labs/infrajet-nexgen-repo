import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Github, Wifi, WifiOff } from 'lucide-react';
import { useGitHub } from '@/contexts/GitHubContext';
import { GitHubSyncManager } from './GitHubSyncManager';

interface GitHubConnectButtonProps {
    className?: string;
}

export const GitHubConnectButton: React.FC<GitHubConnectButtonProps> = ({ className }) => {
    const { isConnected, githubUser, loading } = useGitHub();
    const [isDialogOpen, setIsDialogOpen] = useState(false);

    return (
        <>
            <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                <DialogTrigger asChild>
                    <Button
                        variant="outline"
                        size="sm"
                        className={`flex items-center gap-2 ${className}`}
                        disabled={loading}
                    >
                        <Github className="h-4 w-4" />
                        <span className="hidden sm:inline">
                            {isConnected ? 'GitHub Connected' : 'Connect to GitHub'}
                        </span>
                        <Badge
                            variant={isConnected ? "default" : "secondary"}
                            className="flex items-center gap-1 ml-1"
                        >
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
                    </Button>
                </DialogTrigger>

                <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <Github className="h-5 w-5" />
                            GitHub Integration
                            {isConnected && githubUser && (
                                <Badge variant="outline" className="ml-2">
                                    @{githubUser.login}
                                </Badge>
                            )}
                        </DialogTitle>
                    </DialogHeader>

                    <div className="overflow-y-auto max-h-[calc(90vh-120px)]">
                        <GitHubSyncManager />
                    </div>
                </DialogContent>
            </Dialog>
        </>
    );
};