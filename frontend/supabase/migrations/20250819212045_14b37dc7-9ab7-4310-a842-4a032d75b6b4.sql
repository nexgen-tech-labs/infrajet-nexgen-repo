-- Create user_github_connections table if it doesn't exist
CREATE TABLE IF NOT EXISTS public.user_github_connections (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  github_user_id BIGINT NOT NULL,
  github_username TEXT NOT NULL,
  github_name TEXT,
  github_avatar_url TEXT,
  access_token_encrypted TEXT NOT NULL,
  selected_repo_full_name TEXT,
  selected_repo_name TEXT,
  selected_repo_private BOOLEAN DEFAULT false,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(user_id)
);

-- Enable RLS
ALTER TABLE public.user_github_connections ENABLE ROW LEVEL SECURITY;

-- Create policies
CREATE POLICY "Users can view their own GitHub connections" 
ON public.user_github_connections 
FOR SELECT 
USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own GitHub connections" 
ON public.user_github_connections 
FOR INSERT 
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own GitHub connections" 
ON public.user_github_connections 
FOR UPDATE 
USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own GitHub connections" 
ON public.user_github_connections 
FOR DELETE 
USING (auth.uid() = user_id);

-- Create trigger for automatic timestamp updates
CREATE TRIGGER update_user_github_connections_updated_at
BEFORE UPDATE ON public.user_github_connections
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();