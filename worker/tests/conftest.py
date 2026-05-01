"""worker/tests/ 共通フィクスチャ。

worker コンテナはコンテナ内 ``/app`` 直下にホストの ``shared/`` ``worker/src``
``api/src`` ``tests/`` ``worker/tests/`` ``api/tests/`` を bind mount する
（compose.override.yml）。本ファイル位置から見たリポジトリルートは
``../..`` （コンテナ内では ``/app``、ホストではリポジトリルート）。
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def repo_root() -> Path:
    """リポジトリルート（ホスト）／``/app``（コンテナ）を返すフィクスチャ。

    本テストファイルは ``<repo>/worker/tests/`` に配置されている。
    親 2 つ上がリポジトリルート（compose の build context）。
    """
    return Path(__file__).resolve().parent.parent.parent
