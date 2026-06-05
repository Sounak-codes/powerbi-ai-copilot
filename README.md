# Power BI AI Copilot

Dataset-agnostic AI copilot architecture for Power BI dashboards, with a FastAPI backend, RAG services, Power BI assets, and a custom visual frontend.

The copilot is designed to work with any Power BI report by receiving runtime context from the custom visual: current page, visual type, fields, filters, slicers, selected data points, and optional dataset schema.

## Features

- Works with any PBIX file through a Power BI custom visual.
- Sends selected fields and visible data points to a FastAPI backend.
- Uses Groq to generate business-friendly insights.
- Includes a polished glass-style Copilot panel for Power BI Desktop.
- Includes a Parental Leave Policies PBIX as a sample test dashboard.

## Structure

- `backend/` contains the API, services, vector store, models, tests, logs, and knowledge base.
- `powerbi/` contains a sample PBIX, source data, and DAX definitions for testing.
- `frontend/custom_visual/` contains the Power BI custom visual source.
- `docs/` contains architecture, workflow, API, and setup documentation.

## Setup

### 1. Create Environment

```powershell
conda create -n powerbi-ai-copilot python=3.11 -y
conda activate powerbi-ai-copilot
pip install -r requirement.txt
```

### 2. Configure Groq

Create `.env` from `.env.example`:

```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

### 3. Run Backend

```powershell
cd backend
uvicorn app:app --reload
```

Health check:

```text
http://127.0.0.1:8000/health
```

Swagger API:

```text
http://127.0.0.1:8000/docs
```

### 4. Run Custom Visual

Install Node.js LTS first, then:

```powershell
cd frontend/custom_visual
npm install
npm run start
```

The developer visual runs at:

```text
https://localhost:8080/
```

### 5. Use In Power BI Desktop

1. Open any PBIX file.
2. Enable Power BI custom visual developer mode.
3. Add the Developer Visual.
4. Drag relevant columns/measures into the Copilot visual's Fields well.
5. Ask a question in the Copilot panel.

The visual can work with any dataset, but it can only analyze fields/data passed into the Copilot visual.

## Packaging

To create a `.pbiviz` package:

```powershell
cd frontend/custom_visual
npm run package
```

The package is generated in:

```text
frontend/custom_visual/dist/
```

## Sample Test Dashboard

- PBIX: `powerbi/pbix/Parental_leave_policies.pbix`
- Dataset: `powerbi/sample_data/parental_leave.csv`
- Data dictionary: `powerbi/sample_data/data_dictionary.csv`
- Dashboard screenshot: `frontend/screenshots/Parental_leave_policies_dashboard_img.jpg`

This sample is only for testing. The backend prompt and API contract are intentionally generic and should not assume the report domain.

## Runtime Context

For production use, the Power BI visual should send:

- report and page name
- visual id, visual type, title, fields, and visible data points
- current report/page/visual filters
- slicer selections
- selected data points
- optional dataset schema or semantic model metadata

## Notes

- `.env` is ignored by Git and should not be committed.
- The custom visual currently sends up to 50 visible data rows for fast local testing.
- Backend API base URL for local testing is `http://127.0.0.1:8000`.
