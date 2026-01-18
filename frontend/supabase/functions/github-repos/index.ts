
import "https://deno.land/x/xhr@0.1.0/mod.ts";
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

const ENC_PREFIX = 'ENCv1:';
const te = new TextEncoder();
const td = new TextDecoder();

async function getCryptoKey() {
  const secret = Deno.env.get('GITHUB_TOKEN_ENC_KEY') ?? '';
  if (!secret) throw new Error('Missing GITHUB_TOKEN_ENC_KEY');
  const hash = await crypto.subtle.digest('SHA-256', te.encode(secret));
  return crypto.subtle.importKey('raw', hash, { name: 'AES-GCM' }, false, ['encrypt', 'decrypt']);
}

function base64Encode(bytes: Uint8Array) {
  let binary = '';
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

function base64Decode(str: string) {
  const binary = atob(str);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

async function encryptToken(token: string) {
  const key = await getCryptoKey();
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = new Uint8Array(
    await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, te.encode(token))
  );
  const combined = new Uint8Array(iv.length + ct.length);
  combined.set(iv, 0);
  combined.set(ct, iv.length);
  return ENC_PREFIX + base64Encode(combined);
}

async function decryptToken(enc: string) {
  if (enc.startsWith(ENC_PREFIX)) {
    const payload = enc.slice(ENC_PREFIX.length);
    const bytes = base64Decode(payload);
    const iv = bytes.slice(0, 12);
    const data = bytes.slice(12);
    const key = await getCryptoKey();
    const pt = await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, data);
    return td.decode(new Uint8Array(pt));
  }
  // Backward compatibility for plaintext
  return enc;
}

async function getTokenForUser(req: Request) {
  const supabase = createClient(
    Deno.env.get('SUPABASE_URL') ?? '',
    Deno.env.get('SUPABASE_ANON_KEY') ?? '',
    { global: { headers: { Authorization: req.headers.get('Authorization') ?? '' } } }
  );

  const { data: authData, error: authError } = await supabase.auth.getUser();
  if (authError || !authData?.user) throw new Error('Unauthorized');

  const { data, error } = await supabase
    .from('user_github_connections')
    .select('access_token_encrypted')
    .eq('user_id', authData.user.id)
    .single();

  if (error || !data) throw new Error('GitHub not connected');

  const token = await decryptToken(data.access_token_encrypted as string);

  // Migrate old column name if it exists
  if (data.access_token_encrypted) {
    // Already using new column
  } else if (data.access_token) {
    // Migrate from old column
    const encrypted = await encryptToken(token);
    await supabase
      .from('user_github_connections')
      .update({ access_token_encrypted: encrypted })
      .eq('user_id', authData.user.id);
  }

  return token;
}

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const body = await req.json();
    const { action, name, description, private: isPrivate, organization, token: legacyToken } = body || {};

    let tokenToUse: string | null = null;

    // Prefer secure server-side token fetch; fallback to legacy token if no session
    try {
      tokenToUse = await getTokenForUser(req);
    } catch (_) {
      if (legacyToken) tokenToUse = legacyToken;
    }

    if (!tokenToUse) throw new Error('Missing GitHub token or session');

    if (action === 'list') {
      let url;
      if (organization && organization !== 'personal') {
        // Fetch organization repositories
        url = `https://api.github.com/orgs/${organization}/repos?per_page=100&sort=updated`;
      } else {
        // Fetch user repositories
        url = 'https://api.github.com/user/repos?per_page=100&sort=updated&affiliation=owner';
      }

      const response = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${tokenToUse}`,
          'Accept': 'application/vnd.github.v3+json',
        },
      });

      const repos = await response.json();

      if (!response.ok) {
        throw new Error(repos.message || 'Failed to fetch repositories');
      }

      return new Response(JSON.stringify({ repos }), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    if (action === 'create') {
      let url = 'https://api.github.com/user/repos';
      if (organization && organization !== 'personal') {
        url = `https://api.github.com/orgs/${organization}/repos`;
      }

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${tokenToUse}`,
          'Accept': 'application/vnd.github.v3+json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name,
          description,
          private: isPrivate,
          auto_init: true,
        }),
      });

      const repo = await response.json();

      if (!response.ok) {
        throw new Error(repo.message || 'Failed to create repository');
      }

      return new Response(JSON.stringify({ repo }), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    throw new Error('Invalid action');

  } catch (error) {
    console.error('GitHub repos error:', error);
    return new Response(JSON.stringify({ 
      error: (error as Error).message || 'GitHub repositories operation failed'
    }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
});
