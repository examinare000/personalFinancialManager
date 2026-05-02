"""postgres/tests/ 共通フィクスチャ。

worker/tests/conftest.py と同じ慣習で、テストファイルから 2 階層上の
リポジトリルートを `repo_root` フィクスチャとして公開する。
postgres/tests/unit/db/test_migration_idempotency.py が
`repo_root / "postgres/src/alembic.ini"` を解決するために必要。
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def repo_root() -> Path:
    """リポジトリルート（ホスト）／``/workspace``（コンテナ）を返す。

    本ファイルは ``<repo>/postgres/tests/conftest.py`` に配置されるため、
    親 2 つ上がリポジトリルート（compose の build context）。
    """
    return Path(__file__).resolve().parent.parent.parent
