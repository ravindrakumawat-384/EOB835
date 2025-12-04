from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
from ..services.crud import list_team_members, create_team_member, update_team_member, delete_team_member
from ..services.auth_deps import get_current_user, require_role

router = APIRouter(prefix="/settings/users", tags=["settings-users"])


@router.get("/", response_model=List[Dict[str, Any]])
async def get_users(user: Dict[str, Any] = Depends(get_current_user)):
    org_id = user.get("organization_id") or user.get("org_id")
    return await list_team_members(org_id)


@router.post("/", dependencies=[Depends(require_role(["Admin"]))])
async def post_user(payload: Dict[str, Any], user: Dict[str, Any] = Depends(get_current_user)):
    payload["organization_id"] = user.get("organization_id") or user.get("org_id")
    member = await create_team_member(payload)
    return member


@router.put("/{member_id}", dependencies=[Depends(require_role(["Admin"]))])
async def put_user(member_id: str, payload: Dict[str, Any]):
    updated = await update_team_member(member_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"message": "updated"}


@router.delete("/{member_id}", dependencies=[Depends(require_role(["Admin"]))])
async def del_user(member_id: str):
    deleted = await delete_team_member(member_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"message": "deleted"}
