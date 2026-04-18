"""
Token authentication dependency for FastAPI.

Set HEIMDALL_API_TOKEN in .env to enable auth.
If the variable is empty or unset, all requests are allowed (dev mode).
"""
import os
from fastapi import HTTPException, Request, status


def require_token(request: Request) -> None:
    token = os.getenv("HEIMDALL_API_TOKEN", "").strip()
    if not token:
        return  # auth disabled — dev/local mode
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    if auth_header[7:] != token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
