/**
 * useChat hook for chat functionality
 */

import { useState, useCallback, useEffect } from 'react';
import { Message, ChatRequest, ChatResponse, Session } from '../types/chat';
import apiService from '../services/api';

export interface UseChatReturn {
  messages: Message[];
  input: string;
  setInput: (value: string) => void;
  isLoading: boolean;
  error: string | null;
  session: Session | null;
  suggestions: string[];
  sendMessage: (content: string) => Promise<void>;
  clearMessages: () => void;
  initializeSession: (userId: string, reportId?: string) => Promise<void>;
}

export const useChat = (): UseChatReturn => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([
    "Summarize this visual",
    "Find anomalies",
    "Explain the top drivers",
  ]);

  const initializeSession = useCallback(
    async (userId: string, reportId?: string) => {
      try {
        const newSession = await apiService.createSession(userId, reportId);
        setSession(newSession);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to create session');
      }
    },
    []
  );

  const sendMessage = useCallback(
    async (content: string) => {
      if (!session) {
        setError('Session not initialized');
        return;
      }

      try {
        setIsLoading(true);
        setError(null);

        // Add user message immediately
        const userMessage: Message = {
          id: `msg_${Date.now()}`,
          role: 'user',
          content,
          timestamp: new Date().toISOString(),
        };

        setMessages((prev) => [...prev, userMessage]);

        // Send to API
        const request: ChatRequest = {
          message: content,
          sessionId: session.sessionId,
        };

        const response = await apiService.sendChatMessage(request);
        setSuggestions(response.followUpQuestions ?? suggestions);

        // Add assistant message
        const assistantMessage: Message = {
          id: `msg_${Date.now()}_resp`,
          role: 'assistant',
          content: response.message,
          timestamp: response.timestamp,
          metadata: response.metadata,
        };

        setMessages((prev) => [...prev, assistantMessage]);
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : 'Failed to send message';
        setError(errorMsg);
      } finally {
        setIsLoading(false);
      }
    },
    [session, suggestions]
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  return {
    messages,
    input,
    setInput,
    isLoading,
    error,
    session,
    suggestions,
    sendMessage,
    clearMessages,
    initializeSession,
  };
};
