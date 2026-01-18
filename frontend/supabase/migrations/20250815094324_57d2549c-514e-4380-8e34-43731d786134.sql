-- Hash existing admin passwords and improve security
-- First, let's create a function to hash passwords using pgcrypto
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Update the existing admin user with a properly hashed password
UPDATE admin_users 
SET password_hash = crypt('admin123', gen_salt('bf', 12))
WHERE email = 'admin@admin.com';

-- Create a function to verify admin passwords
CREATE OR REPLACE FUNCTION public.verify_admin_password(input_email text, input_password text)
RETURNS TABLE(admin_id uuid, email text, full_name text, role admin_role, is_active boolean)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  RETURN QUERY
  SELECT au.id, au.email, au.full_name, au.role, au.is_active
  FROM admin_users au
  WHERE au.email = input_email 
    AND au.password_hash = crypt(input_password, au.password_hash)
    AND au.is_active = true;
END;
$$;

-- Create a function to get current admin user from JWT
CREATE OR REPLACE FUNCTION public.get_current_admin_user()
RETURNS TABLE(admin_id uuid, email text, full_name text, role admin_role, is_active boolean)
LANGUAGE plpgsql
SECURITY DEFINER
STABLE
AS $$
BEGIN
  RETURN QUERY
  SELECT au.id, au.email, au.full_name, au.role, au.is_active
  FROM admin_users au
  WHERE au.id = auth.uid()
    AND au.is_active = true;
END;
$$;

-- Create audit log function for admin actions
CREATE OR REPLACE FUNCTION public.log_admin_action(
  action_type text,
  resource_type text,
  resource_id uuid DEFAULT NULL,
  old_values jsonb DEFAULT NULL,
  new_values jsonb DEFAULT NULL
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  admin_user_id uuid;
BEGIN
  -- Get current admin user ID
  SELECT id INTO admin_user_id FROM admin_users WHERE id = auth.uid() AND is_active = true;
  
  IF admin_user_id IS NOT NULL THEN
    INSERT INTO admin_audit_logs (
      admin_id,
      action,
      resource_type,
      resource_id,
      old_values,
      new_values,
      ip_address,
      user_agent
    ) VALUES (
      admin_user_id,
      action_type,
      resource_type,
      resource_id,
      old_values,
      new_values,
      current_setting('request.headers', true)::json->>'x-forwarded-for',
      current_setting('request.headers', true)::json->>'user-agent'
    );
  END IF;
END;
$$;