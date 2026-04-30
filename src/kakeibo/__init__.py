"""kakeibo パッケージのエントリポイント。

公開 API はサブモジュール経由で提供する。本ファイル自体は
バージョン文字列の単一情報源（Single Source of Truth）として機能する。
"""

from __future__ import annotations

# pyproject.toml の version と一致させる。リリース時は pyproject.toml と
# 本ファイルを同じコミットで更新する運用とする（agent-rules/10-git-strategy.md）。
__version__: str = "0.1.0"

__all__ = ["__version__"]
