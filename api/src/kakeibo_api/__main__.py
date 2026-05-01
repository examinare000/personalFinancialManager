"""``python -m kakeibo_api`` で Flask 開発サーバを起動するエントリポイント。

Phase 0 ではこの開発サーバをそのまま Docker コンテナで動かす（スタブ）。
Phase 3.x 以降は ``gunicorn -b 0.0.0.0:8000 'kakeibo_api:create_app()'`` で
本番起動するため、本ファイルは開発専用の互換レイヤとして残す。

環境変数:
- ``API_HOST``: バインドホスト（既定: ``0.0.0.0``）
- ``API_PORT``: バインドポート（既定: ``8000``）
- ``FLASK_DEBUG``: ``1`` で debug モード起動
"""

from __future__ import annotations

import os

from kakeibo_api import create_app


def main() -> None:
    """開発用 Werkzeug サーバを起動する。"""
    host = os.environ.get("API_HOST", "0.0.0.0")
    # 0.0.0.0 バインドはコンテナの外に公開する用途で必要。host バインドは
    # compose.override.yml で 127.0.0.1:8000 に絞るため、開発時の外部到達は
    # ローカルホストのみに限定される（agent-rules/12-security-guidelines）。
    port = int(os.environ.get("API_PORT", "8000"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"

    app = create_app()
    app.run(host=host, port=port, debug=debug, use_reloader=False)


if __name__ == "__main__":
    main()
