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

    psycopg3 ドライバを使うため URL は ``postgresql+psycopg://`` を推奨するが、
    ``postgresql://`` でも psycopg2 が無い環境では psycopg3 が暗黙採用される。
    """
    return create_engine(settings.database_url, future=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """セッションファクトリを生成する。

    呼び出し側は ``with session_factory() as session:`` で取得し、
    トランザクション境界はユースケース層で明示的に制御する。
    """
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


__all__ = ["create_db_engine", "create_session_factory"]
