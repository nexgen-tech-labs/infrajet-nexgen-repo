export interface RuntimeConfig {
  GITHUB_APP_SLUG: string;
  INFRAJET_API_URL: string;
  FIREBASE_API_KEY: string;
  FIREBASE_AUTH_DOMAIN: string;
  FIREBASE_PROJECT_ID: string;
  FIREBASE_STORAGE_BUCKET?: string;
  FIREBASE_MESSAGING_SENDER_ID?: string;
  FIREBASE_APP_ID?: string;
}

let runtimeConfig: RuntimeConfig | null = null;

export async function loadRuntimeConfig(): Promise<RuntimeConfig> {
  if (runtimeConfig) return runtimeConfig;

  try {
    const response = await fetch('/config.json', { cache: 'no-cache' });
    if (!response.ok) {
      throw new Error(`Failed to load runtime config: ${response.statusText}`);
    }

    runtimeConfig = await response.json();
    return runtimeConfig;
  } catch (error) {
    console.warn('Failed to load runtime config from /config.json, falling back to window.__RUNTIME_CONFIG__:', error);
    // Fallback to window.__RUNTIME_CONFIG__ if fetch fails
    if (window.__RUNTIME_CONFIG__) {
      runtimeConfig = window.__RUNTIME_CONFIG__ as RuntimeConfig;
      return runtimeConfig;
    }
    throw error;
  }
}
