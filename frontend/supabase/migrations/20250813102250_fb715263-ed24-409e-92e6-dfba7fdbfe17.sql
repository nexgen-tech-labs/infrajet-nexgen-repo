-- Fix GitHub token security vulnerability
-- Remove client access to access_token field by creating a secure view

-- Create a view that excludes the sensitive access_token field
CREATE VIEW public.user_github_connections_secure AS
SELECT 
  id,
  user_id,
  github_user_id,
  github_user,
  selected_repo,
  created_at,
  updated_at,
  github_username
FROM public.user_github_connections;

-- Enable RLS on the view
ALTER VIEW public.user_github_connections_secure SET (security_invoker = true);

-- Drop existing policies on the main table
DROP POLICY IF EXISTS "Users can view their own GitHub connections" ON public.user_github_connections;
DROP POLICY IF EXISTS "Users can create their own GitHub connections" ON public.user_github_connections;
DROP POLICY IF EXISTS "Users can update their own GitHub connections" ON public.user_github_connections;
DROP POLICY IF EXISTS "Users can delete their own GitHub connections" ON public.user_github_connections;

-- Restrict main table access to server-side only (edge functions)
CREATE POLICY "Server-side access only for GitHub connections"
ON public.user_github_connections
FOR ALL
USING (false)
WITH CHECK (false);

-- Create secure policies for the view (no access to access_token)
CREATE POLICY "Users can view their own GitHub connections (secure)"
ON public.user_github_connections_secure
FOR SELECT
USING (auth.uid() = user_id);

-- For insert/update/delete operations, we'll handle them through edge functions
-- but we need to allow the functions to access the main table
CREATE POLICY "Edge functions can manage GitHub connections"
ON public.user_github_connections
FOR ALL
USING (auth.jwt() ->> 'role' = 'service_role')
WITH CHECK (auth.jwt() ->> 'role' = 'service_role');