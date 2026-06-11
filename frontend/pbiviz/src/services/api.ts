/**
 * API service for backend communication
 */

import { ChatRequest, ChatResponse, Session } from '../types/chat';
import { AnalyticsResult } from '../types/analytics';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

class APIService {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  /**
   * Send a chat message
   */
  async sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
    const response = await fetch(`${this.baseUrl}/chat/message`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Create a new session
   */
  async createSession(userId: string, reportId?: string): Promise<Session> {
    const params = new URLSearchParams({ userId });
    if (reportId) params.append('reportId', reportId);

    const response = await fetch(`${this.baseUrl}/chat/session?${params}`, {
      method: 'POST',
    });

    if (!response.ok) {
      throw new Error(`Failed to create session: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get session info
   */
  async getSession(sessionId: string): Promise<Session> {
    const response = await fetch(`${this.baseUrl}/chat/session/${sessionId}`);

    if (!response.ok) {
      throw new Error(`Failed to get session: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get conversation history
   */
  async getConversationHistory(sessionId: string, limit?: number) {
    const params = new URLSearchParams();
    if (limit) params.append('limit', limit.toString());

    const response = await fetch(
      `${this.baseUrl}/chat/history/${sessionId}?${params}`
    );

    if (!response.ok) {
      throw new Error(`Failed to get history: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Generate insights
   */
  async generateInsights(reportId: string, pageId?: string, visualId?: string) {
    const response = await fetch(`${this.baseUrl}/insights/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        reportId,
        pageId,
        visualId,
        depth: 'standard',
      }),
    });

    if (!response.ok) {
      throw new Error(`Failed to generate insights: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get report insights
   */
  async getReportInsights(reportId: string) {
    const response = await fetch(`${this.baseUrl}/insights/report/${reportId}`);

    if (!response.ok) {
      throw new Error(`Failed to get insights: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Health check
   */
  async healthCheck() {
    const response = await fetch(`${this.baseUrl}/health/`);
    return response.json();
  }
}

export default new APIService();
