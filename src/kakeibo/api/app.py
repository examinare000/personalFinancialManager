"""Flask アプリケーションファクトリ。

設計指針:
- Phase 0 では ``/health`` のみを提供する最小スタブとする。
- Phase 3.1 で Blueprint 単位の REST エンドポイント（資産・取引・予算等）を
  追加する際、本ファクトリがその唯一の登録ポイントとなる。
- Werkzeug ベースの開発サーバで起動するスタブだが、本番デプロイでは
  ``gunicorn`` などの WSGI サーバから ``create_app`` を呼ぶ前提でも動く。
- 環境変数による設定上書きは ``kakeibo.config.Settings`` 経由に集約し、
  Flask の ``app.config`` には直接機密情報を載せない（``__repr__`` での
  漏洩防止のため）。
"""

from __future__ import annotations

from typing import Any

from flask import Flask, jsonify
from flask.wrappers import Response


def create_app() -> Flask:
    """Flask アプリケーションを生成して返す。

    docstring と日本語コメントで責務を明示し、ルーティング追加時の
    変更箇所を本関数だけに局所化する。
    """
    app = Flask(__name__)

    @app.get("/health")
    def health() -> tuple[Response, int]:  # pyright: ignore[reportUnusedFunction]
        """ヘルスチェックエンドポイント。

        - レスポンス: ``{"status": "ok"}``
        - HTTP ステータス: 200
        - 認証不要（Caddy / Docker HEALTHCHECK / 監視からの叩き先）

        将来 DB 接続・依存サービスの疎通も確認したくなった場合は、
        ``/health`` を liveness（軽量）に維持し、新たに ``/ready``
        を readiness（重い疎通検査）として追加する設計に分離する。
        """
        payload: dict[str, Any] = {"status": "ok"}
        return jsonify(payload), 200

    return app


__all__ = ["create_app"]
