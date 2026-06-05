# Power BI Runtime Context

The copilot should work for any Power BI report by sending live context from the custom visual to the backend.

## Context To Send

- `report_name`: current report name
- `page_name`: current page name
- `visual`: current visual id, type, title, fields, and visible data points
- `filters`: report, page, and visual filters
- `slicers`: slicer selections
- `dataset_schema`: optional table/column metadata from the semantic model
- `selected_data`: points or rows selected by the user
- `user_locale`: locale for formatting dates and numbers

## Backend Behavior

The backend should not hardcode a domain. It should answer from the runtime context and ask for missing fields, filters, or data when the context is not enough.

## Sample Project

`Parental_leave_policies.pbix` is a test fixture only. It helps validate the architecture but should not shape the generic copilot behavior.
