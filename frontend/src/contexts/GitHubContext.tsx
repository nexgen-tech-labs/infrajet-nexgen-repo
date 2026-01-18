
import React, { createContext, useContext, useEffect, useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { GitHubRepo, GitHubUser } from '@/services/githubService';
import { supabase } from '@/integrations/supabase/client';
import { githubApi, GitHubRepository } from '@/services/infrajetApi';

interface GitHubContextType {
  isConnected: boolean;
  githubUser: GitHubUser | null;
  selectedRepo: GitHubRepository | null;
  repos: GitHubRepository[];
  organizations: any[];
  selectedOrganization: string;
  connectToGitHub: () => Promise<void>;
  disconnectFromGitHub: () => Promise<void>;
  selectRepo: (repo: GitHubRepository) => void;
  selectOrganization: (org: string) => void;
  refreshRepos: () => Promise<void>;
  pushCode: (files: { path: string; content: string }[], commitMessage: string) => Promise<void>;
  loading: boolean;
}

const GitHubContext = createContext<GitHubContextType | undefined>(undefined);

export const useGitHub = () => {
  const context = useContext(GitHubContext);
  if (context === undefined) {
    throw new Error('useGitHub must be used within a GitHubProvider');
  }
  return context;
};

export const GitHubProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user } = useAuth();
  const [isConnected, setIsConnected] = useState(false);
  const [githubUser, setGithubUser] = useState<GitHubUser | null>(null);
  const [selectedRepo, setSelectedRepo] = useState<GitHubRepository | null>(null);
  const [repos, setRepos] = useState<GitHubRepository[]>([]);
  const [organizations, setOrganizations] = useState<any[]>([]);
  const [selectedOrganization, setSelectedOrganization] = useState<string>('personal');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (user) {
      loadGitHubConnection();
    }
  }, [user]);

  const loadGitHubConnection = async () => {
    try {
      // First, check backend status (primary source of truth)
      try {
        const backendStatus = await githubApi.getStatus();

        if (backendStatus.data?.connected) {
          setIsConnected(true);
          setGithubUser({
            id: backendStatus.data.installation_id || 0,
            login: backendStatus.data.username || '',
            avatar_url: '',
            name: backendStatus.data.username || ''
          });
          // Load repos if connected
          refreshRepos();
          return;
        }
      } catch (backendError) {
        console.warn('Backend status check failed, falling back to database:', backendError);
      }

      // Fallback to database check
      const { data, error } = await (supabase as any)
        .from('user_github_connections')
        .select('*')
        .eq('user_id', user?.id)
        .single();

      if (error && error.code !== 'PGRST116') {
        console.error('Error loading GitHub connection from database:', error);
        return;
      }

      if (data) {
        setIsConnected(true);
        setGithubUser(data.github_user as GitHubUser);
        setOrganizations(data.organizations || []);

        if (data.selected_repo) {
          setSelectedRepo(data.selected_repo as GitHubRepository);
        }
      } else {
        setIsConnected(false);
        setGithubUser(null);
      }
    } catch (error) {
      console.error('Error loading GitHub connection:', error);
    }
  };

  const connectToGitHub = async () => {
    try {
      // Get the GitHub client ID from Supabase function
      const { data, error } = await supabase.functions.invoke('github-config');
      
      if (error || !data?.clientId) {
        throw new Error('GitHub configuration not available');
      }

      const redirectUri = `${window.location.origin}/auth/github/callback`;
      const scope = 'repo,user,read:org';
      
      const authUrl = `https://github.com/login/oauth/authorize?client_id=${data.clientId}&redirect_uri=${redirectUri}&scope=${scope}`;
      window.location.href = authUrl;
    } catch (error) {
      console.error('Error initiating GitHub OAuth:', error);
      throw error;
    }
  };

  const disconnectFromGitHub = async () => {
    try {
      await (supabase as any)
        .from('user_github_connections')
        .delete()
        .eq('user_id', user?.id);

      setIsConnected(false);
      setGithubUser(null);
      setSelectedRepo(null);
      setRepos([]);
      setOrganizations([]);
      setSelectedOrganization('personal');
    } catch (error) {
      console.error('Error disconnecting from GitHub:', error);
    }
  };

  const selectRepo = (repo: GitHubRepository) => {
    setSelectedRepo(repo);

    try {
      (supabase as any)
        .from('user_github_connections')
        .update({ selected_repo: repo as any })
        .eq('user_id', user?.id);
    } catch (error) {
      console.error('Error saving selected repo:', error);
    }
  };

  const selectOrganization = (org: string) => {
    setSelectedOrganization(org);
    setRepos([]); // Clear repos when switching organization
    setSelectedRepo(null); // Clear selected repo when switching organization
  };

  const refreshRepos = async () => {
    setLoading(true);
    try {
      const response = await githubApi.getRepositories();

      setRepos(response.data.repositories || []);
    } catch (error) {
      console.error('Error refreshing repos:', error);
      // Don't throw error to avoid breaking the UI
    } finally {
      setLoading(false);
    }
  };

  const pushCode = async (files: { path: string; content: string }[], commitMessage: string) => {
    if (!selectedRepo) {
      throw new Error('GitHub not connected or no repository selected');
    }

    setLoading(true);
    try {
      const { data, error } = await supabase.functions.invoke('github-push', {
        body: {
          repoFullName: selectedRepo.full_name,
          files,
          commitMessage
        }
      });

      if (error) {
        throw new Error(`Failed to push code: ${error.message}`);
      }

      return data;
    } catch (error) {
      console.error('Error pushing code:', error);
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const value = {
    isConnected,
    githubUser,
    selectedRepo,
    repos,
    organizations,
    selectedOrganization,
    connectToGitHub,
    disconnectFromGitHub,
    selectRepo,
    selectOrganization,
    refreshRepos,
    pushCode,
    loading,
  };

  return <GitHubContext.Provider value={value}>{children}</GitHubContext.Provider>;
};
