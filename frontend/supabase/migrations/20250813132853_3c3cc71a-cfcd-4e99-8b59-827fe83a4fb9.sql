-- Create admin user in the auth system properly
-- We'll use the service role to create the admin user

DO $$
DECLARE
    admin_user_id uuid := 'a599f933-56c0-4953-bba5-90b3d0b75d04';
    admin_email text := 'admin@admin.com';
    admin_password_hash text := '$2a$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi';
BEGIN
    -- Insert into auth.users with minimal required fields
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
        raw_app_meta_data,
        raw_user_meta_data,
        is_super_admin
    ) VALUES (
        admin_user_id,
        '00000000-0000-0000-0000-000000000000',
        'authenticated',
        'authenticated',
        admin_email,
        admin_password_hash,
        NOW(),
        NOW(),
        NOW(),
        '{"provider":"email","providers":["email"]}',
        '{"full_name":"System Administrator","role":"super_admin"}',
        false
    ) ON CONFLICT (id) DO NOTHING;

    -- Insert into auth.identities for email authentication
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
        admin_email,
        admin_user_id,
        format('{"sub":"%s","email":"%s","email_verified":true,"phone_verified":false}', admin_user_id, admin_email)::jsonb,
        'email',
        NOW(),
        NOW(),
        NOW(),
        admin_email
    ) ON CONFLICT (provider, provider_id) DO NOTHING;
END $$;