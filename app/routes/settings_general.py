

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from ..services.auth_deps import get_current_user, require_role
from datetime import datetime
from pydantic import BaseModel
from ..utils.logger import get_logger
from app.common.db.pg_db import get_pg_conn
import psycopg2.extras
logger = get_logger(__name__)

router = APIRouter(prefix="/settings/general", tags=["settings-general"])


class UpdateGeneral(BaseModel):
    name: str
    timezone: str
    retention_days: str
    org_id: str



@router.get("", response_model=Dict[str, Any])
async def read_general_settings(user: Dict[str, Any] = Depends(get_current_user)):
    try:
        user_id = user.get("id")
        logger.info("Fetching general settings for user")
        logger.debug(f"User ID: {user_id}")

        with get_pg_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Get membership
                cur.execute("""
                    SELECT org_id, role FROM organization_memberships WHERE user_id = %s LIMIT 1
                """, (user_id,))
                membership = cur.fetchone()
                if not membership:
                    logger.warning(f"No membership found for user_id: {user_id}")
                    raise HTTPException(status_code=404, detail="User membership not found")
                org_id = membership["org_id"]
                role = membership["role"]

                # Get organization
                cur.execute("SELECT name, timezone FROM organizations WHERE id = %s LIMIT 1", (org_id,))
                org = cur.fetchone()
                if not org:
                    logger.warning("Settings not found for org_id: %s", org_id)
                    raise HTTPException(status_code=404, detail="Settings not found")
                org_name = org["name"]
                time_zone = org.get("timezone") or "pt"

                # Get retention policy
                cur.execute("SELECT retention_days FROM retention_policies WHERE org_id = %s LIMIT 1", (org_id,))
                rp = cur.fetchone()
                retention_days = str(rp["retention_days"]) if rp and rp.get("retention_days") is not None else ""

        organization = {
            "name": org_name,
            "timezone": time_zone,
        }
        retention = {
            "retention_days": retention_days,
        }
        generalSettings = {
            "organization": organization,
            "retention": retention,
        }
        logger.debug(f"General Settings Data: {generalSettings}")
        return {
            "generalSettings": generalSettings,
            "org_id": org_id,
            "role": role,
            "success": "General settings fetched successfully",
        }
    except Exception as e:
        logger.error(f"Failed to fetch general settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch general settings")


@router.patch("", dependencies=[Depends(require_role(["Admin"]))])
async def patch_general_settings(payload: Dict[str, Any], user: Dict[str, Any] = Depends(get_current_user)):
    try:
        user_id = user.get("id")
        logger.info("Updating general settings for user")
        with get_pg_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Get membership
                cur.execute("SELECT org_id FROM organization_memberships WHERE user_id = %s LIMIT 1", (user_id,))
                membership = cur.fetchone()
                if not membership:
                    logger.warning(f"No membership found for user_id: {user_id}")
                    raise HTTPException(status_code=404, detail="User membership not found")
                org_id = membership["org_id"]

                # Check org exists
                cur.execute("SELECT id FROM organizations WHERE id = %s LIMIT 1", (org_id,))
                org = cur.fetchone()
                if not org:
                    logger.warning("Organization not found for org_id: %s", org_id)
                    raise HTTPException(status_code=404, detail="Organization not found")

                # Update organizations
                update_data = {}
                rp_update_data = {}
                update_data["name"] = payload["organization"]["name"]
                # update_data["timezone"] = payload["organization"]["timezone"]
                rp_update_data["retention_days"] = payload["retention"]["retention_days"]

                # if update_data:
                #     cur.execute(
                #         "UPDATE organizations SET name = %s, timezone = %s WHERE id = %s",
                #         (update_data["name"], update_data["timezone"], org_id)
                #     )

                if rp_update_data:
                    cur.execute(
                        "UPDATE retention_policies SET retention_days = %s WHERE org_id = %s",
                        (rp_update_data["retention_days"], org_id)
                    )
                conn.commit()

        generalSettings = {
            "organization": update_data,
            "retention": rp_update_data,
        }
        logger.debug(f"Updated General Settings Data: {generalSettings}")
        return {
            "generalSettings": generalSettings,
            "success": "General settings update successfully",
        }
    except Exception as e:
        logger.error(f"Failed to update general settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to update general settings")




