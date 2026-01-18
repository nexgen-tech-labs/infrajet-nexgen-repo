-- Fix promotional codes security issue by adding explicit access restrictions

-- Drop existing broad policy
DROP POLICY IF EXISTS "Admin users can manage promo_codes" ON public.promo_codes;

-- Create specific policies for promo_codes table

-- 1. Only admin users can view promo codes
CREATE POLICY "Admin users can view promo_codes" 
ON public.promo_codes 
FOR SELECT 
USING (
  EXISTS (
    SELECT 1 
    FROM admin_users 
    WHERE id = auth.uid() AND is_active = true
  )
);

-- 2. Only admin users can create promo codes
CREATE POLICY "Admin users can create promo_codes" 
ON public.promo_codes 
FOR INSERT 
WITH CHECK (
  EXISTS (
    SELECT 1 
    FROM admin_users 
    WHERE id = auth.uid() AND is_active = true
  )
);

-- 3. Only admin users can update promo codes
CREATE POLICY "Admin users can update promo_codes" 
ON public.promo_codes 
FOR UPDATE 
USING (
  EXISTS (
    SELECT 1 
    FROM admin_users 
    WHERE id = auth.uid() AND is_active = true
  )
);

-- 4. Only admin users can delete promo codes
CREATE POLICY "Admin users can delete promo_codes" 
ON public.promo_codes 
FOR DELETE 
USING (
  EXISTS (
    SELECT 1 
    FROM admin_users 
    WHERE id = auth.uid() AND is_active = true
  )
);

-- 5. Explicit denial policy for all other users (including anonymous)
CREATE POLICY "Deny public access to promo_codes" 
ON public.promo_codes 
FOR ALL 
USING (false);

-- Ensure RLS is enabled
ALTER TABLE public.promo_codes ENABLE ROW LEVEL SECURITY;