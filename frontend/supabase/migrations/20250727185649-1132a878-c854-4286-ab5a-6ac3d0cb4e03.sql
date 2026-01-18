
-- Create a terms_acceptances table to track when users accept terms
CREATE TABLE public.terms_acceptances (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  terms_version TEXT NOT NULL DEFAULT '1.0',
  accepted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  ip_address TEXT,
  user_agent TEXT,
  UNIQUE(user_id, terms_version)
);

-- Enable RLS on terms_acceptances table
ALTER TABLE public.terms_acceptances ENABLE ROW LEVEL SECURITY;

-- Create policy for users to view their own terms acceptances
CREATE POLICY "Users can view their own terms acceptances"
  ON public.terms_acceptances
  FOR SELECT
  USING (auth.uid() = user_id);

-- Create policy for users to insert their own terms acceptances
CREATE POLICY "Users can insert their own terms acceptances"
  ON public.terms_acceptances
  FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- Create a trigger to automatically update the profiles table when users sign up
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  INSERT INTO public.profiles (id, full_name, business_email)
  VALUES (
    NEW.id,
    COALESCE(NEW.raw_user_meta_data->>'full_name', ''),
    COALESCE(NEW.email, '')
  );
  RETURN NEW;
END;
$$;

-- Create trigger for new user signup
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_new_user();
