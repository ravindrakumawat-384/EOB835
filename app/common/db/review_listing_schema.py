from pydantic import BaseModel, Field
from enum import Enum
from typing import Any, Dict, List, Optional

# --- response models ---
class TableHeader(BaseModel):
    field: Optional[str] = None
    label: str
    actions: Optional[List[Dict[str, Any]]] = None

class TableRow(BaseModel):
    fileName: str
    payer: Optional[str]
    confidence: str
    status: str
    reviewer: Optional[str]
    uploaded: Optional[str]
    claims: int

class ReviewResponse(BaseModel):
    tableHeaders: List[TableHeader]
    tableData: List[TableRow]
    pagination: Dict[str, Any]
    totalRecords: int