
import React, { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { githubApi } from '@/services/infrajetApi';
import { useToast } from '@/components/ui/use-toast';
import { Loader2 } from 'lucide-react';

const GitHubCallback = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user, loading } = useAuth();
  const { toast } = useToast();

  useEffect(() => {
    // Wait for auth loading to complete
    if (loading) {
      return;
    }

    const handleGitHubCallback = async () => {
      const code = searchParams.get('code');
      const error = searchParams.get('error');

      // Clear the URL to prevent code reuse on refresh
      if (code || error) {
        const url = new URL(window.location.href);
        url.searchParams.delete('code');
        url.searchParams.delete('error');
        window.history.replaceState({}, document.title, url.pathname + url.search);
      }

      if (error) {
        toast({
          title: "GitHub Connection Failed",
          description: error,
          variant: "destructive",
        });
        navigate('/');
        return;
      }

      if (!code) {
        toast({
          title: "GitHub Connection Failed",
          description: "No authorization code received",
          variant: "destructive",
        });
        navigate('/');
        return;
      }

      if (!user) {
        toast({
          title: "Authentication Required",
          description: "Please log in first",
          variant: "destructive",
        });
        navigate('/auth');
        return;
      }

      try {
        // Exchange code for access token via backend API
        const response = await githubApi.connect({ code });

        toast({
          title: "GitHub Connected",
          description: response.message || "Successfully connected to GitHub!",
        });

        navigate('/');
      } catch (error: any) {
        console.error('GitHub callback error:', error);

        // Handle specific error cases
        let errorMessage = error.message;
        if (error.message?.includes('incorrect or expired')) {
          errorMessage = "The authorization code has expired. Please try connecting to GitHub again.";
        }

        toast({
          title: "GitHub Connection Failed",
          description: errorMessage,
          variant: "destructive",
        });
        navigate('/');
      }
    };

    handleGitHubCallback();
  }, [searchParams, navigate, user, toast, loading]);

  // Show loading while auth state is being determined
  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center">
        <div className="text-center space-y-4">
          <Loader2 className="h-8 w-8 animate-spin text-blue-500 mx-auto" />
          <h2 className="text-xl font-semibold text-slate-300">
            Loading...
          </h2>
          <p className="text-slate-400">
            Checking authentication status.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center">
      <div className="text-center space-y-4">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500 mx-auto" />
        <h2 className="text-xl font-semibold text-slate-300">
          Connecting to GitHub...
        </h2>
        <p className="text-slate-400">
          Please wait while we set up your GitHub integration.
        </p>
      </div>
    </div>
  );
};

export default GitHubCallback;
