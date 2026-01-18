-- Create the admin user in auth.users table to match the admin_users entry
-- This allows the admin to sign in with Supabase Auth

-- First, let's create the auth user for the admin
INSERT INTO auth.users (
    id,
    instance_id,
    aud,
    role,
    email,
    encrypted_password,
    email_confirmed_at,
    created_at,
    updated_at,
    confirmation_token,
    email_change,
    email_change_token_new,
    recovery_token,
    confirmation_sent_at,
    recovery_sent_at,
    email_change_token_current,
    email_change_confirm_status,
    banned_until,
    delete_at,
    is_sso_user,
    raw_app_meta_data,
    raw_user_meta_data,
    is_super_admin,
    phone,
    phone_confirmed_at,
    phone_change,
    phone_change_token,
    phone_change_sent_at,
    email_change_sent_at,
    is_anonymous
) VALUES (
    'a599f933-56c0-4953-bba5-90b3d0b75d04',
    '00000000-0000-0000-0000-000000000000',
    'authenticated',
    'authenticated',
    'admin@admin.com',
    '$2a$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', -- This is the hash for 'admin123'
    NOW(),
    NOW(),
    NOW(),
    '',
    '',
    '',
    '',
    NOW(),
    NOW(),
    '',
    0,
    NULL,
    NULL,
    false,
    '{"provider":"email","providers":["email"]}',
    '{"full_name":"System Administrator","role":"super_admin"}',
    false,
    NULL,
    NULL,
    '',
    '',
    NULL,
    NULL,
    false
) ON CONFLICT (id) DO NOTHING;

-- Create identity for email authentication
INSERT INTO auth.identities (
    provider_id,
    user_id,
    identity_data,
    provider,
    last_sign_in_at,
    created_at,
    updated_at,
    email
) VALUES (
    'admin@admin.com',
    'a599f933-56c0-4953-bba5-90b3d0b75d04',
    '{"sub":"a599f933-56c0-4953-bba5-90b3d0b75d04","email":"admin@admin.com","email_verified":true,"phone_verified":false}',
    'email',
    NOW(),
    NOW(),
    NOW(),
    'admin@admin.com'
) ON CONFLICT (provider, provider_id) DO NOTHING;