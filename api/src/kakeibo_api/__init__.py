"""kakeibo REST API レイヤ。

Phase 0 では最小ヘルスチェックエンドポイント（``GET /health``）のみ提供し、
Docker / Caddy / 監視系の疎通基盤として機能させる。Phase 3.1 で資産・取引等
のエンドポイントを実装する際は ``app.py`` のファクトリ ``create_app`` から
Blueprint を登録する想定。

公開 API:
- ``create_app()``: Flask アプリケーションファクトリ。
"""

from __future__ import annotations

from .app import create_app

__all__ = ["create_app"]
