"""Tests for /api/setup/* endpoints — public, no auth required."""
import pytest


class TestSetupStatus:
    def test_returns_correct_schema(self, test_client):
        resp = test_client.get("/api/setup/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "configured" in data
        assert "has_vault_key" in data
        assert "has_api_token" in data

    def test_all_fields_are_bool(self, test_client):
        data = test_client.get("/api/setup/status").json()
        assert isinstance(data["configured"], bool)
        assert isinstance(data["has_vault_key"], bool)
        assert isinstance(data["has_api_token"], bool)

    def test_no_auth_header_required(self, test_client):
        """Setup endpoint must be reachable without any Authorization header."""
        resp = test_client.get("/api/setup/status")
        assert resp.status_code == 200


class TestGenerateKey:
    def test_returns_non_empty_key(self, test_client):
        resp = test_client.get("/api/setup/generate-key")
        assert resp.status_code == 200
        data = resp.json()
        assert "key" in data
        assert len(data["key"]) > 20

    def test_keys_are_unique(self, test_client):
        key1 = test_client.get("/api/setup/generate-key").json()["key"]
        key2 = test_client.get("/api/setup/generate-key").json()["key"]
        assert key1 != key2

    def test_no_auth_required(self, test_client):
        assert test_client.get("/api/setup/generate-key").status_code == 200
