from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI

from core.database import init_db
from routers.assistant import router as assistant_router
from routers.auth import router as auth_router
from routers.projects import router as projects_router
from routers.workstation import router as workstation_router
from services.project_service import init_projects_table

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


app.include_router(workstation_router)
app.include_router(auth_router)
app.include_router(assistant_router)
app.include_router(projects_router)


@app.on_event("startup")
def bootstrap() -> None:
    init_db()
    init_projects_table()
