from typing import Any

from pydantic import BaseModel, Field


class DataField(BaseModel):
    table: str | None = None
    column: str
    data_type: str | None = None
    role: str | None = None


class VisualContext(BaseModel):
    visual_id: str | None = None
    visual_type: str | None = None
    title: str | None = None
    fields: list[DataField] = Field(default_factory=list)
    data_points: list[dict[str, Any]] = Field(default_factory=list)


class ReportContext(BaseModel):
    report_name: str | None = None
    page_name: str | None = None
    visual: VisualContext | None = None
    filters: list[dict[str, Any]] = Field(default_factory=list)
    slicers: list[dict[str, Any]] = Field(default_factory=list)
    dataset_schema: list[DataField] = Field(default_factory=list)
    selected_data: list[dict[str, Any]] = Field(default_factory=list)
    user_locale: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CopilotRequest(BaseModel):
    question: str
    report_context: ReportContext | dict[str, Any] | None = None


class CopilotResponse(BaseModel):
    answer: str
    sources: list[str] = []
