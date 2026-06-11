/**
 * Analytics types and interfaces
 */

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

export interface Trend {
  direction: 'increasing' | 'decreasing' | 'stable';
  magnitude: number;
  confidence: number;
  startDate: string;
  endDate: string;
  description: string;
}

export interface Anomaly {
  timestamp: string;
  value: number;
  expectedRange: [number, number];
  severity: 'low' | 'medium' | 'high';
  description: string;
}

export interface Correlation {
  metric1: string;
  metric2: string;
  coefficient: number;
  significance: number;
  description: string;
}

export interface AnalyticsResult {
  type: string;
  data: Record<string, any>;
  summary: string;
  confidence: number;
  timestamp: string;
}
