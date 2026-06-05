# Power BI AI Copilot

Dataset-agnostic AI copilot architecture for Power BI dashboards, with a FastAPI backend, RAG services, Power BI assets, and a custom visual frontend.

The copilot is designed to work with any Power BI report by receiving runtime context from the custom visual: current page, visual type, fields, filters, slicers, selected data points, and optional dataset schema.

## Structure

- `backend/` contains the API, services, vector store, models, tests, logs, and knowledge base.
- `powerbi/` contains a sample PBIX, source data, and DAX definitions for testing.
- `frontend/custom_visual/` contains the Power BI custom visual source.
- `docs/` contains architecture, workflow, API, and setup documentation.

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
