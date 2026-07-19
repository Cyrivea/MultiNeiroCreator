from fastapi import APIRouter, Depends

from core.deps import verify_token
from schemas.project import AutoSaveProjectRequest, CreateProjectRequest
from services.project_service import create_project as service_create_project
from services.project_service import create_project_backup, ensure_project_for_auto_save, list_recent_projects


router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("")
def create_project(req: CreateProjectRequest, user=Depends(verify_token)):
    return {"project": service_create_project(user["id"], req.name)}


@router.get("/recent")
def get_recent_projects(limit: int = 8, user=Depends(verify_token)):
    safe_limit = max(1, min(limit, 20))
    return {"items": list_recent_projects(user["id"], safe_limit)}


@router.post("/auto-save/ensure")
def ensure_auto_save_project(req: AutoSaveProjectRequest, user=Depends(verify_token)):
    project = ensure_project_for_auto_save(
        user["id"],
        name=req.name,
        project_path=req.project_path,
        save_mode=req.save_mode,
    )
    return {"project": project}


@router.post("/auto-save/backup")
def backup_project(req: AutoSaveProjectRequest, user=Depends(verify_token)):
    return create_project_backup(
        user["id"],
        name=req.name,
        project_path=req.project_path,
        save_mode=req.save_mode,
    )
