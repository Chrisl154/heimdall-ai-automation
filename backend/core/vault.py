"""
Encrypted secret vault.

All API keys, tokens, and passwords are stored encrypted with Fernet
(AES-128-CBC + HMAC-SHA256). The master key lives ONLY in the environment
variable HEIMDALL_VAULT_KEY — never on disk in plain text.

Usage:
    vault = Vault()
    vault.set("anthropic_key", "sk-ant-...")
    key = vault.get("anthropic_key")   # returns plain-text value
"""
import json
import os
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


class VaultError(Exception):
    pass


class Vault:
    def __init__(self, vault_path: str | None = None):
        raw_key = os.getenv("HEIMDALL_VAULT_KEY", "")
        if not raw_key:
            # Auto-generate and print a new key if none is set — dev convenience
            new_key = Fernet.generate_key().decode()
            print(
                f"\n[Heimdall Vault] WARNING: HEIMDALL_VAULT_KEY not set.\n"
                f"  Generated ephemeral key (data will be lost on restart):\n"
                f"  HEIMDALL_VAULT_KEY={new_key}\n"
                f"  Set this in your .env file to persist secrets.\n"
            )
            raw_key = new_key

        try:
            self._fernet = Fernet(raw_key.encode() if isinstance(raw_key, str) else raw_key)
        except Exception as exc:
            raise VaultError(f"Invalid HEIMDALL_VAULT_KEY: {exc}") from exc

        data_dir = os.getenv("HEIMDALL_DATA_DIR", "data")
        self._path = Path(vault_path or f"{data_dir}/vault.enc")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, str] = self._load()

    # ── Internal ─────────────────────────────────────────────────────────────

    def _load(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        try:
            encrypted = self._path.read_bytes()
            plain = self._fernet.decrypt(encrypted)
            return json.loads(plain.decode())
        except InvalidToken:
            raise VaultError(
                "Vault decryption failed — wrong HEIMDALL_VAULT_KEY or vault is corrupt."
            )
        except Exception as exc:
            raise VaultError(f"Failed to load vault: {exc}") from exc

    def _save(self) -> None:
        plain = json.dumps(self._data).encode()
        encrypted = self._fernet.encrypt(plain)
        self._path.write_bytes(encrypted)

    # ── Public API ────────────────────────────────────────────────────────────

    def set(self, key: str, value: str) -> None:
        """Store or update a secret. Value is encrypted immediately."""
        self._data[key] = value
        self._save()

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieve a decrypted secret. Returns default if not found."""
        return self._data.get(key, default)

    def require(self, key: str) -> str:
        """Retrieve a secret; raises VaultError if the key is absent."""
        val = self._data.get(key)
        if not val:
            raise VaultError(
                f"Required secret '{key}' not found in vault. "
                f"Add it via the Settings page or POST /api/vault/{{key}}."
            )
        return val

    def delete(self, key: str) -> bool:
        """Delete a secret. Returns True if it existed."""
        existed = key in self._data
        self._data.pop(key, None)
        if existed:
            self._save()
        return existed

    def list_keys(self) -> list[str]:
        """Return all stored key names (values are never exposed here)."""
        return list(self._data.keys())

    def has(self, key: str) -> bool:
        return key in self._data

    def bulk_set(self, secrets: dict[str, str]) -> None:
        """Set multiple secrets atomically."""
        self._data.update(secrets)
        self._save()


# Module-level singleton — import and use directly
_vault: Vault | None = None


def get_vault() -> Vault:
    global _vault
    if _vault is None:
        _vault = Vault()
    return _vault
