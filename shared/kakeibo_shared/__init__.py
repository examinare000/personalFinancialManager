"""kakeibo_shared 共有コードパッケージのエントリポイント。

サービス（api / worker 等）から ``kakeibo_shared.config`` ``kakeibo_shared.logging``
``kakeibo_shared.db`` ``kakeibo_shared.domain`` を import して利用する。
本ファイル自体はバージョン文字列の単一情報源として機能する。
"""

from __future__ import annotations

# pyproject.toml の version と一致させる。リリース時は pyproject.toml と
# 本ファイルを同じコミットで更新する運用とする（agent-rules/10-git-strategy.md）。
__version__: str = "0.1.0"

__all__ = ["__version__"]
