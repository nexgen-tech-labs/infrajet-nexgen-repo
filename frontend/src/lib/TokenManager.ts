import { getFirebaseAuth } from './firebase';
import { onAuthStateChanged, User } from 'firebase/auth';
import { ApiError, ErrorType } from './ApiError';

export interface TokenData {
  access_token: string;
  expires_at?: number;
}

export class TokenManager {
  private static instance: TokenManager;
  private currentToken: TokenData | null = null;
  private currentUser: User | null = null;
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
      const auth = getFirebaseAuth();
      const user = auth.currentUser;

      if (!user) {
        throw new ApiError(
          ErrorType.AUTHENTICATION_ERROR,
          'No authenticated user found',
          401
        );
      }

      // Get fresh ID token from Firebase
      // Firebase automatically refreshes the token if needed
      const idToken = await user.getIdToken(true); // Force refresh

      // Get token result to check expiration
      const tokenResult = await user.getIdTokenResult();
      const expirationTime = new Date(tokenResult.expirationTime).getTime();

      const tokenData: TokenData = {
        access_token: idToken,
        expires_at: expirationTime,
      };

      this.currentUser = user;
      return tokenData;

    } catch (error) {
      if (error instanceof ApiError) {
        throw error;
      }

      throw new ApiError(
        ErrorType.AUTHENTICATION_ERROR,
        'Failed to refresh authentication token',
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

  clearToken(): void {
    this.currentToken = null;
    this.currentUser = null;
    this.refreshPromise = null;
  }

  // Set up automatic token refresh listener
  setupAutoRefresh(): () => void {
    try {
      const auth = getFirebaseAuth();

      const unsubscribe = onAuthStateChanged(auth, async (user) => {
        if (user) {
          this.currentUser = user;
          // Get initial token
          try {
            const idToken = await user.getIdToken();
            const tokenResult = await user.getIdTokenResult();
            const expirationTime = new Date(tokenResult.expirationTime).getTime();

            this.currentToken = {
              access_token: idToken,
              expires_at: expirationTime,
            };
          } catch (error) {
            console.error('Error getting initial token:', error);
          }
        } else {
          this.clearToken();
        }
      });

      return () => unsubscribe();
    } catch (error) {
      console.error('Error setting up auto-refresh:', error);
      return () => {}; // Return empty cleanup function
    }
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
