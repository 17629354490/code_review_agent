"""API 依赖：鉴权等。"""
from fastapi import Header, HTTPException

from app.config import settings


async def require_api_key(x_api_key: str | None = Header(None, alias="X-API-Key")) -> None:
    """若配置了 API Keys，则必须携带有效 Key。"""
    if not settings.allowed_api_keys:
        return
    if not x_api_key or x_api_key not in settings.allowed_api_keys:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
