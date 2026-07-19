from fastapi import APIRouter
from fastapi.responses import FileResponse


router = APIRouter(tags=["static"])


@router.get("/")
def index():
    return FileResponse("index.html")


@router.get("/logo.png")
def logo():
    return FileResponse("logo.png")


@router.get("/CascadiaMono.ttf")
def font():
    return FileResponse("CascadiaMono.ttf")


@router.get("/favicon.ico")
async def favicon():
    return FileResponse("logo.png")
