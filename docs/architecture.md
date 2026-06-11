# Architecture

Power BI AI Copilot is split into a Power BI custom visual frontend and a FastAPI backend.

## Frontend

- `frontend/custom_visual` contains the working Power BI visual used in Power BI Desktop.
- `frontend/pbiviz` contains the expanded React-oriented architecture scaffold for future UI modules.
- The custom visual sends selected fields, visible data points, and viewport metadata to the backend.

## Backend

- `backend/main.py` is the expanded FastAPI application entrypoint.
- `backend/app.py` remains compatible with the current local development command.
- `backend/orchestration` routes requests through intent detection, agents, memory, and response building.
- `backend/analytics_engine`, `backend/rag`, `backend/dax_copilot`, and `backend/report_documentation` hold specialized capabilities.

## Data Flow

1. A user drags fields into the Copilot visual.
2. The visual sends runtime context and the question to the backend.
3. The backend classifies intent and selects the right workflow.
4. Agents and engines generate insights, DAX, summaries, or explanations.
5. The response is returned to the visual and shown in the chat UI.
