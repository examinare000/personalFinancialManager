"""SQLAlchemy エンジン・セッションの provider。

Phase 1.1 のマイグレーション・モデル実装と整合させ、Settings の
``database_url`` から engine を構築する責務をここに集約する。
本ファイルは骨格のみで、実際のクエリは domain / adapter 側で記述する。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import Session

    from kakeibo_shared.config import Settings


def create_db_engine(settings: Settings) -> Engine:
    """Settings から SQLAlchemy エンジンを生成する。

    psycopg3 ドライバを使うため URL は ``postgresql+psycopg://`` を必須とする。
    ``postgresql://`` 接頭辞は SQLAlchemy 2.x が ``psycopg2`` のエイリアスとして
    解決するため、psycopg2 が未インストールな本リポジトリでは
    ``ModuleNotFoundError: psycopg2`` で失敗する。``+psycopg`` を明示することで
    psycopg3 を選択する（``shared/pyproject.toml`` の依存と整合）。
    """
    return create_engine(settings.database_url, future=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """セッションファクトリを生成する。

    呼び出し側は ``with session_factory() as session:`` で取得し、
    トランザクション境界はユースケース層で明示的に制御する。
    """
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


__all__ = ["create_db_engine", "create_session_factory"]
