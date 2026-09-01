from dataclasses import replace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import webhook_app

client = TestClient(webhook_app.app)


def set_settings(monkeypatch, **overrides):
    monkeypatch.setattr(webhook_app, "settings", replace(webhook_app.settings, **overrides))


@patch("app.webhook_app.issue_random_invoices", return_value=[1, 2, 3])
def test_issue_with_valid_token(mock_issue, monkeypatch):
    set_settings(monkeypatch, issue_token="s3cret", issue_until=None)
    response = client.post("/issue", headers={"X-Issue-Token": "s3cret"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "issued": 3}


def test_issue_rejects_missing_or_bad_token(monkeypatch):
    set_settings(monkeypatch, issue_token="s3cret", issue_until=None)
    assert client.post("/issue").status_code == 403
    assert client.post("/issue", headers={"X-Issue-Token": "wrong"}).status_code == 403


def test_issue_disabled_without_configured_token(monkeypatch):
    set_settings(monkeypatch, issue_token=None)
    assert client.post("/issue", headers={"X-Issue-Token": "x"}).status_code == 503


@patch("app.webhook_app.issue_random_invoices")
def test_issue_noop_after_window(mock_issue, monkeypatch):
    set_settings(monkeypatch, issue_token="s3cret", issue_until="2000-01-01T00:00:00+00:00")
    response = client.post("/issue", headers={"X-Issue-Token": "s3cret"})
    assert response.json() == {"status": "window-closed", "issued": 0}
    mock_issue.assert_not_called()
