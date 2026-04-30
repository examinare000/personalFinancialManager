"""pytest 共通フィクスチャ・設定。

リポジトリルートを sys.path に追加せず、`src` レイアウトの import が
パッケージインストール（uv sync の editable install）経由で解決される
前提に立つ。テスト固有の補助フィクスチャだけを置く。
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def repo_root() -> Path:
    """リポジトリルートを返すフィクスチャ。

    各テストが docs / secrets / compose 等のリポジトリ資産にアクセスする
    際の基準パスとして使う。テストファイルの位置から決定論的に算出する。
    """
    return Path(__file__).resolve().parent.parent
