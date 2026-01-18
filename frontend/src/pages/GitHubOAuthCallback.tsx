import React, { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Loader2 } from 'lucide-react';

const GitHubOAuthCallback = () => {
  const [searchParams] = useSearchParams();

  useEffect(() => {
    const handleCallback = () => {
      const code = searchParams.get('code');
      const state = searchParams.get('state');
      const error = searchParams.get('error');

      if (error) {
        // Send error back to parent window
        window.opener?.postMessage({
          type: 'github_oauth_callback',
          error: error,
          error_description: searchParams.get('error_description')
        }, window.location.origin);
        window.close();
        return;
      }

      if (code && state) {
        // Send success data back to parent window
        window.opener?.postMessage({
          type: 'github_oauth_callback',
          code: code,
          state: state
        }, window.location.origin);
        window.close();
      } else {
        // No code or state - this shouldn't happen
        window.opener?.postMessage({
          type: 'github_oauth_callback',
          error: 'no_code',
          error_description: 'No authorization code received'
        }, window.location.origin);
        window.close();
      }
    };

    // Small delay to ensure parent window is ready to receive messages
    const timer = setTimeout(handleCallback, 100);

    return () => clearTimeout(timer);
  }, [searchParams]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center">
      <div className="text-center space-y-4">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500 mx-auto" />
        <h2 className="text-xl font-semibold text-slate-300">
          Completing GitHub Authorization...
        </h2>
        <p className="text-slate-400">
          Please wait while we connect your GitHub account.
        </p>
      </div>
    </div>
  );
};

export default GitHubOAuthCallback;