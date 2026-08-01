from fastapi import APIRouter, Depends

from core.deps import verify_token
from schemas.project import CreateProjectRequest
from services.project_service import create_project as service_create_project
from services.project_service import list_recent_projects


router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("")
def create_project(req: CreateProjectRequest, user=Depends(verify_token)):
    return {"project": service_create_project(user["id"], req.name, req.project_path)}


@router.get("/recent")
def get_recent_projects(limit: int = 8, user=Depends(verify_token)):
    safe_limit = max(1, min(limit, 20))
    return {"items": list_recent_projects(user["id"], safe_limit)}
