/**
 * WebSocket service for real-time communication
 */

import { Message } from '../types/chat';

class WebSocketService {
  private ws: WebSocket | null = null;
  private url: string;
  private messageHandlers: ((message: Message) => void)[] = [];
  private statusHandlers: ((status: string) => void)[] = [];
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;

  constructor(url: string = 'ws://localhost:8000/ws') {
    this.url = url;
  }

  /**
   * Connect to WebSocket
   */
  connect(sessionId: string): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(`${this.url}?sessionId=${sessionId}`);

        this.ws.onopen = () => {
          console.log('WebSocket connected');
          this.reconnectAttempts = 0;
          this.notifyStatus('connected');
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const message: Message = JSON.parse(event.data);
            this.messageHandlers.forEach((handler) => handler(message));
          } catch (e) {
            console.error('Failed to parse WebSocket message:', e);
          }
        };

        this.ws.onerror = (event) => {
          console.error('WebSocket error:', event);
          this.notifyStatus('error');
          reject(new Error('WebSocket connection failed'));
        };

        this.ws.onclose = () => {
          console.log('WebSocket disconnected');
          this.notifyStatus('disconnected');
          this.attemptReconnect(sessionId);
        };
      } catch (e) {
        reject(e);
      }
    });
  }

  /**
   * Send a message through WebSocket
   */
  send(message: any): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket is not connected');
    }
  }

  /**
   * Register message handler
   */
  onMessage(handler: (message: Message) => void): void {
    this.messageHandlers.push(handler);
  }

  /**
   * Register status change handler
   */
  onStatusChange(handler: (status: string) => void): void {
    this.statusHandlers.push(handler);
  }

  /**
   * Disconnect WebSocket
   */
  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  private attemptReconnect(sessionId: string): void {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = Math.pow(2, this.reconnectAttempts) * 1000;
      console.log(`Reconnecting in ${delay}ms...`);
      setTimeout(() => this.connect(sessionId), delay);
    }
  }

  private notifyStatus(status: string): void {
    this.statusHandlers.forEach((handler) => handler(status));
  }
}

export default new WebSocketService();
