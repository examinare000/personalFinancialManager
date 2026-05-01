"""``.env.example`` のキー網羅性検証テスト。

Issue #1 のチェックボックス 5.2「.env.example の最新化」要件に対応。
``api/src/kakeibo_api/__main__.py`` の ``API_HOST`` / ``API_PORT`` /
``FLASK_DEBUG``、``worker/src/kakeibo_worker/main.py`` の
``WORKER_HEARTBEAT_PATH``、``compose.override.yml`` の ``LOG_LEVEL``
などは ``.env.example`` 上で雛形が示される必要がある。
（パスは ADR-014 のサービス境界別レイアウトに準拠）

設計準拠:
- 計画レポート §4.4 / §5.1（write_tests 仕様）
- architect-review.md（ARCH-NEW-test_environment-bloat の責務分離）
"""

from __future__ import annotations

from pathlib import Path


def test_envExampleが必要なキーを網羅する(repo_root: Path) -> None:
    """``.env.example`` がアプリ参照に必要な環境変数キーをすべて宣言していること。"""
    env_example_path = repo_root / ".env.example"
    assert env_example_path.exists(), ".env.example が存在しません"

    content = env_example_path.read_text(encoding="utf-8")
    required_keys = [
        "DATABASE_URL=",
        "PG_PASSWORD_FILE=",
        "API_HOST=",
        "API_PORT=",
        "FLASK_DEBUG=",
        "LOG_LEVEL=",
        "WORKER_HEARTBEAT_PATH=",
        "TZ=",
    ]
    for key in required_keys:
        assert key in content, f".env.example に '{key}' 行が必要です"
