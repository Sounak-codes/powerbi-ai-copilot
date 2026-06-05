import "./styles.css";
import { askCopilot, DataField, ReportContext } from "./api";

const botImage = require("../assets/bot.webp");

type VisualConstructorOptions = {
  element: HTMLElement;
  host?: unknown;
};

type VisualUpdateOptions = {
  dataViews?: any[];
  viewport?: {
    width: number;
    height: number;
  };
};

type ChatState = {
  question: string;
  userMessage: string;
  answer: string;
};

const STORAGE_KEY = "powerbi-ai-copilot-chat-state";

export class Visual {
  private container: HTMLElement;
  private questionInput: HTMLTextAreaElement;
  private answerOutput: HTMLElement;
  private userBubble: HTMLElement;
  private askButton: HTMLButtonElement;
  private statusLabel: HTMLElement;
  private reportContext: ReportContext = {};
  private hasRestoredState = false;

  constructor(options?: VisualConstructorOptions) {
    if (!options?.element) {
      throw new Error("Power BI visual element was not provided.");
    }

    this.container = options.element;
    this.container.className = "copilot-visual";
    this.container.innerHTML = `
      <section class="copilot-shell">
        <header class="copilot-header">
          <div class="copilot-title-row">
            <span class="copilot-mark">
              <img src="${botImage}" alt="" />
            </span>
            <div>
              <h2>Power BI Copilot</h2>
              <span class="copilot-status" data-role="status">Waiting for report data</span>
            </div>
          </div>
        </header>
        <main class="copilot-main">
          <section class="copilot-chat">
            <div class="copilot-bubble copilot-bubble-user" data-role="user-bubble">Ask me about the fields in this visual.</div>
            <div class="copilot-bot-row">
              <img class="copilot-bot-avatar" src="${botImage}" alt="" />
              <div class="copilot-bubble copilot-bubble-assistant" data-role="answer">Add fields to this visual, then ask Copilot for insights.</div>
            </div>
          </section>
          <div class="copilot-prompt">
            <div class="copilot-input-row">
              <textarea id="copilot-question" class="copilot-input" data-role="question" placeholder="Ask about the selected fields..."></textarea>
              <button class="copilot-button" data-role="ask" type="button">Send</button>
            </div>
          </div>
        </main>
      </section>
    `;

    this.questionInput = this.getElement<HTMLTextAreaElement>("question");
    this.answerOutput = this.getElement<HTMLElement>("answer");
    this.userBubble = this.getElement<HTMLElement>("user-bubble");
    this.askButton = this.getElement<HTMLButtonElement>("ask");
    this.statusLabel = this.getElement<HTMLElement>("status");
    this.askButton.addEventListener("click", () => this.submitQuestion());
    this.questionInput.addEventListener("input", () => this.saveState());
    this.restoreStateOnce();
  }

  public update(options: VisualUpdateOptions): void {
    this.reportContext = this.buildReportContext(options);
    const rowCount = this.reportContext.visual?.data_points?.length ?? 0;
    const fieldCount = this.reportContext.visual?.fields?.length ?? 0;
    this.statusLabel.textContent = `${fieldCount} fields, ${rowCount} data points detected`;
    if (fieldCount === 0 && !this.answerOutput.textContent?.trim()) {
      this.answerOutput.textContent = "Drag columns or measures into the Fields well so Copilot has data to analyze.";
      this.saveState();
    }
  }

  private getElement<T extends HTMLElement>(role: string): T {
    const element = this.container.querySelector(`[data-role="${role}"]`);
    if (!element) {
      throw new Error(`Missing copilot element: ${role}`);
    }
    return element as T;
  }

  private async submitQuestion(): Promise<void> {
    const question = this.questionInput.value.trim();
    if (!question) {
      this.answerOutput.textContent = "Type a question first.";
      return;
    }
    if ((this.reportContext.visual?.fields?.length ?? 0) === 0) {
      this.answerOutput.textContent = "Add at least one column or measure to the Fields well before asking.";
      return;
    }

    this.askButton.disabled = true;
    this.userBubble.textContent = question;
    this.answerOutput.textContent = "Thinking...";
    this.saveState();

    try {
      const result = await askCopilot(question, this.reportContext);
      this.answerOutput.textContent = result.answer || "No answer returned.";
    } catch (error) {
      this.answerOutput.textContent = `Copilot request failed: ${error instanceof Error ? error.message : String(error)}`;
    } finally {
      this.askButton.disabled = false;
      this.saveState();
    }
  }

  private buildReportContext(options: VisualUpdateOptions): ReportContext {
    const dataView = options.dataViews?.[0];
    const fields = this.extractFields(dataView);
    const dataPoints = this.extractDataPoints(dataView);

    return {
      visual: {
        visual_type: "customVisual",
        title: "Power BI AI Copilot",
        fields,
        data_points: dataPoints,
      },
      metadata: {
        viewport: options.viewport,
        row_count: dataPoints.length,
      },
    };
  }

  private extractFields(dataView: any): DataField[] {
    const columns = dataView?.metadata?.columns ?? [];
    return columns.map((column: any) => ({
      table: column?.queryName?.includes(".") ? column.queryName.split(".")[0] : undefined,
      column: column?.displayName ?? column?.queryName ?? "Unknown field",
      data_type: this.getDataType(column?.type),
      role: Object.keys(column?.roles ?? {}).join(", ") || undefined,
    }));
  }

  private extractDataPoints(dataView: any): Record<string, unknown>[] {
    if (dataView?.table?.rows && dataView?.metadata?.columns) {
      return dataView.table.rows.slice(0, 50).map((row: unknown[]) => {
        const point: Record<string, unknown> = {};
        dataView.metadata.columns.forEach((column: any, index: number) => {
          point[column.displayName ?? `Column ${index + 1}`] = row[index];
        });
        return point;
      });
    }

    const categories = dataView?.categorical?.categories ?? [];
    const values = dataView?.categorical?.values ?? [];
    const rowCount = Math.max(
      ...categories.map((category: any) => category.values?.length ?? 0),
      ...values.map((value: any) => value.values?.length ?? 0),
      0
    );

    return Array.from({ length: Math.min(rowCount, 50) }, (_, rowIndex) => {
      const point: Record<string, unknown> = {};
      categories.forEach((category: any) => {
        point[category.source?.displayName ?? "Category"] = category.values?.[rowIndex];
      });
      values.forEach((value: any) => {
        point[value.source?.displayName ?? "Value"] = value.values?.[rowIndex];
      });
      return point;
    });
  }

  private getDataType(type: any): string | undefined {
    if (!type) {
      return undefined;
    }
    if (type.numeric) {
      return "number";
    }
    if (type.dateTime) {
      return "datetime";
    }
    if (type.bool) {
      return "boolean";
    }
    if (type.text) {
      return "text";
    }
    return undefined;
  }

  private restoreStateOnce(): void {
    if (this.hasRestoredState) {
      return;
    }

    this.hasRestoredState = true;
    const state = this.readState();
    if (!state) {
      return;
    }

    this.questionInput.value = state.question;
    this.userBubble.textContent = state.userMessage;
    this.answerOutput.textContent = state.answer;
  }

  private saveState(): void {
    const state: ChatState = {
      question: this.questionInput.value,
      userMessage: this.userBubble.textContent || "",
      answer: this.answerOutput.textContent || "",
    };

    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      // Power BI can restrict storage in some host contexts.
    }
  }

  private readState(): ChatState | null {
    try {
      const value = window.localStorage.getItem(STORAGE_KEY) || window.sessionStorage.getItem(STORAGE_KEY);
      return value ? (JSON.parse(value) as ChatState) : null;
    } catch {
      return null;
    }
  }
}
