from pydantic import BaseModel, Field
from enum import Enum
from typing import List, Any

class WidgetDTO(BaseModel):
    uploaded: int
    processed: int
    pendingReview: int
    accuracyPercent: float
    exceptions: int
    needsTemplate: int

class ActionDef(BaseModel):
    type: str
    icon: str
    styleClass: str

class TableHeader(BaseModel):
    field: str | None = None
    label: str
    actions: List[ActionDef] | None = None

class RecentRow(BaseModel):
    fileName: str
    payer: str | None
    status: str
    uploaded: str

class RecentUploadsData(BaseModel):
    tableHeaders: List[TableHeader]
    tableData: List[RecentRow]

class DashboardResponse(BaseModel):
    widgets: WidgetDTO
    recentUploadsData: RecentUploadsData
    meta: dict