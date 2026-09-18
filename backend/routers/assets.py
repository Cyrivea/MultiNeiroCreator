"""生成产物静态服务：/assets/{uuid}.png。

- 文件名只放行 uuid-hex + 白名单扩展名，路径穿越进不来。
- 不加鉴权：文件名本身是不可预测的票据（32 位 hex）。前端 <img> 不便携带
  Authorization 头；内容只是生成图，不牵用户私有数据。后续若放敏感素材，
  可改 token 签名 URL（HMAC）再升级。
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from core import config

router = APIRouter(prefix="/assets", tags=["assets"])

_ALLOWED_SUFFIX = {".png", ".jpg", ".jpeg", ".webp"}


@router.get("/{filename}")
def get_asset(filename: str):
    name = Path(filename).name
    if Path(filename).name != filename or Path(name).suffix not in _ALLOWED_SUFFIX:
        raise HTTPException(status_code=404, detail="资产不存在")
    path = Path(config.DOCUMENT_STORAGE_DIR).parent / "assets" / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="资产不存在")
    return FileResponse(path)
