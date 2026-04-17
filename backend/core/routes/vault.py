"""
Vault routes — add/retrieve/delete encrypted secrets.
Values are NEVER returned in GET responses (only key names are exposed).
"""
from fastapi import APIRouter, HTTPException

from core.models import VaultSetRequest
from core.vault import get_vault

router = APIRouter(prefix="/api/vault", tags=["vault"])


@router.get("/keys")
def list_keys():
    """Return all stored key names. Values are never exposed."""
    return {"keys": get_vault().list_keys()}


@router.get("/has/{key}")
def has_key(key: str):
    return {"key": key, "exists": get_vault().has(key)}


@router.put("/{key}", status_code=204)
def set_key(key: str, body: VaultSetRequest):
    """Store or update an encrypted secret."""
    if not key.isidentifier() and not all(c.isalnum() or c in "_-." for c in key):
        raise HTTPException(status_code=400, detail="Key contains invalid characters.")
    get_vault().set(key, body.value)


@router.delete("/{key}", status_code=204)
def delete_key(key: str):
    if not get_vault().delete(key):
        raise HTTPException(status_code=404, detail=f"Key '{key}' not found.")
