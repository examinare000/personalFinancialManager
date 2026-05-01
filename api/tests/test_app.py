"""api サービス Flask アプリの振る舞いテスト。

ADR-014 / ADR-015 によりサービス専有テストは ``<service>/tests/`` 配下に
配置する。本ファイルは旧 ``tests/test_environment.py`` の
``test_api_create_appが200でhealthを返す`` を api サービス配下へ移管したもの。

実行: worker コンテナから（worker は dev extras + api extras を持つ）
    ``docker compose run --rm worker pytest api/tests/``
または横断一括:
    ``docker compose run --rm worker pytest``
"""

from __future__ import annotations


def test_api_create_appが200でhealthを返す() -> None:
    """``kakeibo_api.create_app()`` が Flask アプリを返し、``GET /health`` が
    ``{"status": "ok"}`` を 200 で応答すること。

    ヘルスチェックは Docker / Caddy / 監視系すべての疎通基盤になるため、
    レスポンス形式（status キーが ok）と HTTP ステータス（200）を契約として
    固定する。互換性破壊が発生したらここで早期検出する。
    """
    from kakeibo_api import create_app

    app = create_app()
    client = app.test_client()
    response = client.get("/health")

    assert response.status_code == 200
    assert response.is_json, "ヘルスチェックは JSON を返すこと"
    payload = response.get_json()
    assert payload == {"status": "ok"}
