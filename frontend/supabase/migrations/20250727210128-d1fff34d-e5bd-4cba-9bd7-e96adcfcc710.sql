-- Create table for storing GitHub connections
CREATE TABLE public.user_github_connections (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  github_user_id INTEGER NOT NULL,
  github_username TEXT NOT NULL,
  access_token TEXT NOT NULL,
  github_user JSONB NOT NULL,
  selected_repo JSONB,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  UNIQUE(user_id)
);

-- Enable Row Level Security
ALTER TABLE public.user_github_connections ENABLE ROW LEVEL SECURITY;

-- Create policies for user access
CREATE POLICY "Users can view their own GitHub connections" 
ON public.user_github_connections 
FOR SELECT 
USING (auth.uid() = user_id);

CREATE POLICY "Users can create their own GitHub connections" 
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

-- Create function to update timestamps
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for automatic timestamp updates
CREATE TRIGGER update_user_github_connections_updated_at
  BEFORE UPDATE ON public.user_github_connections
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();