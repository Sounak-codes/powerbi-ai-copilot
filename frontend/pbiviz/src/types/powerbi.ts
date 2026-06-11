/**
 * Power BI context types and interfaces
 */

export interface Visual {
  id: string;
  name: string;
  type: string;
  fields: string[];
  data?: Array<Record<string, any>>;
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
  metadata?: Record<string, any>;
}

export interface Filter {
  column: string;
  operator: string;
  value: any;
}

export interface Selection {
  visualId: string;
  dataPoints: Array<Record<string, any>>;
}

export interface PowerBIContext {
  report: Report;
  currentPage: string;
  currentVisual?: string;
  selectedVisuals?: string[];
  filters?: Filter[];
  selection?: Selection;
  slicers?: Record<string, any>;
}

export interface ReportContextPayload {
  reportId: string;
  pageId: string;
  context: PowerBIContext;
}
