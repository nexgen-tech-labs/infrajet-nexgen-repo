-- Fix security vulnerability: Restrict contact_submissions access to admin users only
DROP POLICY IF EXISTS "Only authenticated users can view contact submissions" ON public.contact_submissions;

-- Create new policy that restricts access to admin users only
CREATE POLICY "Only admin users can view contact submissions" 
ON public.contact_submissions 
FOR SELECT 
USING (EXISTS (
  SELECT 1 
  FROM public.admin_users 
  WHERE admin_users.id = auth.uid() 
  AND admin_users.is_active = true
));