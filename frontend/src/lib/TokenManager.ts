import { supabase } from '@/integrations/supabase/client';
import { ApiError, ErrorType } from './ApiError';

export interface TokenData {
  access_token: string;
  refresh_token?: string;
  expires_at?: number;
  expires_in?: number;
}

export class TokenManager {
  private static instance: TokenManager;
  private currentToken: TokenData | null = null;
  private refreshPromise: Promise<TokenData> | null = null;
  private refreshThreshold = 5 * 60 * 1000; // 5 minutes before expiry

  private constructor() {}

  static getInstance(): TokenManager {
    if (!TokenManager.instance) {
      TokenManager.instance = new TokenManager();
    }
    return TokenManager.instance;
  }

  async getValidToken(): Promise<string> {
    // If we have a token and it's not close to expiry, return it
    if (this.currentToken && !this.isTokenExpiringSoon()) {
      return this.currentToken.access_token;
    }

    // If refresh is already in progress, wait for it
    if (this.refreshPromise) {
      return (await this.refreshPromise).access_token;
    }

    // Start token refresh
    this.refreshPromise = this.refreshToken();

    try {
      const tokenData = await this.refreshPromise;
      this.currentToken = tokenData;
      return tokenData.access_token;
    } finally {
      this.refreshPromise = null;
    }
  }

  private async refreshToken(): Promise<TokenData> {
    try {
      // Try to get current session from Supabase
      const { data: { session }, error } = await supabase.auth.getSession();

      if (error) {
        throw new ApiError(
          ErrorType.AUTHENTICATION_ERROR,
          'Failed to get authentication session',
          401,
          undefined,
          error
        );
      }

      if (!session) {
        throw new ApiError(
          ErrorType.AUTHENTICATION_ERROR,
          'No active session found',
          401
        );
      }

      // Check if token is still valid
      if (this.isSessionValid(session)) {
        const tokenData: TokenData = {
          access_token: session.access_token,
          refresh_token: session.refresh_token || undefined,
          expires_at: session.expires_at ? session.expires_at * 1000 : undefined,
          expires_in: session.expires_in || undefined,
        };
        return tokenData;
      }

      // Token is expired or expiring soon, try to refresh
      const { data: refreshData, error: refreshError } = await supabase.auth.refreshSession();

      if (refreshError) {
        throw new ApiError(
          ErrorType.AUTHENTICATION_ERROR,
          'Failed to refresh authentication token',
          401,
          undefined,
          refreshError
        );
      }

      if (!refreshData.session) {
        throw new ApiError(
          ErrorType.AUTHENTICATION_ERROR,
          'Token refresh failed - no session returned',
          401
        );
      }

      const tokenData: TokenData = {
        access_token: refreshData.session.access_token,
        refresh_token: refreshData.session.refresh_token || undefined,
        expires_at: refreshData.session.expires_at ? refreshData.session.expires_at * 1000 : undefined,
        expires_in: refreshData.session.expires_in || undefined,
      };

      return tokenData;

    } catch (error) {
      if (error instanceof ApiError) {
        throw error;
      }

      throw new ApiError(
        ErrorType.AUTHENTICATION_ERROR,
        'Authentication failed',
        401,
        undefined,
        error as Error
      );
    }
  }

  private isTokenExpiringSoon(): boolean {
    if (!this.currentToken?.expires_at) {
      return false;
    }

    const now = Date.now();
    const timeUntilExpiry = this.currentToken.expires_at - now;

    return timeUntilExpiry < this.refreshThreshold;
  }

  private isSessionValid(session: any): boolean {
    if (!session.expires_at) {
      return true; // Assume valid if no expiry
    }

    const now = Date.now();
    const expiresAt = session.expires_at * 1000; // Convert to milliseconds
    const timeUntilExpiry = expiresAt - now;

    return timeUntilExpiry > this.refreshThreshold;
  }

  clearToken(): void {
    this.currentToken = null;
    this.refreshPromise = null;
  }

  // Set up automatic token refresh listener
  setupAutoRefresh(): () => void {
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (event, session) => {
        switch (event) {
          case 'SIGNED_IN':
          case 'TOKEN_REFRESHED':
            if (session) {
              this.currentToken = {
                access_token: session.access_token,
                refresh_token: session.refresh_token || undefined,
                expires_at: session.expires_at ? session.expires_at * 1000 : undefined,
                expires_in: session.expires_in || undefined,
              };
            }
            break;
          case 'SIGNED_OUT':
            this.clearToken();
            break;
        }
      }
    );

    return () => subscription.unsubscribe();
  }

  // Get current token without refreshing
  getCurrentToken(): string | null {
    return this.currentToken?.access_token || null;
  }

  // Check if we have a valid token
  hasValidToken(): boolean {
    return !!(this.currentToken && !this.isTokenExpiringSoon());
  }
}

// Export singleton instance
export const tokenManager = TokenManager.getInstance();