/**
 * Authentication service
 */

interface AuthToken {
  accessToken: string;
  tokenType: string;
  expiresIn: number;
}

class AuthService {
  private token: string | null = null;
  private tokenExpiry: number | null = null;
  private storageKey = 'copilot_auth_token';
  private expiryKey = 'copilot_token_expiry';

  /**
   * Set authentication token
   */
  setToken(token: string, expiresIn: number = 3600): void {
    this.token = token;
    this.tokenExpiry = Date.now() + expiresIn * 1000;
    localStorage.setItem(this.storageKey, token);
    localStorage.setItem(this.expiryKey, this.tokenExpiry.toString());
  }

  /**
   * Get current token
   */
  getToken(): string | null {
    if (this.token && this.isTokenValid()) {
      return this.token;
    }

    // Try to load from localStorage
    const stored = localStorage.getItem(this.storageKey);
    const expiry = localStorage.getItem(this.expiryKey);

    if (stored && expiry && Date.now() < parseInt(expiry)) {
      this.token = stored;
      this.tokenExpiry = parseInt(expiry);
      return this.token;
    }

    this.clearToken();
    return null;
  }

  /**
   * Check if token is valid
   */
  isTokenValid(): boolean {
    if (!this.token || !this.tokenExpiry) {
      return false;
    }
    return Date.now() < this.tokenExpiry;
  }

  /**
   * Clear token
   */
  clearToken(): void {
    this.token = null;
    this.tokenExpiry = null;
    localStorage.removeItem(this.storageKey);
    localStorage.removeItem(this.expiryKey);
  }

  /**
   * Get authorization header
   */
  getAuthHeader(): Record<string, string> {
    const token = this.getToken();
    if (token) {
      return {
        Authorization: `Bearer ${token}`,
      };
    }
    return {};
  }

  /**
   * Logout
   */
  logout(): void {
    this.clearToken();
  }
}

export default new AuthService();
