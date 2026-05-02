"""SQLAlchemy エンジン・セッションの provider。

Phase 1.1 のマイグレーション・モデル実装と整合させ、Settings の
``database_url`` から engine を構築する責務をここに集約する。
本ファイルは骨格のみで、実際のクエリは domain / adapter 側で記述する。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import sessionmaker

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import Session

    from kakeibo_shared.config import Settings


def build_database_url(settings: Settings) -> URL:
    """Settings から SQLAlchemy ``URL`` オブジェクトを構築する。

    Docker secret 規約（``PG_PASSWORD_FILE``）で受け取ったパスワードを
    SQLAlchemy ``URL.set(password=...)`` 経由で URL に注入する。compose.yml の
    ``DATABASE_URL`` は ``postgresql+psycopg://kakeibo@postgres:5432/kakeibo``
    のようにパスワード抜きで宣言され、シークレットはランタイムで合流する。

    優先順:
      1. ``DATABASE_URL`` に既に password が含まれていればそれを使用
         （開発 ``.env`` で ``kakeibo:devpassword@...`` と書く運用を保全。
         空文字列 ``:@`` も意図的指定として尊重 ── ``local trust`` 等の
         パスワード不要 PostgreSQL 構成で運用余地を残す設計判断。
         SQLAlchemy 仕様で ``url.password`` は ``""`` と ``None`` を区別する）
      2. それ以外は ``settings.pg_password`` を ``URL.set`` で注入
      3. どちらも無い場合は ``password=None`` のまま返す（fail-open）
         → 接続時に DB が ``28P01`` を返すため診断は容易

    ``URL`` オブジェクトを返すことで、create_engine 側のログ・例外メッセージで
    SQLAlchemy 標準の ``URL.__repr__`` による password マスク（``***``）が効く。
    ``Settings.__repr__`` のマスクと合わせて二重防壁となる。詳細は ADR-016。
    """
    url = make_url(settings.database_url)
    if url.password is not None:
        return url
    if settings.pg_password:
        return url.set(password=settings.pg_password)
    return url


def create_db_engine(settings: Settings) -> Engine:
    """Settings から SQLAlchemy エンジンを生成する。

    psycopg3 ドライバを使うため URL は ``postgresql+psycopg://`` を必須とする。
    ``postgresql://`` 接頭辞は SQLAlchemy 2.x が ``psycopg2`` のエイリアスとして
    解決するため、psycopg2 が未インストールな本リポジトリでは
    ``ModuleNotFoundError: psycopg2`` で失敗する。``+psycopg`` を明示することで
    psycopg3 を選択する（``shared/pyproject.toml`` の依存と整合）。

    URL の組み立て（特に Docker secret 由来のパスワード注入）は
    ``build_database_url`` に委譲する。詳細は ADR-016。
    """
    return create_engine(build_database_url(settings), future=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """セッションファクトリを生成する。

    呼び出し側は ``with session_factory() as session:`` で取得し、
    トランザクション境界はユースケース層で明示的に制御する。
    """
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


__all__ = ["build_database_url", "create_db_engine", "create_session_factory"]
