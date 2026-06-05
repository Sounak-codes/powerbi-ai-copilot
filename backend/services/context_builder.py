import json
from typing import Any

from pydantic import BaseModel


def _to_plain_dict(value: Any) -> Any:
    if isinstance(value, BaseModel):
        if hasattr(value, "model_dump"):
            return value.model_dump(exclude_none=True)
        return value.dict(exclude_none=True)
    return value


def _format_json_section(title: str, value: Any) -> str | None:
    plain_value = _to_plain_dict(value)
    if not plain_value:
        return None
    formatted = json.dumps(plain_value, indent=2, ensure_ascii=False, default=str)
    return f"{title}:\n{formatted}"


def build_context(report_context: Any = None, retrieved_docs: list[str] | None = None) -> str:
    sections = []
    report_section = _format_json_section("Power BI runtime context", report_context)
    if report_section:
        sections.append(report_section)
    if retrieved_docs:
        sections.append("Optional project knowledge base:\n" + "\n".join(retrieved_docs))
    if not sections:
        sections.append("No Power BI context was provided. Ask for the report, visual, filters, or selected data needed to answer accurately.")
    return "\n\n".join(sections)
