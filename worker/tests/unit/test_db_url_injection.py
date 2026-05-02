"""build_database_url のパスワード注入契約テスト。

Docker secret 経由のパスワードを SQLAlchemy URL.set で注入する仕様（ADR-016）の
振る舞いを契約として固定する。

検証範囲:
- PG_PASSWORD_FILE 経由のパスワードが URL.password に設定されること
- DATABASE_URL に password が既に含まれていれば優先（開発 .env 運用の保全）
- 双方未供給時は URL.password=None のまま（fail-open: 接続時に DB が 28P01 を返す）
- URL.__repr__ が password を *** にマスク（ログ漏洩防止の二重防壁）

設計準拠:
- docs/adr/016-database-password-injection-strategy.md
- agent-rules/12-security-guidelines.md §4
"""

from __future__ import annotations

from pathlib import Path

import pytest


def test_build_database_urlがpg_passwordをURLに注入する(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """PG_PASSWORD_FILE 経由のパスワードが URL.password に設定されること。"""
    secret_file = tmp_path / "pg_password.txt"
    secret_file.write_text("super-secret-pw\n", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://kakeibo@postgres:5432/kakeibo")
    monkeypatch.setenv("PG_PASSWORD_FILE", str(secret_file))
    monkeypatch.delenv("ANTHROPIC_API_KEY_FILE", raising=False)
    monkeypatch.delenv("PAYPAL_API_SECRET_FILE", raising=False)
    monkeypatch.delenv("GMAIL_OAUTH_TOKEN_FILE", raising=False)

    from kakeibo_shared.config import Settings
    from kakeibo_shared.db.session import build_database_url

    url = build_database_url(Settings())  # pyright: ignore[reportCallIssue]
    assert url.password == "super-secret-pw"
    assert url.username == "kakeibo"
    assert url.host == "postgres"
    assert url.database == "kakeibo"


def test_build_database_urlはURL内のpasswordを優先する(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """開発 .env で URL に devpassword が含まれている場合、PG_PASSWORD_FILE より優先される。

    開発時の埋込み URL を壊さないことで、本変更の後方互換性を保証する。
    """
    secret_file = tmp_path / "pg_password.txt"
    secret_file.write_text("from-file\n", encoding="utf-8")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://kakeibo:from-url@localhost:5432/kakeibo",
    )
    monkeypatch.setenv("PG_PASSWORD_FILE", str(secret_file))
    monkeypatch.delenv("ANTHROPIC_API_KEY_FILE", raising=False)
    monkeypatch.delenv("PAYPAL_API_SECRET_FILE", raising=False)
    monkeypatch.delenv("GMAIL_OAUTH_TOKEN_FILE", raising=False)

    from kakeibo_shared.config import Settings
    from kakeibo_shared.db.session import build_database_url

    assert build_database_url(Settings()).password == "from-url"  # pyright: ignore[reportCallIssue]


def test_build_database_urlはpg_password未設定時にURLをそのまま返す(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """secret 未供給かつ URL も password 無しの場合、URL.password は None のまま（fail-open）。

    隠蔽せず素のままを返すことで、接続失敗時に DB 側の 28P01 が出て診断が容易になる。
    """
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://kakeibo@postgres:5432/kakeibo")
    monkeypatch.delenv("PG_PASSWORD_FILE", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY_FILE", raising=False)
    monkeypatch.delenv("PAYPAL_API_SECRET_FILE", raising=False)
    monkeypatch.delenv("GMAIL_OAUTH_TOKEN_FILE", raising=False)

    from kakeibo_shared.config import Settings
    from kakeibo_shared.db.session import build_database_url

    assert build_database_url(Settings()).password is None  # pyright: ignore[reportCallIssue]


def test_build_database_url結果のreprがpasswordをマスクする(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """SQLAlchemy URL.__repr__ が password を *** にマスクすること。

    Settings.__repr__ のマスクと併せた二重防壁。create_engine の例外メッセージ等で
    URL がそのまま出力される経路でも secret が露出しないことを保証する。
    """
    secret_file = tmp_path / "pg_password.txt"
    secret_file.write_text("must-not-leak\n", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://kakeibo@postgres:5432/kakeibo")
    monkeypatch.setenv("PG_PASSWORD_FILE", str(secret_file))
    monkeypatch.delenv("ANTHROPIC_API_KEY_FILE", raising=False)
    monkeypatch.delenv("PAYPAL_API_SECRET_FILE", raising=False)
    monkeypatch.delenv("GMAIL_OAUTH_TOKEN_FILE", raising=False)

    from kakeibo_shared.config import Settings
    from kakeibo_shared.db.session import build_database_url

    rendered = repr(build_database_url(Settings()))  # pyright: ignore[reportCallIssue]
    assert "must-not-leak" not in rendered, (
        f"URL の repr に生のパスワードが露出しています: {rendered!r}"
    )
    assert "***" in rendered, f"URL の repr で password がマスク表現になっていません: {rendered!r}"


def test_build_database_urlは空文字列passwordを意図的指定として尊重する(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """URL に ``:@`` で空 password が明示されている場合、PG_PASSWORD_FILE より優先される。

    SQLAlchemy 仕様で ``url.password`` は空文字列を保持する（None と区別される）。
    本ヘルパは「URL 内 password を最優先」契約に従い、空文字列も意図的指定と解釈する。
    秘匿でない接続（信頼ネットワーク内の `local trust` 等）を想定した運用余地を残す設計判断。
    """
    secret_file = tmp_path / "pg_password.txt"
    secret_file.write_text("from-file\n", encoding="utf-8")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://kakeibo:@postgres:5432/kakeibo",
    )
    monkeypatch.setenv("PG_PASSWORD_FILE", str(secret_file))
    monkeypatch.delenv("ANTHROPIC_API_KEY_FILE", raising=False)
    monkeypatch.delenv("PAYPAL_API_SECRET_FILE", raising=False)
    monkeypatch.delenv("GMAIL_OAUTH_TOKEN_FILE", raising=False)

    from kakeibo_shared.config import Settings
    from kakeibo_shared.db.session import build_database_url

    assert build_database_url(Settings()).password == ""  # pyright: ignore[reportCallIssue]
