from fastapi import APIRouter, Depends, HTTPException

from core.deps import verify_token
from schemas.project import CreateProjectRequest
from services.project_service import create_project as service_create_project
from services.project_service import discard_project as service_discard_project
from services.project_service import get_project as service_get_project
from services.project_service import list_recent_projects
from services.project_service import mark_project_saved as service_mark_project_saved
from services.project_service import touch_project_opened as service_touch_project_opened

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("")
def create_project(req: CreateProjectRequest, user=Depends(verify_token)):
    return {"project": service_create_project(user["id"], req.name, req.project_path)}


@router.get("/recent")
def get_recent_projects(limit: int = 8, user=Depends(verify_token)):
    safe_limit = max(1, min(limit, 20))
    return {"items": list_recent_projects(user["id"], safe_limit)}


@router.get("/{project_id}")
def get_project(project_id: int, user=Depends(verify_token)):
    project = service_get_project(user["id"], project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在或已失效")
    # B29：被放弃且从未保存过的工程 = 彻底失效（用户拍板：没保存的就不要了）；
    # 被放弃但保存过的 → 返回最后保存版本（本地磁盘），面板复活交由 /opened touch 处理
    if project.discarded_at is not None and project.saved_at is None:
        raise HTTPException(status_code=404, detail="项目不存在或已失效")
    return {"project": project}


@router.post("/{project_id}/discard")
def discard_project(project_id: int, user=Depends(verify_token)):
    """「不保存」放弃：软删除出面板。仅对从未保存过的工程有意义；
    保存过的工程丢弃的只是未保存修改，不应调此接口（前端已按 saved_at 分流）。"""
    project = service_discard_project(user["id"], project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"project": project}


@router.post("/{project_id}/saved")
def mark_project_saved(project_id: int, user=Depends(verify_token)):
    """前端真实写盘成功后上报（自动保存 tick / 用户显式保存）。"""
    project = service_mark_project_saved(user["id"], project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"project": project}


@router.post("/{project_id}/opened")
def touch_project_opened(project_id: int, user=Depends(verify_token)):
    """真实打开时刻上报：刷新 last_opened_at + 被放弃（但保存过）的工程复活。"""
    project = service_touch_project_opened(user["id"], project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在或已失效")
    if project.discarded_at is not None and project.saved_at is None:
        raise HTTPException(status_code=404, detail="项目不存在或已失效")
    return {"project": project}
