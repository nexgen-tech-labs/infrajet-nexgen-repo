
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
  return enc; // plaintext fallback
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
    .select('access_token')
    .eq('user_id', authData.user.id)
    .single();

  if (error || !data) throw new Error('GitHub not connected');

  const token = await decryptToken(data.access_token as string);

  // Migrate plaintext tokens
  if (!String(data.access_token).startsWith(ENC_PREFIX)) {
    const encrypted = await encryptToken(token);
    await supabase
      .from('user_github_connections')
      .update({ access_token: encrypted })
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
    const { repoFullName, files, commitMessage, token: legacyToken } = body || {};

    if (!repoFullName || !Array.isArray(files) || !commitMessage) {
      throw new Error('Missing required fields');
    }

    let tokenToUse: string | null = null;
    try {
      tokenToUse = await getTokenForUser(req);
    } catch (_) {
      if (legacyToken) tokenToUse = legacyToken;
    }
    if (!tokenToUse) throw new Error('Missing GitHub token or session');

    // Get the default branch
    const repoResponse = await fetch(`https://api.github.com/repos/${repoFullName}`, {
      headers: {
        'Authorization': `token ${tokenToUse}`,
        'Accept': 'application/vnd.github.v3+json',
      },
    });

    const repo = await repoResponse.json();
    const defaultBranch = repo.default_branch;

    // Get the latest commit SHA
    const branchResponse = await fetch(`https://api.github.com/repos/${repoFullName}/git/refs/heads/${defaultBranch}`, {
      headers: {
        'Authorization': `token ${tokenToUse}`,
        'Accept': 'application/vnd.github.v3+json',
      },
    });

    const branchData = await branchResponse.json();
    const latestCommitSha = branchData.object.sha;

    // Get the tree for the latest commit
    const commitResponse = await fetch(`https://api.github.com/repos/${repoFullName}/git/commits/${latestCommitSha}`, {
      headers: {
        'Authorization': `token ${tokenToUse}`,
        'Accept': 'application/vnd.github.v3+json',
      },
    });

    const commitData = await commitResponse.json();
    const treeSha = commitData.tree.sha;

    // Create blobs for all files
    const blobs = await Promise.all(
      files.map(async (file: { path: string; content: string }) => {
        const blobResponse = await fetch(`https://api.github.com/repos/${repoFullName}/git/blobs`, {
          method: 'POST',
          headers: {
            'Authorization': `token ${tokenToUse}`,
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            content: file.content,
            encoding: 'utf-8',
          }),
        });

        const blob = await blobResponse.json();
        return { path: file.path, sha: blob.sha };
      })
    );

    // Create a new tree
    const treeResponse = await fetch(`https://api.github.com/repos/${repoFullName}/git/trees`, {
      method: 'POST',
      headers: {
        'Authorization': `token ${tokenToUse}`,
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        base_tree: treeSha,
        tree: blobs.map((blob) => ({
          path: blob.path,
          mode: '100644',
          type: 'blob',
          sha: blob.sha,
        })),
      }),
    });

    const newTree = await treeResponse.json();

    // Create a new commit
    const newCommitResponse = await fetch(`https://api.github.com/repos/${repoFullName}/git/commits`, {
      method: 'POST',
      headers: {
        'Authorization': `token ${tokenToUse}`,
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: commitMessage,
        tree: newTree.sha,
        parents: [latestCommitSha],
      }),
    });

    const newCommit = await newCommitResponse.json();

    // Update the reference
    const updateRefResponse = await fetch(`https://api.github.com/repos/${repoFullName}/git/refs/heads/${defaultBranch}`, {
      method: 'PATCH',
      headers: {
        'Authorization': `token ${tokenToUse}`,
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ sha: newCommit.sha }),
    });

    const updateResult = await updateRefResponse.json();

    return new Response(JSON.stringify({ 
      success: true,
      commit: newCommit,
      ref: updateResult
    }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });

  } catch (error) {
    console.error('GitHub push error:', error);
    return new Response(JSON.stringify({ 
      error: (error as Error).message || 'Failed to push to GitHub'
    }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
});
