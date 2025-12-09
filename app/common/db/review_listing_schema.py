from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class DropdownOption(BaseModel):
    label: str
    value: Any

class EditableDropdown(BaseModel):
    type: str
    placeholder: Optional[str] = None
    options: List[DropdownOption] = []

class ActionItem(BaseModel):
    type: str
    icon: Optional[str] = None
    styleClass: Optional[str] = None

class TableHeader(BaseModel):
    field: Optional[str] = None
    label: str
    editable: Optional[EditableDropdown] = None
    actions: Optional[List[ActionItem]] = None

class TableRow(BaseModel):
    fileName: str
    payer: Optional[str] = None
    confidence: str
    status: str
    reviewer: Optional[str] = None
    uploaded: Optional[str] = None

class ReviewResponse(BaseModel):
    tableHeaders: List[TableHeader]
    tableData: List[TableRow]
    pagination: Dict[str, Any]
    totalRecords: int