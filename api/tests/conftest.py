"""api/tests/ 共通フィクスチャ。

api コンテナはコンテナ内 ``/workspace`` （compose.override.yml で
ホストリポジトリ全体をマウント）をリポジトリルートとして見る。
本テストは worker コンテナから ``docker compose run --rm worker pytest``
で実行される（api コンテナには pytest 等の dev 依存が無いため）。
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def repo_root() -> Path:
    """リポジトリルート（ホスト）／``/workspace``（コンテナ）を返すフィクスチャ。

    本テストファイルは ``<repo>/api/tests/`` に配置されている。
    親 2 つ上がリポジトリルート（compose の build context）。
    """
    return Path(__file__).resolve().parent.parent.parent
