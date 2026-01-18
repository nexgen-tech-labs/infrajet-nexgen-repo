import React from 'react';
import { GitHubSyncManager } from './GitHubSyncManager';

interface GitHubIntegrationProps {
    projectId: string;
    githubToken?: string;
    className?: string;
}

export const GitHubIntegration: React.FC<GitHubIntegrationProps> = ({
    projectId,
    githubToken,
    className,
}) => {
    return (
        <GitHubSyncManager
            className={className}
            projectId={projectId}
            githubToken={githubToken}
        />
    );
};