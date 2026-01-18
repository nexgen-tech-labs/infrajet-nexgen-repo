// src/global.d.ts
export { };

declare global {
  interface Window {
    __RUNTIME_CONFIG__?: {
      GITHUB_APP_SLUG?: string;
      INFRAJET_API_URL?: string;
      SUPABASE_PROJECT_ID?: string;
      SUPABASE_PUBLISHABLE_KEY?: string;
      SUPABASE_URL?: string;
    };
  }
}
