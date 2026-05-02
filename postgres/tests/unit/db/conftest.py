"""DB スキーマ検証用フィクスチャ。

設計判断:
- spec §実装方針8 と planner レポート §3.4 に従い、テスト用 PostgreSQL は
  ``testcontainers`` で起動する（``pytest-postgresql`` は dev 依存に未宣言のため不採用）。
- session スコープでコンテナを 1 度だけ起動し、`alembic upgrade head` を 1 度だけ
  適用することで、planner §5.5 の「テスト全体 10 秒以内」という時間予算に収める。
- Docker 利用不可な環境（CI worker / ローカル） では ``shutil.which("docker")`` の
  欠落、または ``container.start()`` の例外（daemon 未起動 等）を検知して
  ``pytest.skip`` する。これは tests/test_environment.py の既存慣習に合わせた挙動。
- alembic は ``alembic.command.upgrade()`` を直接呼ぶ。subprocess 経由は
  スタックトレースが取得できず、テスト失敗時の原因究明が困難なため採用しない。
- DB アクセスは ``psycopg`` を直接使う。SQLAlchemy 例外ラップを介さないため、
  ``psycopg.errors.UniqueViolation`` 等の具体例外型を ``pytest.raises`` で素直に
  捕捉できる（planner レポート §4.2 と整合）。
- alembic.ini の ``script_location = alembic`` は CWD 相対で解決されるため、
  pytest 実行時 CWD（``/app/shared`` 想定）からは見つからない。テスト用に
  ``Config.set_main_option("script_location", ...)`` で絶対パスへ上書きし、
  本番運用（worker コンテナ内 ``cd /app/postgres/src && alembic upgrade head``）の
  挙動を一切変えない方針を採る（agent-rules/00-core-principles.md デグレ防止）。
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from alembic.config import Config
    import psycopg
    from testcontainers.postgres import PostgresContainer


_DOCKER_UNAVAILABLE_MESSAGE = "docker daemon が利用不可のためスキップ"


def _repo_root() -> Path:
    """このフィクスチャファイルから見たリポジトリルート。

    postgres/tests/unit/db/conftest.py から 4 階層上る
    （db → unit → tests → postgres → リポジトリルート）。
    postgres/tests/conftest.py の ``repo_root`` フィクスチャと同じパスを
    指すが、session 開始前から使うためフィクスチャに依存しない関数として
    独立させる。
    """
    return Path(__file__).resolve().parents[4]


def make_alembic_config(repo_root: Path) -> Config:
    """テスト用に alembic Config を組み立てる共通ヘルパ。

    ``alembic.ini`` の ``script_location = alembic`` は CWD 相対で解釈されるため、
    pytest 実行 CWD（shared/）からは ``alembic`` ディレクトリが見えず
    ``CommandError: Path doesn't exist: alembic`` で失敗する。本ヘルパでは
    ``script_location`` を ``postgres/src/alembic`` の絶対パスへ上書きし、
    どの CWD で呼ばれても確実に解決できるようにする。

    本番運用（``cd /app/postgres/src && alembic upgrade head``）には影響しない。
    """
    from alembic.config import Config

    ini_path = repo_root / "postgres" / "src" / "alembic.ini"
    config = Config(str(ini_path))
    config.set_main_option(
        "script_location",
        str(repo_root / "postgres" / "src" / "alembic"),
    )
    return config


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    """testcontainers で PostgreSQL 16 を 1 度だけ起動する。

    - ``driver="psycopg"`` を明示し、``get_connection_url()`` が返す URL を
      ``postgresql+psycopg://`` 形式に統一する（pyproject.toml 依存と整合）。
    - 起動失敗（docker daemon 未起動等）は skip 扱い。テスト失敗ではない。
    """
    if shutil.which("docker") is None:
        pytest.skip(_DOCKER_UNAVAILABLE_MESSAGE)

    from testcontainers.postgres import PostgresContainer  # 重い import を遅延

    container = PostgresContainer("postgres:16-alpine", driver="psycopg")
    try:
        container.start()
    except Exception as exc:  # docker daemon 未起動 / image pull 失敗 等
        pytest.skip(f"PostgresContainer 起動に失敗したためスキップ: {exc}")

    try:
        yield container
    finally:
        container.stop()


@pytest.fixture(scope="session")
def applied_database(postgres_container: PostgresContainer) -> str:
    """testcontainers で起動した PostgreSQL に ``alembic upgrade head`` を 1 度適用する。

    Returns:
        psycopg 接続用の DSN（``postgresql://`` 形式、SQLAlchemy ドライバ接頭辞なし）。
    """
    from alembic import command

    sqlalchemy_url = postgres_container.get_connection_url()
    psycopg_dsn = postgres_container.get_connection_url(driver=None)

    # alembic/env.py の resolve_database_url() は環境変数を一次入力とする。
    # session 終了で破棄されるため、復元処理は不要。
    os.environ["DATABASE_URL"] = sqlalchemy_url

    config = make_alembic_config(_repo_root())
    command.upgrade(config, "head")

    return psycopg_dsn


@pytest.fixture
def psycopg_connection(applied_database: str) -> Iterator[psycopg.Connection]:
    """テストごとに psycopg 接続を確立し、テスト終了時にロールバックする。

    制約違反テストで INSERT が成功してしまうケースでも、ロールバックにより
    後続テストへの汚染を防ぐ。``autocommit=False`` で明示的にトランザクション
    境界を持つ。
    """
    # import をフィクスチャ内に閉じ、コレクション時の余計なロードを避ける。
    import psycopg

    connection = psycopg.connect(applied_database, autocommit=False)
    try:
        yield connection
    finally:
        connection.rollback()
        connection.close()
