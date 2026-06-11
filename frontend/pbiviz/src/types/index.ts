"""Frontend type definitions as TypeScript files."""
# This is a placeholder - actual TypeScript files should be created

# Types for chat module
chat_types = """
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
  messages: Message[];
  createdAt: string;
  updatedAt: string;
}
"""

# Types for analytics
analytics_types = """
export interface Metric {
  name: string;
  value: number;
  unit?: string;
  timestamp: string;
}

export interface DataPoint {
  timestamp: string;
  value: number;
  labels?: Record<string, string>;
}

export interface TimeSeries {
  name: string;
  dataPoints: DataPoint[];
  metrics?: Record<string, number>;
}

export interface AnalyticsResult {
  type: string;
  data: Record<string, any>;
  summary: string;
  confidence: number;
  timestamp: string;
}
"""

# Types for Power BI context
powerbi_types = """
export interface Visual {
  id: string;
  name: string;
  type: string;
  fields: string[];
}

export interface Page {
  id: string;
  name: string;
  visuals: Visual[];
}

export interface Report {
  id: string;
  name: string;
  pages: Page[];
}

export interface PowerBIContext {
  report: Report;
  currentPage: string;
  selectedVisuals: string[];
  filters: Record<string, any>;
}
"""
