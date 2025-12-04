from fastapi import APIRouter, Depends
from typing import List, Optional, Dict, Any
from ..services.crud import list_audit_logs
from ..services.auth_deps import get_current_user

router = APIRouter(prefix="/settings/audit-logs", tags=["settings-audit-logs"])


@router.get("/", response_model=List[Dict[str, Any]])
async def get_logs(
    user_name: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 100,
    user: Dict[str, Any] = Depends(get_current_user),
):
    org_id = user.get("organization_id") or user.get("org_id")
    return await list_audit_logs(org_id, user_name=user_name, category=category, limit=limit)
