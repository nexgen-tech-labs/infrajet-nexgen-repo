import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.52.1';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

const supabase = createClient(
  Deno.env.get('SUPABASE_URL') ?? '',
  Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
);

serve(async (req) => {
  // Handle CORS preflight requests
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const { email, password, action } = await req.json();

    if (action === 'login') {
      console.log('Admin login attempt for:', email);
      
      // Verify admin credentials using the secure function
      const { data: adminData, error: verifyError } = await supabase
        .rpc('verify_admin_password', {
          input_email: email,
          input_password: password
        });

      if (verifyError) {
        console.error('Password verification error:', verifyError);
        return new Response(JSON.stringify({ error: 'Authentication failed' }), {
          status: 401,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        });
      }

      if (!adminData || adminData.length === 0) {
        console.log('Invalid credentials for:', email);
        return new Response(JSON.stringify({ error: 'Invalid credentials' }), {
          status: 401,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        });
      }

      const admin = adminData[0];
      
      // Create admin auth user if it doesn't exist
      let authUser;
      const { data: existingUser } = await supabase.auth.admin.getUserByEmail(email);
      
      if (existingUser.user) {
        authUser = existingUser.user;
      } else {
        // Create auth user for admin
        const { data: newUser, error: createError } = await supabase.auth.admin.createUser({
          email: email,
          password: password,
          email_confirm: true,
          user_metadata: {
            full_name: admin.full_name,
            role: admin.role,
            is_admin: true
          }
        });

        if (createError) {
          console.error('Error creating auth user:', createError);
          return new Response(JSON.stringify({ error: 'Authentication setup failed' }), {
            status: 500,
            headers: { ...corsHeaders, 'Content-Type': 'application/json' },
          });
        }
        authUser = newUser.user;
      }

      // Generate access token for admin
      const { data: sessionData, error: sessionError } = await supabase.auth.admin.generateLink({
        type: 'magiclink',
        email: email,
        options: {
          redirectTo: `${req.headers.get('origin')}/admin`
        }
      });

      if (sessionError) {
        console.error('Session generation error:', sessionError);
        return new Response(JSON.stringify({ error: 'Session creation failed' }), {
          status: 500,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        });
      }

      // Update last login
      await supabase
        .from('admin_users')
        .update({ last_login_at: new Date().toISOString() })
        .eq('id', admin.admin_id);

      // Log admin login
      await supabase.rpc('log_admin_action', {
        action_type: 'login',
        resource_type: 'admin_session',
        resource_id: admin.admin_id
      });

      return new Response(JSON.stringify({
        user: {
          id: admin.admin_id,
          email: admin.email,
          full_name: admin.full_name,
          role: admin.role,
          is_active: admin.is_active
        },
        session: {
          access_token: sessionData.properties?.access_token,
          refresh_token: sessionData.properties?.refresh_token
        }
      }), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    if (action === 'verify') {
      const authHeader = req.headers.get('authorization');
      if (!authHeader) {
        return new Response(JSON.stringify({ error: 'No authorization header' }), {
          status: 401,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        });
      }

      const token = authHeader.replace('Bearer ', '');
      
      // Verify the JWT token
      const { data: { user }, error: userError } = await supabase.auth.getUser(token);
      
      if (userError || !user) {
        return new Response(JSON.stringify({ error: 'Invalid token' }), {
          status: 401,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        });
      }

      // Check if user is admin
      const { data: adminData, error: adminError } = await supabase
        .from('admin_users')
        .select('*')
        .eq('email', user.email)
        .eq('is_active', true)
        .single();

      if (adminError || !adminData) {
        return new Response(JSON.stringify({ error: 'Not an admin user' }), {
          status: 403,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        });
      }

      return new Response(JSON.stringify({
        user: {
          id: adminData.id,
          email: adminData.email,
          full_name: adminData.full_name,
          role: adminData.role,
          is_active: adminData.is_active
        }
      }), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    return new Response(JSON.stringify({ error: 'Invalid action' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });

  } catch (error) {
    console.error('Admin auth error:', error);
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
});