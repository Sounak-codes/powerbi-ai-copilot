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
const REQUEST_TIMEOUT_MS = 30000;

export async function askCopilot(question: string, reportContext: ReportContext = {}) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, report_context: reportContext }),
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("Backend request timed out. Restart the backend and check the Groq API key/model.");
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }

  if (!response.ok) {
    throw new Error(await response.text());
  }

  return response.json();
}
