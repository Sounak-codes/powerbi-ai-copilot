/**
 * Chat types and interfaces
 */

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  metadata?: Record<string, any>;
}

export interface ChatRequest {
  message: string;
  sessionId: string;
  context?: Record<string, any>;
}

export interface ChatResponse {
  message: string;
  sessionId: string;
  timestamp: string;
  metadata?: Record<string, any>;
  followUpQuestions?: string[];
}

export interface Conversation {
  id: string;
  sessionId: string;
  userId: string;
  messages: Message[];
  createdAt: string;
  updatedAt: string;
}

export interface Session {
  sessionId: string;
  userId: string;
  reportId?: string;
  createdAt: string;
  expiresAt: string;
}
