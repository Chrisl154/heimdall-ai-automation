"""Tests for core.vault.Vault."""
import pytest
from cryptography.fernet import Fernet

from core.vault import Vault, VaultError


class TestVaultSetGet:
    def test_set_and_get(self, vault_env):
        vault = Vault()
        vault.set("test_key", "test_value")
        assert vault.get("test_key") == "test_value"

    def test_get_returns_default_when_missing(self, vault_env):
        vault = Vault()
        assert vault.get("nonexistent", "default") == "default"
        assert vault.get("nonexistent") is None

    def test_require_raises_when_missing(self, vault_env):
        vault = Vault()
        with pytest.raises(VaultError, match="Required secret 'missing' not found"):
            vault.require("missing")

    def test_require_returns_value(self, vault_env):
        vault = Vault()
        vault.set("my_key", "my_value")
        assert vault.require("my_key") == "my_value"


class TestVaultDelete:
    def test_delete_existing_key(self, vault_env):
        vault = Vault()
        vault.set("to_delete", "value")
        assert vault.delete("to_delete") is True
        assert vault.get("to_delete") is None

    def test_delete_nonexistent_key(self, vault_env):
        vault = Vault()
        assert vault.delete("nonexistent") is False


class TestVaultListKeys:
    def test_list_keys_returns_all_keys(self, vault_env):
        vault = Vault()
        vault.set("key1", "value1")
        vault.set("key2", "value2")
        keys = vault.list_keys()
        assert "key1" in keys
        assert "key2" in keys
        assert "key3" not in keys


class TestVaultHas:
    def test_has_returns_true_for_existing_key(self, vault_env):
        vault = Vault()
        vault.set("exists", "value")
        assert vault.has("exists") is True

    def test_has_returns_false_for_missing_key(self, vault_env):
        vault = Vault()
        assert vault.has("missing") is False


class TestVaultBulkSet:
    def test_bulk_set_allows_multiple_secrets(self, vault_env):
        vault = Vault()
        vault.bulk_set({"a": "1", "b": "2", "c": "3"})
        assert vault.get("a") == "1"
        assert vault.get("b") == "2"
        assert vault.get("c") == "3"


class TestVaultError:
    def test_vault_error_on_invalid_key(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HEIMDALL_VAULT_KEY", "not-a-valid-fernet-key")
        monkeypatch.setenv("HEIMDALL_DATA_DIR", str(tmp_path))
        with pytest.raises(VaultError, match="Invalid HEIMDALL_VAULT_KEY"):
            Vault()

    def test_vault_error_on_wrong_decryption_key(self, vault_env, monkeypatch):
        # Write a vault with the original key
        vault = Vault()
        vault.set("secret", "encrypted_value")
        # Now swap in a different key — loading the same file should fail
        different_key = Fernet.generate_key().decode()
        monkeypatch.setenv("HEIMDALL_VAULT_KEY", different_key)
        with pytest.raises(VaultError, match="Vault decryption failed"):
            Vault()


class TestVaultRoundTrip:
    def test_round_trip_set_get(self, vault_env):
        vault = Vault()
        vault.set("roundtrip", "secret_data")
        assert vault.get("roundtrip") == "secret_data"

    def test_round_trip_new_instance(self, vault_env):
        vault1 = Vault()
        vault1.set("persistent", "value")
        vault2 = Vault()
        assert vault2.get("persistent") == "value"
