"""``Settings.__repr__()`` のシークレット非露出検証テスト。

Issue #1 DoD3「API ログにシークレット非露出」を補強するため、
Settings インスタンスを ``repr`` した文字列に機微値が含まれないことを
契約として固定する。``shared/kakeibo_shared/config.py`` の ``__repr__``
実装と、``shared/kakeibo_shared/logging.py`` の redact processor が連携して
シークレット漏洩を防ぐ。本テストは前者の振る舞いだけを直接検証する。
（パスは ADR-014 のサービス境界別レイアウトに準拠）

設計準拠:
- 計画レポート §5.1（write_tests 仕様）
- agent-rules/12-security-guidelines.md §4
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# src レイアウトを sys.path に追加し、editable install されていなくても
# import が解決できるようにする（tests/test_environment.py と同じパターン）。
_SRC = Path(__file__).resolve().parent.parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def test_settings_reprがpasswordをマスクする(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``repr(settings)`` の文字列に ``pg_password`` の値が含まれず、
    ``[REDACTED]`` プレースホルダで置換されていること。

    Docker secret 由来のパスワードがロガーやスタックトレースで
    表示されないことを担保する。``database_url`` のような非機密フィールドは
    値が露出する設計（運用時の可視性のため）。
    """
    secret_value = "super-secret-pg-password-do-not-leak"
    secret_file = tmp_path / "pg_password.txt"
    secret_file.write_text(f"{secret_value}\n", encoding="utf-8")

    monkeypatch.setenv("DATABASE_URL", "postgresql://x@y:5432/z")
    monkeypatch.setenv("PG_PASSWORD_FILE", str(secret_file))
    # 他の secret 系 env が CI で残っていても干渉しないよう明示的に解除する。
    monkeypatch.delenv("ANTHROPIC_API_KEY_FILE", raising=False)
    monkeypatch.delenv("PAYPAL_API_SECRET_FILE", raising=False)
    monkeypatch.delenv("GMAIL_OAUTH_TOKEN_FILE", raising=False)

    from kakeibo_shared.config import Settings

    settings = Settings()  # pyright: ignore[reportCallIssue]

    # 前提: PG_PASSWORD_FILE 経由で値が読み込まれていること。
    # （マスクの確認は値を一度ロードしてから行う必要がある。）
    assert settings.pg_password == secret_value, (
        "テスト前提条件: PG_PASSWORD_FILE 経由で pg_password が読み込まれること"
    )

    rendered = repr(settings)
    assert secret_value not in rendered, (
        f"repr(settings) に生のパスワードが露出しています: {rendered!r}"
    )
    # 他の機微フィールド（anthropic_api_key 等）のマスクで条件を満たせてしまう
    # 曖昧アサートを避け、pg_password 自体がマスクされていることを直接検証する。
    assert "pg_password='[REDACTED]'" in rendered, (
        f"pg_password がマスク表現で出力されていません: {rendered!r}"
    )


def test_settings_reprが非機密フィールドはマスクしない(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``database_url`` のような非機密フィールドは ``repr`` で値が表示されること。

    過剰マスクは運用時のトラブルシュートを阻害するため、マスク対象は
    ``_SENSITIVE_KEYWORDS`` に該当するフィールドだけに限定されている
    ことを検証する。
    """
    db_url = "postgresql://kakeibo@postgres:5432/kakeibo"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.delenv("PG_PASSWORD_FILE", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY_FILE", raising=False)
    monkeypatch.delenv("PAYPAL_API_SECRET_FILE", raising=False)
    monkeypatch.delenv("GMAIL_OAUTH_TOKEN_FILE", raising=False)

    from kakeibo_shared.config import Settings

    settings = Settings()  # pyright: ignore[reportCallIssue]
    rendered = repr(settings)

    assert db_url in rendered, (
        f"非機密フィールド database_url の値が repr に含まれていません: {rendered!r}"
    )
