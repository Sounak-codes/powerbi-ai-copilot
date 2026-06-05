export type DataField = {
  table?: string;
  column: string;
  data_type?: string;
  role?: string;
};

export type VisualContext = {
  visual_id?: string;
  visual_type?: string;
  title?: string;
  fields?: DataField[];
  data_points?: Record<string, unknown>[];
};

export type ReportContext = {
  report_name?: string;
  page_name?: string;
  visual?: VisualContext;
  filters?: Record<string, unknown>[];
  slicers?: Record<string, unknown>[];
  dataset_schema?: DataField[];
  selected_data?: Record<string, unknown>[];
  user_locale?: string;
  metadata?: Record<string, unknown>;
};

const API_BASE_URL = "http://127.0.0.1:8000";

export async function askCopilot(question: string, reportContext: ReportContext = {}) {
  const response = await fetch(`${API_BASE_URL}/api/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, report_context: reportContext }),
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }

  return response.json();
}
