# API Documentation

## POST `/api/ask`

Sends an analytics question and live Power BI runtime context to the copilot service.

### Request

```json
{
  "question": "What is unusual in this visual?",
  "report_context": {
    "report_name": "Any Power BI Report",
    "page_name": "Overview",
    "visual": {
      "visual_id": "visual-123",
      "visual_type": "barChart",
      "title": "Current visual title",
      "fields": [
        {
          "table": "TableName",
          "column": "MetricName",
          "data_type": "number",
          "role": "Values"
        }
      ],
      "data_points": []
    },
    "filters": [],
    "slicers": [],
    "dataset_schema": [],
    "selected_data": [],
    "user_locale": "en-US"
  }
}
```

### Response

```json
{
  "answer": "Based on the current visual and filters...",
  "sources": []
}
```

The API is dataset-agnostic. It should receive the current report/visual context from the Power BI custom visual at runtime, so the same backend can answer questions for any report.
