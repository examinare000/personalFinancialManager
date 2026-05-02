"""``alembic upgrade head`` の冪等性検証。

検証戦略:
- ``conftest.applied_database`` フィクスチャは session 開始時点で 1 度
  ``alembic upgrade head`` を適用している。本ファイルではその後に
  もう 1 度 ``command.upgrade(config, "head")`` を呼び、例外なく完了することを確認する。
- 2 回目の upgrade 後も ``alembic_version.version_num`` が末端リビジョン
  ``0005`` を保持し、テーブル数も変化しないことを併せて確認する。

設計準拠:
- spec §受入条件「alembic upgrade head を 2 回連続で実行しても 2 回目が no-op として成功」
- spec §テスト計画3「適用済み DB に対する upgrade 再実行が成功し、テーブル数・行数が変化しない」
- planner レポート §5.5 #1, #2
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from alembic.config import Config

    import psycopg


def _make_alembic_config(repo_root: Path) -> Config:
    """テスト用に alembic Config を組み立てる小ヘルパ。

    ``alembic.ini`` の ``script_location = alembic`` は CWD 相対で解釈される
    （CWD=shared/ では見つからず CommandError）ため、ここで絶対パスに上書きする。
    conftest.make_alembic_config と同等の振る舞いだが、テストファイルから
    隣接 conftest.py の関数を直接 import するのを避けるため重複させている。
    """
    from alembic.config import Config

    ini_path = repo_root / "postgres" / "src" / "alembic.ini"
    config = Config(str(ini_path))
    config.set_main_option(
        "script_location",
        str(repo_root / "postgres" / "src" / "alembic"),
    )
    return config


_LATEST_REVISION = "0005"


def _count_public_tables(connection: psycopg.Connection) -> int:
    """public スキーマの BASE TABLE 数を返す（alembic_version 含む）。"""
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """,
        )
        row = cur.fetchone()
    assert row is not None
    return int(row[0])


def test_2回目のupgrade_headが例外なく成功する(
    psycopg_connection: psycopg.Connection,
    repo_root: Path,
) -> None:
    """既にマイグレーション適用済みの DB に対して ``alembic upgrade head`` を
    再実行しても例外を発生させずに成功すること（spec §受入条件 / §テスト計画3）。

    Alembic は同 revision に対する再 upgrade を no-op として扱うため、
    本テストは「実装が標準仕様から外れていない」ことを担保する回帰防止テスト。
    """
    from alembic import command

    # applied_database フィクスチャで DATABASE_URL は既に設定済みだが、
    # 明示的に検証して契約を固定する。
    assert os.environ.get("DATABASE_URL"), (
        "applied_database フィクスチャ後に DATABASE_URL が設定されていません"
    )

    config = _make_alembic_config(repo_root)
    # ここで例外が出れば pytest が失敗扱いにする。明示の assert は不要。
    command.upgrade(config, "head")


def test_2回目upgrade後のリビジョンが末端と一致する(
    psycopg_connection: psycopg.Connection,
    repo_root: Path,
) -> None:
    """``alembic_version.version_num`` が 2 回目 upgrade 後も最新リビジョン
    ``0005`` を指していること。

    planner §4.2 の revision id 命名規約 ``0001`` 〜 ``0005`` に従う。
    末端リビジョン名が変われば本テストは失敗し、命名規約からの逸脱を検出する。
    """
    from alembic import command

    config = _make_alembic_config(repo_root)
    command.upgrade(config, "head")

    with psycopg_connection.cursor() as cur:
        cur.execute("SELECT version_num FROM alembic_version")
        row = cur.fetchone()

    assert row is not None, "alembic_version テーブルにレコードが存在しません"
    assert row[0] == _LATEST_REVISION, (
        f"alembic_version が末端リビジョンと一致しません: "
        f"expected={_LATEST_REVISION}, actual={row[0]!r}"
    )


def test_2回目upgrade前後でテーブル数が一致する(
    psycopg_connection: psycopg.Connection,
    repo_root: Path,
) -> None:
    """2 回目 ``upgrade head`` が新規テーブルを生成しない（no-op である）ことを、
    ``information_schema.tables`` のカウント差分で検証する。

    1 回目 upgrade（フィクスチャ）→ テーブル数 N。
    2 回目 upgrade → テーブル数 N（不変）。
    spec §テスト計画3「テーブル数が変化しない」を直接固定する。
    """
    from alembic import command

    before = _count_public_tables(psycopg_connection)

    config = _make_alembic_config(repo_root)
    command.upgrade(config, "head")

    # 別接続でカウントを取り直す（カタログ更新の即時反映確認）。
    after = _count_public_tables(psycopg_connection)

    assert before == after, (
        f"2 回目 upgrade でテーブル数が変化しました: before={before}, after={after}"
    )
