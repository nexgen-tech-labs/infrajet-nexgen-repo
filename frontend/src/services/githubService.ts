
import { supabase } from "@/integrations/supabase/client";

export interface GitHubRepo {
  id: number;
  name: string;
  full_name: string;
  private: boolean;
  html_url: string;
  default_branch: string;
}

export interface GitHubUser {
  id: number;
  login: string;
  avatar_url: string;
  name: string;
}

export const getGitHubAuthUrl = async () => {
  try {
    const { data } = await supabase.functions.invoke('github-config');
    const redirectUri = `${window.location.origin}/auth/github/callback`;
    const scope = 'repo,user,read:org';
    
    return `https://github.com/login/oauth/authorize?client_id=${data.clientId}&redirect_uri=${redirectUri}&scope=${scope}`;
  } catch (error) {
    console.error('Error getting GitHub auth URL:', error);
    throw error;
  }
};

export const exchangeCodeForToken = async (code: string) => {
  const { data, error } = await supabase.functions.invoke('github-auth', {
    body: { code }
  });

  if (error) {
    throw new Error(`GitHub authentication failed: ${error.message}`);
  }

  return data;
};

export const getUserRepos = async (token: string): Promise<GitHubRepo[]> => {
  const { data, error } = await supabase.functions.invoke('github-repos', {
    body: { token, action: 'list' }
  });

  if (error) {
    throw new Error(`Failed to fetch repositories: ${error.message}`);
  }

  return data.repos || [];
};

export const createRepo = async (token: string, name: string, description: string, isPrivate: boolean = false, organization?: string) => {
  const { data, error } = await supabase.functions.invoke('github-repos', {
    body: { 
      token, 
      action: 'create',
      name,
      description,
      private: isPrivate,
      organization
    }
  });

  if (error) {
    throw new Error(`Failed to create repository: ${error.message}`);
  }

  return data.repo;
};

export const pushCodeToRepo = async (token: string, repoFullName: string, files: { path: string; content: string }[], commitMessage: string) => {
  const { data, error } = await supabase.functions.invoke('github-push', {
    body: {
      token,
      repoFullName,
      files,
      commitMessage
    }
  });

  if (error) {
    throw new Error(`Failed to push code: ${error.message}`);
  }

  return data;
};
