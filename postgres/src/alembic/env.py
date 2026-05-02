"""Alembic 実行環境。

設計上のポイント:
- ``alembic.ini`` には接続文字列を書かず、ランタイムで環境変数 ``DATABASE_URL``
  を解決する（agent-rules/12-security-guidelines.md §認証情報）
- ``resolve_database_url()`` をモジュール公開関数として切り出し、
  単体テストで URL 解決ロジックだけを検証可能にする（tests/test_environment.py）
- 実 engine 構築には ``kakeibo_shared.db.session.build_database_url`` を使い、
  Docker secret 経由のパスワードを ``URL.set`` で注入する（ADR-016）。
  ``resolve_database_url()`` は文字列レベルの環境変数解決のみを責務とする
  後方互換 API として残置する
- ``alembic.context`` の属性参照（``context.config`` 等）は CLI 実行時に
  Alembic ランタイムが下準備をした後でしか有効でないため、pytest からの
  単純 import で AttributeError にならないよう try/except でガードする
- マイグレーション本体は Phase 1.1 で追加するため、現時点では最小骨格
"""

from __future__ import annotations

import os
from logging.config import fileConfig
from typing import Any

from alembic import context


def resolve_database_url() -> str:
    """環境変数 ``DATABASE_URL`` から接続文字列を取得する（後方互換 API）。

    alembic.ini の ``${DATABASE_URL}`` プレースホルダ展開だけでは、
    pytest からテストする際に ConfigParser の補間タイミングが揃わないため、
    本関数を独立させて単体テストの対象とする。

    実際の engine 構築では ``build_database_url`` を経由し、Docker secret 由来の
    パスワードを ``URL.set`` で注入する（ADR-016）。本関数は文字列レベルの
    環境変数解決のみを責務とし、worker/tests/test_environment.py の契約を保つ。
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "環境変数 DATABASE_URL が設定されていません。"
            "Docker Compose の environment または .env で指定してください。"
        )
    return url


# Alembic から参照されるターゲット metadata。Phase 1.1 で SQLAlchemy
# 宣言的モデルを kakeibo.db.models に作成し、ここで bind する。
target_metadata: Any = None


def run_migrations_offline() -> None:
    """オフラインモード（SQL スクリプト出力）でマイグレーションを実行する。

    オフラインモードは SQL スクリプトを生成するだけで実 DB に接続しないため、
    Docker secret 経由のパスワード注入は不要。``build_database_url`` が
    ``URL`` オブジェクトを返すのは ``URL.__repr__`` で password が ``***`` に
    マスクされる利点を活かすため（接続用途）だが、オフラインモードで生成される
    SQL スクリプトの URL 表記には password を一切含めない方が安全（防御的設計）。
    そのため ``resolve_database_url()`` の戻り値（password 抜きの URL 文字列）を
    そのまま使用し、``build_database_url`` 経路（``URL`` オブジェクト）は通さない。
    """
    url = resolve_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """オンラインモードで実 DB に接続してマイグレーションを実行する。

    ``build_database_url`` 経由で Settings から ``URL`` を構築することで、
    ``DATABASE_URL`` がパスワード抜きで宣言されている場合でも
    ``PG_PASSWORD_FILE`` 経由のパスワードが ``URL.set`` で注入される（ADR-016）。
    ``alembic.ini`` の ``sqlalchemy.url`` プレースホルダは経由せず、
    構築済み ``Engine`` を直接 connect する。
    """
    # 重い import は CLI 実行時にだけ行う（テストからの import を軽くする）。
    from sqlalchemy import create_engine, pool

    from kakeibo_shared.config import Settings
    from kakeibo_shared.db.session import build_database_url

    settings = Settings()  # pyright: ignore[reportCallIssue]
    url_obj = build_database_url(settings)
    connectable = create_engine(url_obj, poolclass=pool.NullPool, future=True)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


# pytest から本ファイルを単純 import するケースでは ``context.config`` の
# proxy が初期化されておらず NameError / AttributeError が発生する。
# Alembic CLI 経由で読まれた場合のみ logging 設定とマイグレーション起動を走らせる。
# Alembic は env.py の import を ``EnvironmentContext.run_env()`` 内で行い、
# その時点で proxy が確立されているため、両方を捕捉して安全に分岐する。
try:
    _config_file: str | None = context.config.config_file_name
    _is_offline: bool | None = context.is_offline_mode()
except (AttributeError, NameError):  # pragma: no cover - pytest 経由の import 時
    _config_file = None
    _is_offline = None

if _config_file is not None:
    fileConfig(_config_file)

if _is_offline is True:  # pragma: no cover - CLI offline 経由
    run_migrations_offline()
elif _is_offline is False:  # pragma: no cover - CLI online 経由
    run_migrations_online()
