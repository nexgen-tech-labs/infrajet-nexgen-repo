-- Create enum for user roles
CREATE TYPE public.user_role AS ENUM (
  'Devops Engineer',
  'SRE',
  'Infrastructure Engineer', 
  'Cloud Engineer',
  'Lead Engineer',
  'Cloud Specialist'
);

-- Add new columns to profiles table
ALTER TABLE public.profiles 
ADD COLUMN role public.user_role,
ADD COLUMN organization TEXT,
ADD COLUMN linkedin_profile TEXT;