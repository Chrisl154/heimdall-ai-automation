"""
Tests for GET /api/logs/events and GET /api/logs/app.

The module-level log Path constants are patched to isolated tmp_path
locations so no real log files are needed.
"""
import json
from pathlib import Path
from unittest.mock import patch


# ── GET /api/logs/events ──────────────────────────────────────────────────────

class TestGetEvents:
    def _client(self, test_client, event_log_path: Path):
        """Return test_client with _EVENT_LOG redirected to event_log_path."""
        return test_client, event_log_path

    def test_returns_empty_when_file_missing(self, test_client, tmp_path):
        missing = tmp_path / "no_events.jsonl"
        with patch("core.routes.logs._EVENT_LOG", missing):
            resp = test_client.get("/api/logs/events")
        assert resp.status_code == 200
        body = resp.json()
        assert body["events"] == []
        assert body["total"] == 0

    def test_returns_parsed_events(self, test_client, tmp_path):
        log = tmp_path / "events.jsonl"
        entries = [
            {"type": "TASK_STARTED", "task_id": "t1", "message": "start"},
            {"type": "TASK_COMPLETED", "task_id": "t1", "message": "done"},
        ]
        log.write_text("\n".join(json.dumps(e) for e in entries), encoding="utf-8")

        with patch("core.routes.logs._EVENT_LOG", log):
            body = test_client.get("/api/logs/events").json()

        assert body["total"] == 2
        assert len(body["events"]) == 2
        assert body["events"][0]["type"] == "TASK_STARTED"
        assert body["events"][1]["type"] == "TASK_COMPLETED"

    def test_limit_returns_only_last_n_events(self, test_client, tmp_path):
        log = tmp_path / "events.jsonl"
        lines = [json.dumps({"seq": i}) for i in range(10)]
        log.write_text("\n".join(lines), encoding="utf-8")

        with patch("core.routes.logs._EVENT_LOG", log):
            body = test_client.get("/api/logs/events?limit=3").json()

        assert body["total"] == 10
        assert len(body["events"]) == 3
        # Should be the LAST 3
        assert body["events"][-1]["seq"] == 9

    def test_skips_malformed_json_lines(self, test_client, tmp_path):
        log = tmp_path / "events.jsonl"
        log.write_text(
            '{"type": "OK"}\nnot json at all\n{"type": "ALSO_OK"}\n',
            encoding="utf-8",
        )
        with patch("core.routes.logs._EVENT_LOG", log):
            body = test_client.get("/api/logs/events").json()

        assert body["total"] == 3  # counts all lines including bad ones
        assert len(body["events"]) == 2  # only valid JSON returned
        types = {e["type"] for e in body["events"]}
        assert types == {"OK", "ALSO_OK"}

    def test_blank_lines_are_ignored(self, test_client, tmp_path):
        log = tmp_path / "events.jsonl"
        log.write_text('{"type": "A"}\n\n\n{"type": "B"}\n', encoding="utf-8")
        with patch("core.routes.logs._EVENT_LOG", log):
            body = test_client.get("/api/logs/events").json()
        assert len(body["events"]) == 2

    def test_default_limit_is_500(self, test_client, tmp_path):
        log = tmp_path / "events.jsonl"
        lines = [json.dumps({"seq": i}) for i in range(600)]
        log.write_text("\n".join(lines), encoding="utf-8")

        with patch("core.routes.logs._EVENT_LOG", log):
            body = test_client.get("/api/logs/events").json()

        assert body["total"] == 600
        assert len(body["events"]) == 500


# ── GET /api/logs/app ─────────────────────────────────────────────────────────

class TestGetAppLog:
    def test_returns_not_exists_when_file_missing(self, test_client, tmp_path):
        missing = tmp_path / "no.log"
        with patch("core.routes.logs._APP_LOG", missing):
            body = test_client.get("/api/logs/app").json()
        assert body["exists"] is False
        assert body["lines"] == []

    def test_returns_log_lines_when_file_exists(self, test_client, tmp_path):
        log = tmp_path / "app.log"
        log.write_text("INFO starting\nERROR something failed\nINFO shutdown\n",
                       encoding="utf-8")
        with patch("core.routes.logs._APP_LOG", log):
            body = test_client.get("/api/logs/app").json()
        assert body["exists"] is True
        assert body["total"] == 3
        assert "INFO starting" in body["lines"]
        assert "ERROR something failed" in body["lines"]

    def test_limit_returns_only_last_n_lines(self, test_client, tmp_path):
        log = tmp_path / "app.log"
        log.write_text("\n".join(f"line {i}" for i in range(20)), encoding="utf-8")
        with patch("core.routes.logs._APP_LOG", log):
            body = test_client.get("/api/logs/app?lines=5").json()
        assert body["total"] == 20
        assert len(body["lines"]) == 5
        assert body["lines"][-1] == "line 19"

    def test_exists_true_when_file_present(self, test_client, tmp_path):
        log = tmp_path / "app.log"
        log.write_text("hello\n", encoding="utf-8")
        with patch("core.routes.logs._APP_LOG", log):
            body = test_client.get("/api/logs/app").json()
        assert body["exists"] is True

    def test_empty_log_file_returns_empty_list(self, test_client, tmp_path):
        log = tmp_path / "app.log"
        log.write_text("", encoding="utf-8")
        with patch("core.routes.logs._APP_LOG", log):
            body = test_client.get("/api/logs/app").json()
        assert body["exists"] is True
        assert body["lines"] == []
        assert body["total"] == 0
