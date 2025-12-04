
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
from ..services.crud import list_team_members, create_team_member, update_team_member, delete_team_member
from ..services.auth_deps import get_current_user, require_role
from ..utils.logger import get_logger
logger = get_logger(__name__)

router = APIRouter(prefix="/settings/users", tags=["settings-users"])


@router.get("/", response_model=List[Dict[str, Any]])
async def get_users(user: Dict[str, Any] = Depends(get_current_user)):
    try:
        org_id = user.get("organization_id") or user.get("org_id")
        members = await list_team_members(org_id)
        logger.info(f"Fetched {len(members)} team members for org_id: {org_id}")
        return members
    except Exception as e:
        logger.error(f"Failed to fetch team members: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch team members")


@router.post("/", dependencies=[Depends(require_role(["Admin"]))])
async def post_user(payload: Dict[str, Any], user: Dict[str, Any] = Depends(get_current_user)):
    try:
        payload["organization_id"] = user.get("organization_id") or user.get("org_id")
        member = await create_team_member(payload)
        logger.info(f"Created team member for org_id: {payload['organization_id']}")
        return member
    except Exception as e:
        logger.error(f"Failed to create team member: {e}")
        raise HTTPException(status_code=500, detail="Failed to create team member")


@router.put("/{member_id}", dependencies=[Depends(require_role(["Admin"]))])
async def put_user(member_id: str, payload: Dict[str, Any]):
    try:
        updated = await update_team_member(member_id, payload)
        if not updated:
            logger.warning(f"Member not found: {member_id}")
            raise HTTPException(status_code=404, detail="Member not found")
        logger.info(f"Updated team member: {member_id}")
        return {"message": "updated"}
    except Exception as e:
        logger.error(f"Failed to update team member: {e}")
        raise HTTPException(status_code=500, detail="Failed to update team member")


@router.delete("/{member_id}", dependencies=[Depends(require_role(["Admin"]))])
async def del_user(member_id: str):
    try:
        deleted = await delete_team_member(member_id)
        if not deleted:
            logger.warning(f"Member not found: {member_id}")
            raise HTTPException(status_code=404, detail="Member not found")
        logger.info(f"Deleted team member: {member_id}")
        return {"message": "deleted"}
    except Exception as e:
        logger.error(f"Failed to delete team member: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete team member")
