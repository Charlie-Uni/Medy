"""`python -m medops.infrastructure.db.login_users` hands every configured login password to `provision`, and the
optional users (restricted, loop) may be left unset without blocking the mandatory three."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

from pydantic import SecretStr

from medops.infrastructure.db import login_users


def _fake_settings(**passwords):
    fields = {k: SecretStr(v) if v else None for k, v in passwords.items()}
    return SimpleNamespace(
        db_app_password=fields.get("app"),
        db_readonly_password=fields.get("readonly"),
        db_admin_password=fields.get("admin"),
        db_restricted_password=fields.get("restricted"),
        db_loop_password=fields.get("loop"),
    )


def _run(monkeypatch, capsys, settings):
    seen: dict[str, object] = {}

    @contextmanager
    def fake_connect(url):
        yield SimpleNamespace(commit=lambda: None)

    def fake_provision(conn, *, prefix, passwords):
        seen["passwords"] = dict(passwords)
        return {k: login_users.username(prefix, k) for k, v in passwords.items() if v}

    monkeypatch.setattr(login_users, "_settings", lambda: settings)
    monkeypatch.setattr(login_users, "_admin_url", lambda: "postgresql://x")
    monkeypatch.setattr(login_users.psycopg, "connect", fake_connect)
    monkeypatch.setattr(login_users, "provision", fake_provision)
    rc = login_users.main([])
    return rc, seen, capsys.readouterr().out


def test_loop_password_reaches_provision(monkeypatch, capsys):
    rc, seen, out = _run(monkeypatch, capsys, _fake_settings(app="a", readonly="r", admin="m", loop="l"))
    assert rc == 0
    assert seen["passwords"] == {"app": "a", "readonly": "r", "admin": "m", "restricted": "", "loop": "l"}
    assert "loop: medops_loop_user (member of medops_loop_role)" in out
    assert "restricted:" not in out and "l" not in out.split("loop:")[0].split()  # passwords are never printed


def test_optional_users_do_not_block_the_mandatory_three(monkeypatch, capsys):
    rc, seen, _ = _run(monkeypatch, capsys, _fake_settings(app="a", readonly="r", admin="m"))
    assert rc == 0 and seen["passwords"]["loop"] == "" and seen["passwords"]["restricted"] == ""


def test_missing_mandatory_password_refuses_before_connecting(monkeypatch, capsys):
    rc, seen, out = _run(monkeypatch, capsys, _fake_settings(app="a", readonly="", admin="m", loop="l"))
    assert rc == 2 and "passwords" not in seen and "readonly" in out and "loop" not in out
