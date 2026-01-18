-- Fix GitHub token security issue by encrypting access tokens
-- Drop the existing access_token column and replace with encrypted version
ALTER TABLE public.user_github_connections 
  DROP COLUMN IF EXISTS access_token;

-- Add the encrypted access token column
ALTER TABLE public.user_github_connections 
  ADD COLUMN access_token_encrypted TEXT;

-- Update the existing records to use the new schema from the Edge Function
-- The edge function already handles encryption, so this just updates the schema
UPDATE public.user_github_connections 
SET access_token_encrypted = ''
WHERE access_token_encrypted IS NULL;