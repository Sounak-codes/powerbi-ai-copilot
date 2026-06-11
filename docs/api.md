# API

## Health

- `GET /health`
- `GET /health/status`

## Chat

- `POST /api/chat/message`
- `POST /api/chat/session`
- `GET /api/chat/session/{session_id}`
- `GET /api/chat/history/{session_id}`

## Analytics And Insights

- `POST /api/analytics/analyze`
- `POST /api/insights/generate`
- `POST /api/dax/generate`
- `POST /api/reports/document`
- `POST /api/feedback`

The legacy local endpoint `POST /api/ask` is kept for the currently working custom visual path.
